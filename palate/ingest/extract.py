"""Stage-2 LLM extraction. OWNER A. See docs/trd-a-ingest.md step 7.

Routed through Merge Gateway via palate.llm — you do not call Anthropic directly.
"""

from palate import config, contracts, db, llm

BATCH_SIZE = 20

PROMPT_RULES = """\
Extract one entry per booking from the messages below.

Times are LOCAL WALL-CLOCK with no timezone: copy what the email says.
If a field is not explicitly stated, return null; never infer or estimate.
A cancellation email for a prior booking has status "cancelled" and
cancelled_at set if the cancellation time is stated.
Ignore marketing email entirely.

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
    db.executemany(
        "UPDATE raw_message SET extracted = 1 WHERE id = ?",
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
            v["source"] = "gmail"
            v["source_ref"] = source_ref
            v["vendor"] = raw["matched_vendor"]
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