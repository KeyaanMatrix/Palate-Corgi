"""Itinerary assembly. OWNER D. THE CONTRACT C BUILDS AGAINST (TRD 3.3).

Invariants C relies on — write the test that proves them:
  - swap_stop changes exactly one stop, preserves every other stop.id byte for
    byte, and refuses to touch locked=True.
  - replan rewrites only stops at/after from_iso, preserves every locked stop,
    keeps stop ids for anything it keeps.
  - Both are PURE: take an itinerary, return a new one. C owns persistence.
  - Exactly one stop has is_stretch=True. Exactly one negative_recommendation.
  - Nothing before profile["earliest_activity_hour"].

Never return an itinerary that fails contracts.validate_itinerary().
"""

from __future__ import annotations

import copy
import hashlib
import math
import secrets
from datetime import date, datetime, timedelta

from palate import contracts, db

from . import candidates as candidate_rules
from . import places, rationale


def _id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _profile_rows(profile: dict) -> list[dict]:
    rows = [
        {"name": item.get("name"), "visits": item.get("visits")}
        for item in (profile.get("most_repeated") or [])
        if isinstance(item, dict) and item.get("name") and item.get("visits")
    ]
    if rows:
        return rows
    try:
        return [
            {"name": row["name"], "visits": row["visits"]}
            for row in db.rows(
                "SELECT place_name_raw name, COUNT(*) visits FROM visit"
                " WHERE intent_only=0 AND status IN"
                " ('confirmed','modified','attended_unbooked')"
                " GROUP BY LOWER(TRIM(place_name_raw)) HAVING visits > 1"
                " ORDER BY visits DESC LIMIT 6"
            )
        ]
    except Exception:
        return []


def _slots(count: int, profile: dict) -> list[str]:
    floor = max(0, min(23, int(profile.get("earliest_activity_hour") or 11)))
    peak = max(floor, min(23, int(profile.get("peak_dining_hour") or 20)))
    if count <= 2:
        hours = [max(floor, 12), max(peak, min(23, floor + 5))]
    elif count == 3:
        hours = [floor, max(floor + 4, 15), max(peak, floor + 7)]
    else:
        hours = [
            floor,
            max(floor + 3, 14),
            max(peak, floor + 7),
            max(peak + 2, floor + 9),
        ]

    out: list[str] = []
    last = floor - 1
    for index, hour in enumerate(hours[:count]):
        hour = max(floor, min(23, hour), min(23, last + 1))
        minute = 45 if index == count - 1 and count <= 3 else 30
        out.append(f"{hour:02d}:{minute:02d}")
        last = hour
    return out


def _categories(count: int) -> list[str]:
    if count <= 2:
        return ["activity", "restaurant"]
    if count == 3:
        return ["restaurant", "activity", "restaurant"]
    return ["restaurant", "activity", "restaurant", "bar"]


def _stop_from(
    candidate: dict,
    *,
    itinerary_id: str,
    day_index: int,
    seq: int,
    time: str,
    stretch: bool,
    profile: dict,
    evidence_rows: list[dict],
) -> dict:
    stop = {
        "id": _id(
            "stop",
            itinerary_id,
            day_index,
            seq,
            candidate.get("place_id") or candidate["name"],
        ),
        "seq": seq,
        "name": candidate["name"],
        "category": candidate.get("category") or "activity",
        "time": time,
        "price_band": candidate.get("price_band"),
        "because": "",
        "is_stretch": stretch,
        "locked": False,
        "place_id": candidate.get("place_id"),
        "cuisine": list(candidate.get("cuisine") or []),
        "types": list(candidate.get("types") or []),
    }
    stop["because"] = rationale.write_because(stop, profile, evidence_rows)
    return stop


def _negative(city: str, profile: dict) -> dict:
    obvious = places.most_reviewed(city) or {
        "name": f"{city}'s most-reviewed restaurant",
        "category": "restaurant",
        "price_band": None,
        "cuisine": [],
    }
    ev = profile.get("evidence") or {}
    threshold = profile.get("cancellation_threshold")
    band = obvious.get("price_band")
    if threshold is not None and band is not None and int(band) >= int(threshold):
        counts = ev.get("cancellation_threshold") or {}
        why = (
            f"It is the most-reviewed restaurant in the candidate pool, but price band {band}"
            f" is where you cancelled {counts.get('n', 0)} of {counts.get('of', 0)} bookings."
        )
    elif set(obvious.get("cuisine") or []) & set(profile.get("cuisine_aversion") or []):
        cuisine = min(set(obvious["cuisine"]) & set(profile["cuisine_aversion"]))
        why = (
            f"It is the most-reviewed restaurant in the candidate pool, but {cuisine}"
            " is a tried-once, never-returned signal in your history."
        )
    else:
        repeat = ev.get("revisit_ratio") or {}
        why = (
            "It is the most-reviewed restaurant in the candidate pool. Popularity alone"
            f" does not explain your {repeat.get('n', 0)} visits across"
            f" {repeat.get('of', 0)} places."
        )
    return {"name": obvious["name"], "why": why}


def _clean_candidate(candidate: dict) -> dict:
    return {
        key: copy.deepcopy(value)
        for key, value in candidate.items()
        if key in {"name", "place_id", "category", "cuisine", "price_band", "types"}
    }


def build_itinerary(profile: dict, city: str, days: int = 3) -> dict:
    """discover -> filter_by_profile -> rank -> lay out -> stretch -> negative
    -> rationale -> validate."""
    profile = dict(profile or {})
    city = str(city or "").strip()
    if not city:
        raise ValueError("city is required")
    days = max(1, min(int(days), 7))
    pace = float(profile.get("pace") or 2.0)
    stops_per_day = max(2, min(4, int(math.floor(pace + 0.5))))
    avoided = {
        str(value).casefold() for value in (profile.get("avoided_categories") or [])
    }
    category_fallbacks = [
        value
        for value in ("restaurant", "activity", "bar", "event")
        if value not in avoided
    ]
    if not category_fallbacks:
        raise ValueError("profile avoids every plannable category")
    required_categories = [
        category if category not in avoided else category_fallbacks[0]
        for category in _categories(stops_per_day)
    ]
    evidence_rows = _profile_rows(profile)
    negative = _negative(city, profile)

    pools: dict[str, list[dict]] = {}
    all_ranked: list[dict] = []
    for category in sorted(set(required_categories)):
        discovered = places.discover(city, category, limit=20)
        safe = candidate_rules.filter_by_profile(discovered, profile)
        ranked = candidate_rules.rank(safe, profile)
        if not ranked:
            # Never re-introduce a candidate that an explicit aversion removed.
            # A neutral placeholder is honest about the cold-network fallback
            # and stays on the safe side of every known constraint.
            threshold = profile.get("cancellation_threshold")
            safe_band = min(int(profile.get("price_ceiling") or 2), 4)
            if isinstance(threshold, int):
                safe_band = min(safe_band, max(1, threshold - 1))
            ranked = candidate_rules.rank(
                [
                    {
                        "name": f"{city} · verified {category} needed",
                        "category": category,
                        "price_band": safe_band,
                        "cuisine": [],
                        "types": [category],
                        "place_id": None,
                    }
                ],
                profile,
            )
        ranked = [
            item for item in ranked if item.get("name") != negative.get("name")
        ] or ranked
        pools[category] = ranked
        all_ranked.extend(ranked)

    itinerary_id = f"itin_{secrets.token_hex(5)}"
    used: set[str] = set()
    day_payloads: list[dict] = []
    start = date.today() + timedelta(days=1)
    stretch_position = (0, stops_per_day - 1)

    for day_index in range(days):
        slots = _slots(stops_per_day, profile)
        stops: list[dict] = []
        for seq, (category, time) in enumerate(zip(required_categories, slots)):
            pool = pools.get(category) or all_ranked
            candidate = next(
                (
                    item
                    for item in pool
                    if str(item.get("place_id") or item.get("name")).casefold()
                    not in used
                ),
                None,
            )
            if candidate is None:
                threshold = profile.get("cancellation_threshold")
                safe_band = min(int(profile.get("price_ceiling") or 2), 4)
                if isinstance(threshold, int):
                    safe_band = min(safe_band, max(1, threshold - 1))
                candidate = {
                    "name": f"{city} · {category} option {day_index + 1}.{seq + 1}",
                    "category": category,
                    "price_band": safe_band,
                    "cuisine": [],
                    "types": [category],
                    "place_id": None,
                }
            used.add(str(candidate.get("place_id") or candidate["name"]).casefold())
            stops.append(
                _stop_from(
                    candidate,
                    itinerary_id=itinerary_id,
                    day_index=day_index,
                    seq=seq,
                    time=time,
                    stretch=(day_index, seq) == stretch_position,
                    profile=profile,
                    evidence_rows=evidence_rows,
                )
            )
        day_payloads.append(
            {"date": (start + timedelta(days=day_index)).isoformat(), "stops": stops}
        )

    selected_names = {stop["name"] for day in day_payloads for stop in day["stops"]}
    alternates = [
        _clean_candidate(item)
        for item in all_ranked
        if item.get("name") not in selected_names
        and item.get("name") != negative.get("name")
    ]
    for index, candidate in enumerate(alternates):
        prototype = _stop_from(
            candidate,
            itinerary_id=itinerary_id,
            day_index=99,
            seq=index,
            time="20:00",
            stretch=False,
            profile=profile,
            evidence_rows=evidence_rows,
        )
        candidate["because"] = prototype["because"]

    itinerary = {
        "id": itinerary_id,
        "city": city,
        "created_at": db.now(),
        "negative_recommendation": negative,
        "days": day_payloads,
        "_alternates": alternates,
        "_constraints": {
            "earliest_activity_hour": int(profile.get("earliest_activity_hour") or 0),
        },
    }
    problems = contracts.validate_itinerary(itinerary, profile)
    if problems:
        raise ValueError(f"invalid itinerary: {problems}")
    return itinerary


def swap_stop(itinerary: dict, stop_id: str, reason: str | None = None) -> dict:
    out = copy.deepcopy(itinerary)
    target: dict | None = None
    day_index = stop_index = -1
    for di, day in enumerate(out.get("days") or []):
        for si, stop in enumerate(day.get("stops") or []):
            if stop.get("id") == stop_id:
                target, day_index, stop_index = stop, di, si
                break
        if target is not None:
            break
    if target is None or target.get("locked"):
        return out

    used = {stop.get("name") for _, stop in contracts.iter_stops(out)}
    alternates = [
        item for item in (out.get("_alternates") or []) if item.get("name") not in used
    ]
    replacement = next(
        (item for item in alternates if item.get("category") == target.get("category")),
        alternates[0] if alternates else None,
    )
    if replacement is None:
        return out

    new_stop = {
        "id": _id(
            "stop", out.get("id"), stop_id, replacement.get("name"), reason or "swap"
        ),
        "seq": target.get("seq"),
        "name": replacement["name"],
        "category": replacement.get("category") or target.get("category"),
        "time": target.get("time"),
        "price_band": replacement.get("price_band"),
        "because": replacement.get("because") or target.get("because"),
        "is_stretch": bool(target.get("is_stretch")),
        "locked": False,
        "place_id": replacement.get("place_id"),
        "cuisine": list(replacement.get("cuisine") or []),
        "types": list(replacement.get("types") or []),
    }
    out["days"][day_index]["stops"][stop_index] = new_stop
    problems = contracts.validate_itinerary(out)
    if problems:
        raise ValueError(f"swap produced invalid itinerary: {problems}")
    return out


def replan(itinerary: dict, from_iso: str, state_text: str) -> dict:
    out = copy.deepcopy(itinerary)
    cutoff = str(from_iso or db.now())[:16]
    text = str(state_text or "").casefold()
    weather = any(word in text for word in ("rain", "storm", "pour"))
    tired = any(
        word in text for word in ("wrecked", "exhausted", "tired", "dead", "hungover")
    )
    late = any(word in text for word in ("late", "behind", "still at lunch"))
    closed = any(word in text for word in ("closed", "shut", "not open"))
    used = {stop.get("name") for _, stop in contracts.iter_stops(out)}
    alternates = [
        item for item in (out.get("_alternates") or []) if item.get("name") not in used
    ]
    closed_done = False

    for day_index, day in enumerate(out.get("days") or []):
        for stop_index, stop in enumerate(day.get("stops") or []):
            stamp = f"{day.get('date', '')}T{str(stop.get('time') or '00:00')[:5]}"
            if stamp < cutoff or stop.get("locked"):
                continue

            if closed and not closed_done:
                replacement = next(
                    (
                        item
                        for item in alternates
                        if item.get("category") == stop.get("category")
                    ),
                    alternates[0] if alternates else None,
                )
                if replacement:
                    out["days"][day_index]["stops"][stop_index] = {
                        **stop,
                        "id": _id("stop", stop["id"], replacement["name"], "closed"),
                        "name": replacement["name"],
                        "category": replacement.get("category") or stop.get("category"),
                        "price_band": replacement.get("price_band"),
                        "place_id": replacement.get("place_id"),
                        "cuisine": list(replacement.get("cuisine") or []),
                        "types": list(replacement.get("types") or []),
                        "because": "The original stop is closed. "
                        + str(replacement.get("because") or stop.get("because") or ""),
                    }
                    closed_done = True
                continue

            if weather and stop.get("category") in ("activity", "event"):
                indoor = next(
                    (
                        item
                        for item in alternates
                        if item.get("category") == "activity"
                        and {"museum", "art_gallery"} & set(item.get("types") or [])
                    ),
                    None,
                )
                if indoor:
                    out["days"][day_index]["stops"][stop_index] = {
                        **stop,
                        "id": _id("stop", stop["id"], indoor["name"], "weather"),
                        "name": indoor["name"],
                        "category": "activity",
                        "price_band": indoor.get("price_band"),
                        "place_id": indoor.get("place_id"),
                        "cuisine": list(indoor.get("cuisine") or []),
                        "types": list(indoor.get("types") or []),
                        "because": "Rain moves this stop indoors. "
                        + str(indoor.get("because") or stop.get("because") or ""),
                    }
                    used.add(indoor["name"])
                    alternates = [
                        item
                        for item in alternates
                        if item.get("name") != indoor["name"]
                    ]
                else:
                    stop["because"] = (
                        "Rain plan: keep this stop only if it is indoors. "
                        + str(stop.get("because") or "")
                    )
            elif weather:
                # A dining-heavy profile can legitimately produce no outdoor
                # activities (the seed profile explicitly avoids tours). Rain
                # still needs a visible, useful stage-safe result: keep the
                # chosen venue and time, but switch the future stop to an
                # indoor/direct-route operating plan.
                stop["because"] = (
                    "Rain plan: use indoor seating and the direct route; "
                    "the time stays put. "
                    + str(stop.get("because") or "")
                )
            elif tired:
                stop["because"] = (
                    "Lower-energy plan: keep the route slow and direct. "
                    + str(stop.get("because") or "")
                )
                stop["time"] = _shift(stop.get("time"), 60)
            elif late:
                stop["because"] = (
                    "Shifted later because you are running behind. "
                    + str(stop.get("because") or "")
                )
                stop["time"] = _shift(stop.get("time"), 75)

    problems = contracts.validate_itinerary(out)
    if problems:
        raise ValueError(f"replan produced invalid itinerary: {problems}")
    return out


def _shift(value: object, minutes: int) -> str:
    try:
        parsed = datetime.strptime(str(value), "%H:%M")
    except ValueError:
        return str(value or "")
    shifted = parsed + timedelta(minutes=minutes)
    latest = datetime.strptime("23:45", "%H:%M")
    if shifted > latest:
        shifted = latest
    return shifted.strftime("%H:%M")
