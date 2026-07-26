"""Preference metrics. OWNER B. See docs/trd-b-profile.md.

Pure SQL + stdlib statistics. No pandas, no model.

Every function returns (value, evidence) where evidence is the kwargs for
contracts.Evidence.add(). A number without a row count behind it must never
reach the stage (PRD 5.4), so the return type makes the count mandatory rather
than optional.

Vocabulary used throughout:
  REAL      rows describing a real scheduled thing — excludes Notion saves,
            which carry intent_only=1 and no scheduled_at
  HAPPENED  things the user actually did: confirmed/modified/attended, never
            cancelled. Cancellations are NOT deleted; distaste.py needs them.
"""

import json
from collections import Counter

from palate import config, db

REAL = "intent_only = 0 AND scheduled_at IS NOT NULL"
HAPPENED = "status IN ('confirmed', 'modified', 'attended_unbooked')"
DINING = "category IN ('restaurant', 'bar')"

DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile. Deliberately not interpolated — n is small
    enough that interpolation would imply precision the data doesn't have."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[int(round(p * (len(ordered) - 1)))]


def _mode(values: list) -> tuple[object | None, int]:
    if not values:
        return None, 0
    value, count = Counter(values).most_common(1)[0]
    return value, count


def _hours(extra: str = "") -> list[int]:
    sql = (
        "SELECT CAST(strftime('%H', scheduled_at) AS INTEGER) h FROM visit"
        f" WHERE {REAL} AND {HAPPENED}"
    )
    if extra:
        sql += f" AND {extra}"
    return [r["h"] for r in db.rows(sql) if r["h"] is not None]


# --------------------------------------------------------------------- metrics


def home_city() -> tuple[str | None, dict]:
    """Modal city. Everything else is is_travel."""
    cities = [r["city"] for r in db.rows(f"SELECT city FROM visit WHERE {REAL} AND city IS NOT NULL")]
    city, count = _mode(cities)
    if not city:
        return config.HOME_CITY, {"n": 0, "of": 0, "note": "no city data; fell back to HOME_CITY"}
    return city, {"n": count, "of": len(cities), "note": f"visits in {city}"}


def earliest_activity_hour() -> tuple[int | None, dict]:
    """The earliest hour they have ever actually gone through with.

    This is a FLOOR, not a typical value, because D uses it as a hard constraint
    ("nothing before this hour"). That rules out a percentile: p5 over a
    dinner-dominated distribution lands near dinner, which would forbid the
    planner from ever scheduling lunch. The minimum is also the honest basis for
    the demo line — "you have never once scheduled anything before 11am."

    Lodging is excluded: a hotel check-in time says nothing about when someone
    is willing to be awake and out.

    Evidence carries the support count, so a floor resting on a single row is
    visible rather than hidden. If that count is 1 and the hour looks freakish,
    that is a data problem to look at, not a number to read on stage.
    """
    hours = _hours("(category IS NULL OR category != 'lodging')")
    if not hours:
        return None, {"n": 0, "of": 0, "note": "no scheduled hours"}
    value = min(hours)
    support = sum(1 for h in hours if h <= value + 1)
    return value, {
        "n": support,
        "of": len(hours),
        "note": f"earliest of {len(hours)} completed visits started at {value}:00",
    }


def peak_dining_hour() -> tuple[int | None, dict]:
    """Mode of the scheduled hour across restaurants and bars."""
    hours = _hours(DINING)
    hour, count = _mode(hours)
    if hour is None:
        return None, {"n": 0, "of": 0, "note": "no dining rows"}
    return hour, {"n": count, "of": len(hours), "note": f"bookings starting in the {hour}:00 hour"}


def preferred_days() -> tuple[list[str], dict]:
    """Days holding more than 1.5x their uniform share."""
    dows = [
        int(r["d"])
        for r in db.rows(
            f"SELECT strftime('%w', scheduled_at) d FROM visit"
            f" WHERE {REAL} AND {HAPPENED} AND {DINING}"
        )
        if r["d"] is not None
    ]
    if not dows:
        return [], {"n": 0, "of": 0, "note": "no dining rows"}
    counts = Counter(dows)
    threshold = 1.5 * len(dows) / 7
    days = sorted((d for d, c in counts.items() if c >= threshold), key=lambda d: -counts[d])
    names = [DAY_NAMES[d] for d in days]
    covered = sum(counts[d] for d in days)
    return names, {
        "n": covered,
        "of": len(dows),
        "note": f"dining bookings on {' and '.join(names)}" if names else "no dominant day",
    }


def typical_party_size() -> tuple[int | None, dict]:
    """Mode. The evidence count IS the demo line: '23 of your last 30'."""
    sizes = [
        r["party_size"]
        for r in db.rows(f"SELECT party_size FROM visit WHERE {REAL} AND party_size IS NOT NULL")
    ]
    size, count = _mode(sizes)
    if size is None:
        return None, {"n": 0, "of": 0, "note": "no party sizes recorded"}
    return size, {"n": count, "of": len(sizes), "note": f"reservations for {size}"}


def price_ceiling() -> tuple[int | None, dict]:
    """Highest band they actually went through with."""
    band = db.scalar(
        f"SELECT MAX(price_band) FROM visit WHERE {REAL} AND {HAPPENED} AND price_band IS NOT NULL"
    )
    if band is None:
        return None, {"n": 0, "of": 0, "note": "no price bands"}
    at_band = db.scalar(
        f"SELECT COUNT(*) FROM visit WHERE {REAL} AND {HAPPENED} AND price_band = ?", (band,), 0
    )
    total = db.scalar(
        f"SELECT COUNT(*) FROM visit WHERE {REAL} AND {HAPPENED} AND price_band IS NOT NULL", (), 0
    )
    return band, {"n": at_band, "of": total, "note": f"completed visits at band {band}"}


def revisit_ratio() -> tuple[float, dict]:
    """Visits per distinct place. Above ~1.8 reads as 'you go back'."""
    total = db.scalar(f"SELECT COUNT(*) FROM visit WHERE {REAL} AND {HAPPENED}", (), 0)
    distinct = db.scalar(
        f"SELECT COUNT(DISTINCT LOWER(TRIM(place_name_raw))) FROM visit WHERE {REAL} AND {HAPPENED}",
        (),
        0,
    )
    if not distinct:
        return 0.0, {"n": 0, "of": 0, "note": "no visits"}
    return round(total / distinct, 2), {
        "n": total,
        "of": distinct,
        "note": f"{total} visits across {distinct} distinct places",
    }


def most_repeated(limit: int = 6) -> tuple[list[dict], dict]:
    """The places they keep going back to. Feeds the 'same six places, 41 times'
    line, and gives D concrete anchors to name in rationales."""
    rows = db.rows(
        f"SELECT place_name_raw AS name, COUNT(*) n FROM visit WHERE {REAL} AND {HAPPENED}"
        " GROUP BY LOWER(TRIM(place_name_raw)) HAVING n > 1 ORDER BY n DESC LIMIT ?",
        (limit,),
    )
    places = [{"name": r["name"], "visits": r["n"]} for r in rows]
    covered = sum(p["visits"] for p in places)
    total = db.scalar(f"SELECT COUNT(*) FROM visit WHERE {REAL} AND {HAPPENED}", (), 0)
    return places, {
        "n": covered,
        "of": total,
        "note": f"visits concentrated in {len(places)} repeat places",
    }


def novelty_appetite(revisit: float) -> str:
    """Derived from revisit_ratio, so it carries no evidence entry of its own."""
    if revisit >= 1.8:
        return "low"
    if revisit >= 1.3:
        return "medium"
    return "high"


def cuisine_affinity() -> tuple[dict[str, float], dict]:
    """Weighted by REPEAT count, not raw count (PRD 5.3).

    A repeat visit counts double: one visit is a trial, two is a preference.
    Normalized to sum to 1.0 so D can rank candidates against it directly.
    """
    rows = db.rows(
        "SELECT cuisine, LOWER(TRIM(place_name_raw)) place, COUNT(*) n FROM visit"
        f" WHERE {REAL} AND {HAPPENED} AND cuisine IS NOT NULL GROUP BY place, cuisine"
    )
    scores: Counter = Counter()
    visits = 0
    for r in rows:
        try:
            tags = json.loads(r["cuisine"]) or []
        except (json.JSONDecodeError, TypeError):
            continue
        repeats = max(0, r["n"] - 1)
        visits += r["n"]
        for tag in tags:
            scores[str(tag).lower()] += r["n"] + repeats

    total = sum(scores.values())
    if not total:
        return {}, {"n": 0, "of": 0, "note": "no cuisine tags"}
    affinity = {k: round(v / total, 3) for k, v in scores.most_common()}
    return affinity, {"n": visits, "of": visits, "note": f"{len(affinity)} cuisines, repeat-weighted"}


def booking_lead_time_median_days() -> tuple[int | None, dict]:
    """Median days between booking and going."""
    leads = [
        r["d"]
        for r in db.rows(
            "SELECT julianday(scheduled_at) - julianday(booked_at) d FROM visit"
            f" WHERE {REAL} AND booked_at IS NOT NULL"
        )
        if r["d"] is not None and r["d"] >= 0
    ]
    if not leads:
        return None, {"n": 0, "of": 0, "note": "no booked_at timestamps"}
    median = int(round(_percentile(leads, 0.5)))
    return median, {
        "n": len(leads),
        "of": len(leads),
        "note": f"bookings with a lead time; median {median} days ahead",
    }


def seat_preference() -> tuple[str | None, dict]:
    """Modal seat — but the strong version is scoped to solo reservations.

    'Every solo reservation in two years was a bar seat' is a sentence someone
    remembers. 'Usually sits at the bar' is not.
    """
    seats = [
        r["seat"]
        for r in db.rows(f"SELECT seat FROM visit WHERE {REAL} AND {HAPPENED} AND seat IS NOT NULL")
    ]
    seat, count = _mode(seats)
    if seat is None:
        return None, {"n": 0, "of": 0, "note": "no seat data"}

    solo = [
        r["seat"]
        for r in db.rows(
            f"SELECT seat FROM visit WHERE {REAL} AND {HAPPENED}"
            " AND party_size = 1 AND seat IS NOT NULL"
        )
    ]
    if len(solo) >= 2 and all(s == seat for s in solo):
        return seat, {
            "n": len(solo),
            "of": len(solo),
            "note": f"every one of {len(solo)} solo reservations was a {seat} seat",
        }
    return seat, {"n": count, "of": len(seats), "note": f"visits seated at the {seat}"}


def pace() -> tuple[float, dict]:
    """Stops per active day. Feeds D's density constraint."""
    row = db.one(
        "SELECT COUNT(*) total, COUNT(DISTINCT date(scheduled_at)) days FROM visit"
        f" WHERE {REAL} AND {HAPPENED}"
    )
    if not row or not row["days"]:
        return 0.0, {"n": 0, "of": 0, "note": "no active days"}
    return round(row["total"] / row["days"], 2), {
        "n": row["total"],
        "of": row["days"],
        "note": f"{row['total']} stops across {row['days']} active days",
    }
