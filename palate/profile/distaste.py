"""Revealed aversion. OWNER B. See docs/trd-b-profile.md.

This file is the technical claim (PRD section 1): every recommender models
preference, none model revealed distaste. Guard every metric with a minimum n —
reporting noise as insight is worse than reporting nothing.

Pure SQL + stdlib, same as metrics.py. The row vocabulary (REAL / HAPPENED /
DINING) is imported from there rather than restated, so the two files can never
drift apart on what counts as a row.

Every function returns (value, evidence-kwargs) exactly like metrics.py.
"""

import json
import re
from collections import defaultdict

from palate import db

from .metrics import HAPPENED, REAL

MIN_N_THRESHOLD = 3   # bookings at a price band before a threshold is reportable
MIN_N_AVERSION = 2    # distinct other cuisines chosen since the one trial
MIN_N_CATEGORY = 2    # rows in a category before it can be called avoided

CANCEL_RATE = 0.5     # "cancels more often than not"
AVOIDED_RATE = 0.5    # a category must be avoided at least half the time
AVOIDED_RATIO = 1.5   # ...and at least this many times the overall baseline


def _norm(name: str | None) -> str:
    """Normalize a place name for matching a Notion save against a real visit.

    Stricter than the LOWER(TRIM()) used for the revisit count in metrics.py:
    saves are typed by hand ("Sushi Shin." / "sushi shin"), so punctuation and
    doubled whitespace have to go or the aspiration gap silently overcounts.
    """
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def _city(value: str | None) -> str:
    """Match key for a city name. Real rows carry 'San Francisco', 'san francisco'
    and 'San  Francisco' for the same place; compared raw, they read as three
    cities and every same-city guard below quietly stops counting."""
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _tags(raw: str | None) -> list[str]:
    """cuisine is a JSON array in the column. Bad JSON means no tags, not a crash.

    Deduplicated: extraction can emit ["sushi", "Sushi"], and a repeated tag
    would make one visit look like two — which is enough to disqualify a
    cuisine from "tried exactly once" and lose the aversion entirely.
    """
    try:
        parsed = json.loads(raw) or []
    except (json.JSONDecodeError, TypeError):
        return []
    seen: dict[str, None] = {}
    for tag in parsed:
        cleaned = str(tag).lower().strip()
        if cleaned:
            seen.setdefault(cleaned)
    return list(seen)


def _visited_names() -> set[str]:
    return {
        _norm(r["place_name_raw"])
        for r in db.rows(f"SELECT place_name_raw FROM visit WHERE {REAL} AND {HAPPENED}")
    }


# ------------------------------------------------------------------- distaste


def cancellation_threshold() -> tuple[int | None, dict]:
    """Lowest price_band where the cancel rate is above half.

    Evidence carries 'k of n at band B'. The line is "You cancel above
    $180/head. Four for four." A threshold with no count is worthless, and a
    threshold resting on one booking is a lie, so a band needs at least
    MIN_N_THRESHOLD bookings before it can be reported at all.

    Notion saves are excluded by REAL: a place you saved was never booked, so
    it can never have been cancelled. Counting saves in the denominator would
    quietly drag every band's rate toward zero.
    """
    bands = db.rows(
        "SELECT price_band band, COUNT(*) n,"
        " SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) k"
        f" FROM visit WHERE {REAL} AND price_band IS NOT NULL"
        " GROUP BY price_band ORDER BY price_band"
    )
    if not bands:
        return None, {"n": 0, "of": 0, "note": "no price bands on any booking"}

    for row in bands:
        if row["n"] >= MIN_N_THRESHOLD and row["k"] / row["n"] > CANCEL_RATE:
            return row["band"], {
                "n": row["k"],
                "of": row["n"],
                "note": f"{row['k']} of {row['n']} bookings at band {row['band']} were cancelled",
            }

    # Nothing qualified. Say what the worst band actually looked like, so the
    # absence is inspectable instead of just being a null.
    worst = max(bands, key=lambda r: (r["k"] / r["n"], r["n"]))
    return None, {
        "n": worst["k"],
        "of": worst["n"],
        "note": (
            f"no band cancels more than half the time; worst is {worst['k']} of"
            f" {worst['n']} at band {worst['band']}"
        ),
    }


def cuisine_aversion(min_alternatives: int = 3) -> tuple[list[str], dict]:
    """Cuisines tried exactly once and never returned to.

    A single visit only means something if going back was possible and was
    passed over. Two guards enforce that, and both are counted *in the city
    where the trial happened* — a cuisine tried once in Mexico City was not
    rejected in San Francisco, it was simply out of reach:

      1. at least `min_alternatives` later dining bookings in that city, and
      2. at least MIN_N_AVERSION distinct other cuisines among them.

    The second guard is what stops "you had three more dinners" from meaning
    "you went back to the same Italian place three times". A candidate that
    fails either guard is dropped, not reported with a caveat — the list is
    read on stage, and a caveat does not survive being read out loud.
    """
    rows = db.rows(
        "SELECT TRIM(place_name_raw) place, city, scheduled_at, cuisine FROM visit"
        f" WHERE {REAL} AND {HAPPENED} AND cuisine IS NOT NULL"
        " ORDER BY scheduled_at"
    )
    trials: dict[str, list[dict]] = defaultdict(list)
    tagged: list[dict] = []
    for r in rows:
        tags = _tags(r["cuisine"])
        if not tags:
            continue
        entry = {
            "place": r["place"],
            "city": r["city"],
            "city_key": _city(r["city"]),
            "when": r["scheduled_at"],
            "tags": set(tags),
        }
        tagged.append(entry)
        for tag in tags:
            trials[tag].append(entry)

    if not trials:
        return [], {"n": 0, "of": 0, "note": "no cuisine tags on any completed visit"}

    aversions: list[str] = []
    notes: list[str] = []
    for tag, visits in sorted(trials.items()):
        if len(visits) != 1:
            continue
        trial = visits[0]
        since = [
            e
            for e in tagged
            if e["when"] > trial["when"]
            and e["city_key"] == trial["city_key"]
            and tag not in e["tags"]
        ]
        others = {t for e in since for t in e["tags"] if t != tag}
        if len(since) < min_alternatives or len(others) < MIN_N_AVERSION:
            continue
        aversions.append(tag)
        # Whitespace-collapsed for display only. Case is left alone: "SF" is not
        # something to title-case, and this note gets read out loud as written.
        where = " ".join((trial["city"] or "").split()) or "the same city"
        notes.append(
            f"{tag}: one visit ({trial['place']}, {trial['when'][:10]}), {len(since)}"
            f" later dining bookings in {where}, never went back"
        )

    return aversions, {
        "n": len(aversions),
        "of": len(trials),
        "note": "; ".join(notes) if notes else "no cuisine cleared the return-opportunity guard",
    }


def avoided_categories() -> tuple[list[str], dict]:
    """Categories booked-then-cancelled, or saved-never-visited, above baseline.

    Both behaviours are the same signal wearing different clothes — the user
    put it on a list and then did not go — so they share a numerator. The
    seeded 9am tour is the archetype: booked three weeks out, killed the night
    before.

    A category has to clear all three bars: at least MIN_N_CATEGORY rows, an
    avoided rate of at least AVOIDED_RATE, and AVOIDED_RATIO times the rate
    across every row in the table. The baseline term is what keeps this
    honest — if the user cancels everything, nothing is specifically avoided.
    """
    visited = _visited_names()
    rows = db.rows(
        "SELECT COALESCE(category, 'uncategorized') cat, status, intent_only,"
        " place_name_raw FROM visit"
    )
    if not rows:
        return [], {"n": 0, "of": 0, "note": "no visits"}

    total = defaultdict(int)
    avoided = defaultdict(int)
    for r in rows:
        cat = r["cat"]
        total[cat] += 1
        cancelled = r["status"] == "cancelled"
        saved_unvisited = bool(r["intent_only"]) and _norm(r["place_name_raw"]) not in visited
        if cancelled or saved_unvisited:
            avoided[cat] += 1

    all_rows = sum(total.values())
    baseline = sum(avoided.values()) / all_rows
    floor = max(AVOIDED_RATE, AVOIDED_RATIO * baseline)

    hits = [
        cat
        for cat, n in total.items()
        if n >= MIN_N_CATEGORY and avoided[cat] / n >= floor
    ]
    hits.sort(key=lambda c: (-avoided[c] / total[c], c))

    if not hits:
        return [], {
            "n": 0,
            "of": all_rows,
            "note": f"no category is avoided at {floor:.0%}+; baseline is {baseline:.0%}",
        }
    detail = "; ".join(
        f"{avoided[c]} of {total[c]} {c} rows cancelled or saved and never visited" for c in hits
    )
    return hits, {
        "n": sum(avoided[c] for c in hits),
        "of": sum(total[c] for c in hits),
        "note": f"{detail} (baseline {sum(avoided.values())} of {all_rows})",
    }


def aspiration_gap() -> tuple[list[dict], dict]:
    """intent_only rows (Notion saves) with no matching completed visit.

    PRD 8.2 step 4: "I saved 14. I went to 2." Biggest emotional hit in the
    demo, and it exists only because Merge is in the stack. Matched on
    normalized name — a save and a reservation are typed by different hands.
    """
    visited = _visited_names()
    saves = db.rows(
        "SELECT place_name_raw name, city, category, source, created_at FROM visit"
        " WHERE intent_only = 1 ORDER BY created_at, place_name_raw"
    )
    gap = [
        {
            "name": r["name"],
            "city": r["city"],
            "category": r["category"],
            "source": r["source"],
            "saved_at": r["created_at"],
        }
        for r in saves
        if _norm(r["name"]) not in visited
    ]
    if not saves:
        return [], {"n": 0, "of": 0, "note": "no saved-but-unvisited places"}
    return gap, {
        "n": len(gap),
        "of": len(saves),
        "note": f"{len(gap)} of {len(saves)} saved places have no completed visit",
    }
