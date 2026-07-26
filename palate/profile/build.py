"""Profile assembly. OWNER B. See docs/trd-b-profile.md.

load_profile() is what C and D call. Keep that signature stable.

Nothing here computes a number. Every value comes from metrics.py or
distaste.py as a (value, evidence) pair, and this file's only job is to keep
those two halves together — the number and the row count behind it travel as
one thing, all the way to the stage.
"""

import json

from palate import contracts, db

from . import distaste, metrics
from .metrics import DINING, HAPPENED, REAL

# Keys computed here that are not in contracts.TASTE_PROFILE_KEYS. Additive
# only: C and D read by key, so an extra key costs them nothing, and the copy
# needs the repeat places to say "the same six, 41 times".
EXTRA_KEYS = ["most_repeated", "computed_at"]


def build_profile() -> dict:
    """Run every metric, assemble the dict, write a taste_profile row, return it."""
    ev = contracts.Evidence()

    def take(key: str, result: tuple):
        """Unpack (value, evidence-kwargs) and file the evidence under `key`."""
        value, evidence = result
        ev.add(key, **evidence)
        return value

    revisit = take("revisit_ratio", metrics.revisit_ratio())

    profile = {
        "home_city": take("home_city", metrics.home_city()),
        "earliest_activity_hour": take("earliest_activity_hour", metrics.earliest_activity_hour()),
        "peak_dining_hour": take("peak_dining_hour", metrics.peak_dining_hour()),
        "preferred_days": take("preferred_days", metrics.preferred_days()),
        "typical_party_size": take("typical_party_size", metrics.typical_party_size()),
        "price_ceiling": take("price_ceiling", metrics.price_ceiling()),
        "cancellation_threshold": take(
            "cancellation_threshold", distaste.cancellation_threshold()
        ),
        "revisit_ratio": revisit,
        "novelty_appetite": metrics.novelty_appetite(revisit),  # derived; no evidence of its own
        "cuisine_affinity": take("cuisine_affinity", metrics.cuisine_affinity()),
        "cuisine_aversion": take("cuisine_aversion", distaste.cuisine_aversion()),
        "booking_lead_time_median_days": take(
            "booking_lead_time_median_days", metrics.booking_lead_time_median_days()
        ),
        "seat_preference": take("seat_preference", metrics.seat_preference()),
        "pace": take("pace", metrics.pace()),
        "avoided_categories": take("avoided_categories", distaste.avoided_categories()),
        "aspiration_gap": take("aspiration_gap", distaste.aspiration_gap()),
        "most_repeated": take("most_repeated", metrics.most_repeated()),
        "computed_at": db.now(),
        "evidence": ev.as_dict(),
    }

    missing = contracts.profile_is_sourced(profile)
    if missing:
        raise ValueError(f"unsourced profile keys: {missing}")

    db.execute(
        "INSERT INTO taste_profile (computed_at, payload) VALUES (?, ?)",
        (profile["computed_at"], contracts.dumps(profile)),
    )
    return profile


def load_profile() -> dict | None:
    """Latest taste_profile row, parsed. THE CROSS-OWNER SEAM — do not rename."""
    row = db.one("SELECT payload FROM taste_profile ORDER BY id DESC LIMIT 1")
    if row is None:
        return None
    try:
        return json.loads(row["payload"])
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- explain

# The rows behind each number, so a challenge at 3 AM is settled by looking at
# the data instead of re-reading the code. TRD section 9: do not ship a number
# you cannot source.
_EXPLAIN: dict[str, tuple[str, str]] = {
    "home_city": (
        "cities across every real row",
        f"SELECT city, COUNT(*) rows FROM visit WHERE {REAL} AND city IS NOT NULL"
        " GROUP BY city ORDER BY rows DESC",
    ),
    "earliest_activity_hour": (
        "completed visits by start hour, earliest first (lodging excluded)",
        "SELECT CAST(strftime('%H', scheduled_at) AS INTEGER) hour, place_name_raw, city,"
        f" scheduled_at FROM visit WHERE {REAL} AND {HAPPENED}"
        " AND (category IS NULL OR category != 'lodging') ORDER BY hour LIMIT 12",
    ),
    "peak_dining_hour": (
        "restaurant and bar bookings by start hour",
        "SELECT CAST(strftime('%H', scheduled_at) AS INTEGER) hour, COUNT(*) rows FROM visit"
        f" WHERE {REAL} AND {HAPPENED} AND {DINING} GROUP BY hour ORDER BY rows DESC",
    ),
    "preferred_days": (
        "dining bookings by weekday (0=Sun)",
        "SELECT strftime('%w', scheduled_at) dow, COUNT(*) rows FROM visit"
        f" WHERE {REAL} AND {HAPPENED} AND {DINING} GROUP BY dow ORDER BY rows DESC",
    ),
    "typical_party_size": (
        "reservations by party size",
        f"SELECT party_size, COUNT(*) rows FROM visit WHERE {REAL} AND party_size IS NOT NULL"
        " GROUP BY party_size ORDER BY rows DESC",
    ),
    "price_ceiling": (
        "completed visits by price band",
        f"SELECT price_band, COUNT(*) rows FROM visit WHERE {REAL} AND {HAPPENED}"
        " AND price_band IS NOT NULL GROUP BY price_band ORDER BY price_band DESC",
    ),
    "cancellation_threshold": (
        "bookings and cancellations by price band",
        "SELECT price_band, COUNT(*) bookings,"
        " SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) cancelled"
        f" FROM visit WHERE {REAL} AND price_band IS NOT NULL"
        " GROUP BY price_band ORDER BY price_band",
    ),
    "revisit_ratio": (
        "completed visits per place",
        "SELECT place_name_raw, COUNT(*) visits FROM visit"
        f" WHERE {REAL} AND {HAPPENED} GROUP BY LOWER(TRIM(place_name_raw))"
        " ORDER BY visits DESC",
    ),
    "most_repeated": (
        "places visited more than once",
        "SELECT place_name_raw, COUNT(*) visits FROM visit"
        f" WHERE {REAL} AND {HAPPENED} GROUP BY LOWER(TRIM(place_name_raw))"
        " HAVING visits > 1 ORDER BY visits DESC",
    ),
    "cuisine_affinity": (
        "completed visits by place and cuisine (repeat count is the weight)",
        "SELECT cuisine, place_name_raw, COUNT(*) visits FROM visit"
        f" WHERE {REAL} AND {HAPPENED} AND cuisine IS NOT NULL"
        " GROUP BY LOWER(TRIM(place_name_raw)), cuisine ORDER BY visits DESC",
    ),
    "cuisine_aversion": (
        "every completed visit carrying a cuisine tag, oldest first",
        "SELECT scheduled_at, cuisine, place_name_raw, city FROM visit"
        f" WHERE {REAL} AND {HAPPENED} AND cuisine IS NOT NULL ORDER BY scheduled_at",
    ),
    "booking_lead_time_median_days": (
        "days between booking and going",
        "SELECT place_name_raw, booked_at, scheduled_at,"
        " CAST(julianday(scheduled_at) - julianday(booked_at) AS INTEGER) lead_days"
        f" FROM visit WHERE {REAL} AND booked_at IS NOT NULL ORDER BY lead_days",
    ),
    "seat_preference": (
        "seats on completed visits, solo reservations first",
        "SELECT seat, party_size, place_name_raw, scheduled_at FROM visit"
        f" WHERE {REAL} AND {HAPPENED} AND seat IS NOT NULL"
        " ORDER BY party_size, scheduled_at",
    ),
    "pace": (
        "completed visits per calendar day",
        "SELECT date(scheduled_at) day, COUNT(*) stops FROM visit"
        f" WHERE {REAL} AND {HAPPENED} GROUP BY day ORDER BY stops DESC, day",
    ),
    "avoided_categories": (
        "every row by category, cancellations and saves called out",
        "SELECT COALESCE(category, 'uncategorized') category, COUNT(*) rows,"
        " SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) cancelled,"
        " SUM(intent_only) saved FROM visit GROUP BY category ORDER BY rows DESC",
    ),
    "aspiration_gap": (
        "saved places, and whether a completed visit matches the name",
        "SELECT s.place_name_raw saved, s.city, s.created_at saved_at,"
        " (SELECT COUNT(*) FROM visit v WHERE LOWER(TRIM(v.place_name_raw))"
        f"   = LOWER(TRIM(s.place_name_raw)) AND {REAL} AND {HAPPENED}) visits"
        " FROM visit s WHERE s.intent_only = 1 ORDER BY s.place_name_raw",
    ),
}


def _table(rows: list) -> str:
    if not rows:
        return "  (no rows)"
    cols = list(rows[0].keys())
    widths = [
        max(len(c), max(len(str(r[c])) for r in rows)) for c in cols
    ]
    head = "  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    rule = "  " + "  ".join("-" * w for w in widths)
    body = [
        "  " + "  ".join(str(r[c]).ljust(w) for c, w in zip(cols, widths)) for r in rows
    ]
    return "\n".join([head, rule, *body])


def explain(key: str) -> str:
    """Print the rows behind one metric. Settles a 3 AM argument in ten seconds."""
    if key not in _EXPLAIN:
        return f"unknown metric: {key}\n\nknown metrics:\n  " + "\n  ".join(sorted(_EXPLAIN))

    headline, sql = _EXPLAIN[key]
    lines = [f"{key} — {headline}"]

    profile = load_profile()
    if profile is not None:
        value = profile.get(key)
        evidence = (profile.get("evidence") or {}).get(key)
        lines.append(f"  value: {contracts.dumps(value)}")
        if evidence:
            of = "" if evidence.get("of") is None else f" of {evidence['of']}"
            lines.append(f"  evidence: {evidence['n']}{of} — {evidence.get('note', '')}")
    else:
        lines.append("  (no profile built yet — run `python -m palate profile.build`)")

    lines.append("")
    lines.append(_table(db.rows(sql)))
    return "\n".join(lines)
