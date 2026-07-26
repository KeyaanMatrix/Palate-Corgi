"""The 'because'. OWNER D. Routed through Merge Gateway.

Bad:  Recommended because you like Italian food.
Good: You've been to Cotogna four times and always at the counter. This is the
      one counter-service place in Lisbon that runs the same way — booked
      Wednesday 8:45, which is your slot.
"""

from __future__ import annotations

import json

from palate import config

PROMPT_RULES = """\
Explain this recommendation by referencing a SPECIFIC behavior from the user's
history: a named place they went to repeatedly, a count, a time slot, a
cancellation. Never use genre labels — "because you like Italian food" is a
failure. Two sentences maximum. No preamble.
"""


def write_because(stop: dict, profile: dict, evidence_rows: list[dict]) -> str:
    """Cache by (stop_id, profile_version) — a swap must not regenerate the day."""
    cache_key = (str(stop.get("id")), str(profile.get("computed_at") or "unversioned"))
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    fallback = _fallback(stop, profile, evidence_rows)
    has_model_route = bool(
        (config.MERGE_GATEWAY_BASE_URL and config.MERGE_GATEWAY_API_KEY)
        or config.ANTHROPIC_API_KEY
    )
    if not has_model_route:
        _CACHE[cache_key] = fallback
        return fallback

    facts = {
        "stop": {
            "name": stop.get("name"),
            "category": stop.get("category"),
            "time": stop.get("time"),
            "price_band": stop.get("price_band"),
            "cuisine": stop.get("cuisine") or [],
            "is_stretch": bool(stop.get("is_stretch")),
        },
        "profile": {
            "peak_dining_hour": profile.get("peak_dining_hour"),
            "price_ceiling": profile.get("price_ceiling"),
            "seat_preference": profile.get("seat_preference"),
        },
        "behaviors": evidence_rows[:6],
    }
    prompt = (
        f"{PROMPT_RULES}\nUse only these facts. Include the exact name and visit count"
        " of one behavior when available. Do not claim an attribute of the new venue"
        " unless it appears in stop.cuisine/category/price_band.\n"
        f"{json.dumps(facts, ensure_ascii=False, sort_keys=True)}"
    )
    try:
        from palate import llm

        generated = llm.complete_text(
            prompt, purpose="rationale", max_tokens=220
        ).strip()
    except Exception:
        generated = ""

    anchors = [
        (str(row.get("name") or ""), str(row.get("visits") or ""))
        for row in evidence_rows
        if row.get("name") and row.get("visits")
    ]
    valid = (
        generated
        and len(generated) <= 420
        and generated.count(".") <= 3
        and any(name in generated and visits in generated for name, visits in anchors)
    )
    result = generated if valid else fallback
    _CACHE[cache_key] = result
    return result


_CACHE: dict[tuple[str, str], str] = {}


def _fallback(stop: dict, profile: dict, evidence_rows: list[dict]) -> str:
    anchor = next(
        (row for row in evidence_rows if row.get("name") and row.get("visits")),
        None,
    )
    peak = profile.get("peak_dining_hour")
    ceiling = profile.get("price_ceiling")
    band = stop.get("price_band")
    cuisines = stop.get("cuisine") or []
    affinity = {
        str(key).casefold(): value
        for key, value in (profile.get("cuisine_affinity") or {}).items()
    }

    specifics: list[str] = []
    matching = next(
        (
            str(cuisine).casefold()
            for cuisine in cuisines
            if str(cuisine).casefold() in affinity
        ),
        None,
    )
    if matching:
        specifics.append(f"{matching} appears in your repeat-weighted dining history")
    if band is not None and ceiling is not None and int(band) <= int(ceiling):
        specifics.append(f"price band {band} stays inside your ceiling of {ceiling}")
    if peak is not None and str(stop.get("time") or "").startswith(f"{int(peak):02d}:"):
        specifics.append(f"{stop.get('time')} is your usual dining window")
    if not specifics:
        specifics.append(
            f"the {stop.get('time') or 'planned'} slot follows your observed pace"
        )

    lead = ""
    if anchor:
        count = int(anchor["visits"])
        lead = f"You went back to {anchor['name']} {count} time{'s' if count != 1 else ''}. "
    else:
        evidence = (profile.get("evidence") or {}).get("peak_dining_hour") or {}
        if (
            peak is not None
            and evidence.get("n") is not None
            and evidence.get("of") is not None
        ):
            lead = (
                f"{evidence['n']} of {evidence['of']} dining bookings started in your"
                f" {peak}:00 hour. "
            )

    detail = specifics[0].capitalize()
    if stop.get("is_stretch"):
        strongest = max(affinity, key=affinity.get) if affinity else None
        if strongest:
            detail = (
                "This is the itinerary's one deliberate stretch; it moves beyond"
                f" your strongest {strongest} pattern while {specifics[-1]}"
            )
        else:
            detail = f"This is the itinerary's one deliberate stretch; {specifics[-1]}"
    return f"{lead}{detail}.".strip()
