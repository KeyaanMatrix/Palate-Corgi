"""Candidate filtering and ranking. OWNER D.

Filter BEFORE ranking. Filtering after ranking gives you popular places that
violate the profile — which is the exact product we exist to reject.
"""

from __future__ import annotations

from typing import Any


def _price_band(candidate: dict) -> int | None:
    value = candidate.get("price_band", candidate.get("price_level"))
    if isinstance(value, int) and 1 <= value <= 4:
        return value
    return None


def _cuisines(candidate: dict) -> set[str]:
    raw: Any = candidate.get("cuisine", candidate.get("cuisines", []))
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return set()
    return {str(value).strip().casefold() for value in raw if str(value).strip()}


def filter_by_profile(candidates: list[dict], profile: dict) -> list[dict]:
    """Drop: above cancellation_threshold, cuisine_aversion, avoided_categories."""
    threshold = profile.get("cancellation_threshold")
    threshold = threshold if isinstance(threshold, int) else None
    aversions = {
        str(value).strip().casefold()
        for value in (profile.get("cuisine_aversion") or [])
        if str(value).strip()
    }
    avoided = {
        str(value).strip().casefold()
        for value in (profile.get("avoided_categories") or [])
        if str(value).strip()
    }

    filtered: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        if (
            not isinstance(candidate, dict)
            or not str(candidate.get("name") or "").strip()
        ):
            continue

        band = _price_band(candidate)
        # cancellation_threshold is the first band where cancellations become
        # dominant, so the threshold itself is already outside the safe range.
        if threshold is not None and band is not None and band >= threshold:
            continue
        if _cuisines(candidate) & aversions:
            continue
        category = str(candidate.get("category") or "").strip().casefold()
        if category and category in avoided:
            continue

        identity = (
            str(candidate.get("place_id") or candidate["name"]).strip().casefold()
        )
        if identity in seen:
            continue
        seen.add(identity)
        filtered.append(dict(candidate))
    return filtered


def rank(candidates: list[dict], profile: dict) -> list[dict]:
    """Score by cuisine_affinity, price fit, category fit.

    NOT by rating. Rating is the popularity engine (PRD section 1).
    """
    affinities = {
        str(key).strip().casefold(): float(value)
        for key, value in (profile.get("cuisine_affinity") or {}).items()
        if isinstance(value, (int, float))
    }
    ceiling = profile.get("price_ceiling")
    ceiling = ceiling if isinstance(ceiling, int) else None
    seat = str(profile.get("seat_preference") or "").casefold()

    ranked: list[dict] = []
    for position, candidate in enumerate(candidates):
        item = dict(candidate)
        cuisines = _cuisines(item)
        cuisine_score = max((affinities.get(tag, 0.0) for tag in cuisines), default=0.0)

        price_score = 0.0
        band = _price_band(item)
        if ceiling is not None and band is not None:
            if band <= ceiling:
                price_score = 0.24 - (abs(ceiling - band) * 0.035)
            else:
                price_score = -0.25 * (band - ceiling)

        types = {str(value).casefold() for value in (item.get("types") or [])}
        seat_score = (
            0.04
            if seat == "bar" and ("bar" in types or item.get("category") == "bar")
            else 0.0
        )

        # Source order is a deliberately tiny tie breaker. Ratings and review
        # counts are never consulted here.
        item["_score"] = round(
            cuisine_score * 2.0 + price_score + seat_score - position * 1e-6, 6
        )
        ranked.append(item)

    return sorted(
        ranked,
        key=lambda item: (
            -float(item["_score"]),
            str(item.get("name") or "").casefold(),
        ),
    )
