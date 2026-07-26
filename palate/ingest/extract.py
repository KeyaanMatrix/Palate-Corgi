"""Stage-2 LLM extraction. OWNER A. See docs/trd-a-ingest.md step 7.

Routed through Merge Gateway via palate.llm — you do not call Anthropic directly.
"""

import re
from datetime import datetime

from palate import config, contracts, db, llm

BATCH_SIZE = 20

PROMPT_RULES = """\
Extract one entry per booking from the messages below.

Times are LOCAL WALL-CLOCK with no timezone: copy what the email says.
If a field is not explicitly stated, return null; never infer or estimate.
A cancellation email for a prior booking has status "cancelled" and
cancelled_at set if the cancellation time is stated.
Ignore marketing email entirely.
For calendar rows, ignore ordinary work meetings and reminders. Extract only
events that name a restaurant, bar, hotel, attraction, ticketed event, or other
place the user plausibly visited.

For every extracted visit:
- source_ref MUST be the MESSAGE_ID shown for that message.
- vendor should be the MATCHED_VENDOR shown for that message.
- Do not invent a city, party size, price, cuisine, seat, or time.
"""


def _prompt_for(rows) -> str:
    parts = [PROMPT_RULES]

    for row in rows:
        parts.append(
            f"""
--- MESSAGE ---
MESSAGE_ID: {row["id"]}
SOURCE: {row["source"]}
MATCHED_VENDOR: {row["matched_vendor"]}
FROM: {row["sender"] or ""}
SUBJECT: {row["subject"] or ""}
RECEIVED_AT: {row["received_at"] or ""}

BODY:
{row["body"] or ""}
--- END MESSAGE ---
""".strip()
        )

    return "\n\n".join(parts)


def _mark_extracted(rows) -> None:
    """Retain only audit metadata after extracting; discard private message text."""
    db.executemany(
        """
        UPDATE raw_message
        SET extracted = 1, sender = NULL, subject = NULL, body = NULL
        WHERE id = ?
        """,
        [(row["id"],) for row in rows],
    )


def extract_pending(batch_size: int = BATCH_SIZE) -> int:
    """Batch matched messages -> visit rows. Returns rows written.

    llm.complete_json returning None means DROP THE BATCH. Do not retry, do not
    repair. Recall is not the constraint tonight; precision is.
    """
    if batch_size <= 0:
        return 0

    written = 0

    while True:
        rows = db.rows(
            """
            SELECT id, sender, subject, body, received_at, matched_vendor
                 , source
            FROM raw_message
            WHERE matched_vendor IS NOT NULL
              AND extracted = 0
            ORDER BY received_at
            LIMIT ?
            """,
            (batch_size,),
        )

        if not rows:
            break

        # Keep the real database metadata keyed by Gmail message ID.
        by_id = {row["id"]: row for row in rows}

        result = llm.complete_json(
            _prompt_for(rows),
            contracts.VISIT_EXTRACTION_SCHEMA,
            purpose="extract",
        )

        # Contract: failed batch gets dropped, never repaired/retried.
        if result is None:
            _mark_extracted(rows)
            continue

        visits = result.get("visits", [])

        if not isinstance(visits, list):
            _mark_extracted(rows)
            continue

        for extracted in visits:
            if not isinstance(extracted, dict):
                continue

            v = dict(extracted)

            source_ref = v.get("source_ref")

            # Never accept a model-invented message reference.
            if source_ref not in by_id:
                continue

            raw = by_id[source_ref]

            # Deterministic facts come from our pipeline, not the model.
            v["source"] = raw["source"]
            v["source_ref"] = source_ref
            v["vendor"] = raw["matched_vendor"] if raw["source"] == "gmail" else None
            v["place_id"] = None
            v["intent_only"] = 0

            city = v.get("city")
            v["is_travel"] = int(
                bool(city)
                and city.strip().casefold() != config.HOME_CITY.strip().casefold()
            )

            if not contracts.valid_visit(v):
                continue

            v["id"] = contracts.visit_id(
                v["source"],
                v["source_ref"],
                v["place_name_raw"],
                v.get("scheduled_at"),
            )

            db.upsert_visit(v)
            written += 1

        _mark_extracted(rows)

    return written


def _normal_place(value: str) -> str:
    value = re.sub(r"^\s*the\s+", "", str(value or ""), flags=re.IGNORECASE)
    value = re.split(r"\s+(?:[-–—|]|\()\s*", value, maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _scheduled(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)[:19])
    except (TypeError, ValueError):
        return None


def dedupe_visits(window_hours: int = 3) -> int:
    """Collapse confirmation/modification/cancellation duplicates.

    A later cancellation email often has a different provider message id from
    the original confirmation. Both must not become separate bookings in the
    profile. We keep the strongest/latest status, fill its missing fields from
    the richer duplicate, and delete only same-place, same-city rows within the
    configured time window.
    """
    rows = db.rows(
        "SELECT * FROM visit WHERE intent_only=0 AND scheduled_at IS NOT NULL"
        " AND source IN ('gmail','calendar') ORDER BY scheduled_at, created_at"
    )
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        payload = dict(row)
        place = _normal_place(payload.get("place_name_raw"))
        when = _scheduled(payload.get("scheduled_at"))
        if not place or when is None:
            continue
        city = re.sub(r"\s+", " ", str(payload.get("city") or "").casefold()).strip()
        grouped.setdefault((place, city), []).append(payload)

    clusters: list[list[dict]] = []
    max_seconds = max(0, int(window_hours)) * 3600
    for candidates in grouped.values():
        current: list[dict] = []
        anchor: datetime | None = None
        for row in candidates:
            when = _scheduled(row["scheduled_at"])
            if anchor is None or (when - anchor).total_seconds() <= max_seconds:
                current.append(row)
                anchor = when if anchor is None else anchor
            else:
                if len(current) > 1:
                    clusters.append(current)
                current = [row]
                anchor = when
        if len(current) > 1:
            clusters.append(current)

    status_rank = {
        "attended_unbooked": 1,
        "confirmed": 2,
        "modified": 3,
        "cancelled": 4,
    }
    fill_fields = [
        "vendor",
        "place_id",
        "city",
        "category",
        "cuisine",
        "price_band",
        "party_size",
        "booked_at",
        "cancelled_at",
        "seat",
        "raw_total_cents",
    ]
    removed = 0
    with db.connect() as conn:
        for cluster in clusters:

            def score(row: dict) -> tuple[int, int, int, str]:
                richness = sum(
                    row.get(field) not in (None, "") for field in fill_fields
                )
                return (
                    status_rank.get(str(row.get("status")), 0),
                    richness,
                    int(row.get("source") == "gmail"),
                    str(row.get("created_at") or ""),
                )

            winner = max(cluster, key=score)
            merged = dict(winner)
            for candidate in sorted(cluster, key=score, reverse=True):
                for field in fill_fields:
                    if merged.get(field) in (None, "") and candidate.get(field) not in (
                        None,
                        "",
                    ):
                        merged[field] = candidate[field]

            conn.execute(
                "UPDATE visit SET "
                + ", ".join(f"{field}=?" for field in fill_fields)
                + " WHERE id=?",
                [merged.get(field) for field in fill_fields] + [winner["id"]],
            )
            losers = [row["id"] for row in cluster if row["id"] != winner["id"]]
            conn.executemany(
                "DELETE FROM visit WHERE id=?", [(value,) for value in losers]
            )
            removed += len(losers)
    return removed
