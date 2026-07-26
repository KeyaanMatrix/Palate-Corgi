"""Hand-written §3.3 itinerary until Owner D's assemble.py lands.

C calls these through plan_api(); real assemble wins when importable.
"""

from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timedelta

from palate import db


def _stop(
    *,
    sid: str,
    seq: int,
    name: str,
    category: str,
    time: str,
    price_band: int,
    because: str,
    is_stretch: bool = False,
    locked: bool = False,
    place_id: str | None = None,
) -> dict:
    return {
        "id": sid,
        "seq": seq,
        "name": name,
        "category": category,
        "time": time,
        "price_band": price_band,
        "because": because,
        "is_stretch": is_stretch,
        "locked": locked,
        "place_id": place_id,
    }


def build_itinerary(profile: dict, city: str, days: int = 3) -> dict:
    days = max(1, min(int(days), 5))
    city = (city or "Lisbon").strip() or "Lisbon"
    start = datetime.now().date() + timedelta(days=1)
    itin_id = "itin_" + hashlib.sha256(f"{city}|{db.now()}".encode()).hexdigest()[:10]

    seat = (profile or {}).get("seat_preference") or "bar"
    day_list = []
    for d in range(days):
        date = (start + timedelta(days=d)).isoformat()
        stretch = d == 0
        day_list.append(
            {
                "date": date,
                "stops": [
                    _stop(
                        sid=f"stop_{itin_id}_{d}_0",
                        seq=0,
                        name="Pastelaria Aloma" if d == 0 else f"{city} Market Hall",
                        category="restaurant",
                        time="11:30",
                        price_band=1,
                        because=(
                            f"Your earliest activity hour is "
                            f"{(profile or {}).get('earliest_activity_hour', 11)}:00 — "
                            "this is the soft open that matches it."
                        ),
                    ),
                    _stop(
                        sid=f"stop_{itin_id}_{d}_1",
                        seq=1,
                        name="Taberna Sal Grosso" if d == 0 else f"Corner Bar {city}",
                        category="restaurant",
                        time="20:45",
                        price_band=2,
                        because=(
                            f"You've booked counter seats before; seat preference is "
                            f"{seat}. This runs the same way."
                        ),
                        is_stretch=stretch,
                    ),
                    _stop(
                        sid=f"stop_{itin_id}_{d}_2",
                        seq=2,
                        name="Pensão Amor" if d == 0 else f"{city} Nightcap",
                        category="bar",
                        time="22:30",
                        price_band=2,
                        because="Late stop after dinner — same pacing as your home weeks.",
                    ),
                ],
            }
        )

    return {
        "id": itin_id,
        "city": city,
        "created_at": db.now(),
        "negative_recommendation": {
            "name": f"Time Out Market {city}",
            "why": (
                "High stranger-rating, zero overlap with your revisit pattern — "
                "skip the food hall."
            ),
        },
        "days": day_list,
    }


_SWAP_POOL = [
    ("Cervejaria Ramiro", "restaurant", "You've done seafood counters at home; this is the local equivalent."),
    ("A Cevicheria", "restaurant", "Price band 2, counter energy — fits the ceiling without the stretch."),
    ("Foxtrot", "bar", "Small room, no tourist queue signal — a quieter swap."),
    ("Solar dos Presuntos", "restaurant", "Classic room, not a stranger-list pick — safer mid-swap."),
]


def swap_stop(itinerary: dict, stop_id: str, reason: str | None = None) -> dict:
    out = copy.deepcopy(itinerary)
    target = None
    day_idx = None
    stop_idx = None
    for di, day in enumerate(out.get("days") or []):
        for si, stop in enumerate(day.get("stops") or []):
            if stop.get("id") == stop_id:
                target = stop
                day_idx = di
                stop_idx = si
                break
        if target is not None:
            break
    if target is None:
        return out
    if target.get("locked"):
        return out

    used = {s.get("name") for _, s in _iter(out)}
    pick = None
    for name, cat, because in _SWAP_POOL:
        if name not in used:
            pick = (name, cat, because)
            break
    if pick is None:
        pick = ("Bairro Alto Hide", "bar", "Fresh swap — not on the prior list.")

    name, cat, because = pick
    new_id = "stop_" + hashlib.sha256(f"{stop_id}|{name}|{reason}".encode()).hexdigest()[:10]
    out["days"][day_idx]["stops"][stop_idx] = {
        **target,
        "id": new_id,
        "name": name,
        "category": cat,
        "because": because,
        "is_stretch": False,
        "locked": False,
    }
    # Preserve exactly one stretch across the itinerary.
    stretches = [s for _, s in _iter(out) if s.get("is_stretch")]
    if not stretches:
        # Prefer an unlocked non-swapped dinner-ish stop.
        for _, s in _iter(out):
            if not s.get("locked") and s["id"] != new_id:
                s["is_stretch"] = True
                break
    return out


def replan(itinerary: dict, from_iso: str, state_text: str) -> dict:
    out = copy.deepcopy(itinerary)
    from_iso = from_iso or db.now()
    # Replan only stops at/after from_iso wall-clock on their day date + time.
    for day in out.get("days") or []:
        date = day.get("date") or ""
        for stop in day.get("stops") or []:
            if stop.get("locked"):
                continue
            stamp = f"{date}T{stop.get('time') or '00:00'}"
            if stamp < from_iso:
                continue
            # Weather / energy: bump indoor or earlier; closed: rename.
            text = (state_text or "").lower()
            if any(w in text for w in ("rain", "storm", "pour")):
                stop["because"] = (
                    "Re-planned indoors — rain changes the afternoon. "
                    + str(stop.get("because") or "")
                )
                if stop.get("category") == "activity":
                    stop["name"] = f"Indoor: {stop['name']}"
                    stop["category"] = "event"
            elif any(w in text for w in ("wrecked", "exhausted", "tired", "dead", "hungover")):
                # Drop pace: push later stops later / soften
                h, m = (stop.get("time") or "12:00").split(":")[:2]
                hour = min(23, int(h) + 1)
                stop["time"] = f"{hour}:{m}"
                stop["because"] = "Lower energy — one fewer climb between stops. " + str(
                    stop.get("because") or ""
                )
            elif any(w in text for w in ("late", "behind", "still at lunch")):
                h, m = (stop.get("time") or "12:00").split(":")[:2]
                hour = min(23, int(h) + 1)
                stop["time"] = f"{hour}:{int(m):02d}" if m.isdigit() else f"{hour}:{m}"
                stop["because"] = "Shifted later — you're running behind. " + str(
                    stop.get("because") or ""
                )
            elif any(w in text for w in ("closed", "shut", "not open")):
                stop["id"] = "stop_" + hashlib.sha256(
                    f"{stop['id']}|closed|{state_text}".encode()
                ).hexdigest()[:10]
                stop["name"] = f"Alt: {stop['name']}"
                stop["because"] = "Original was closed — swapped in place. " + str(
                    stop.get("because") or ""
                )
    return out


def _iter(itinerary: dict):
    for day in itinerary.get("days") or []:
        for stop in day.get("stops") or []:
            yield day, stop
