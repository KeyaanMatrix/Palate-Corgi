"""Inbound routing. OWNER C. See docs/trd-c-photon.md step 7.

Keyword-match BEFORE reaching for the model. The demo says "raining" out loud;
a keyword match cannot fail on stage, and a model call on venue wifi at 7:30 AM
can.
"""

from __future__ import annotations

import re

from palate import contracts, db
from palate.chat import format as fmt
from palate.chat import photon, session
from palate.chat.plan_api import build_itinerary, swap_stop
from palate.chat.plan_api import replan as plan_replan

STATE_PATTERNS = {
    "weather": ["raining", "rain", "storm", "pouring"],
    "energy": ["wrecked", "exhausted", "tired", "dead", "hungover"],
    "running": ["still at lunch", "running late", "behind"],
    "closed": ["closed", "shut", "not open"],
}

DECLINE = (
    "I only handle stops — tap 👎 to swap one, or tell me "
    "what changed (raining, running late, museum closed)."
)

_PLAN_RE = re.compile(r"^\s*plan\s+(.+?)\s*$", re.IGNORECASE)
_NUMBER_RE = re.compile(r"^\s*(\d+)\s*$")


def classify_state(text: str) -> str | None:
    """Keyword match FIRST. Deterministic beats clever on stage."""
    lowered = (text or "").casefold()
    for kind, words in STATE_PATTERNS.items():
        for word in words:
            if word.casefold() in lowered:
                return kind
    return None


def _load_profile() -> dict:
    try:
        from palate.profile.build import load_profile  # type: ignore

        profile = load_profile()
        if isinstance(profile, dict) and profile:
            return profile
    except Exception:
        pass
    return {
        "home_city": "San Francisco",
        "earliest_activity_hour": 11,
        "peak_dining_hour": 20,
        "seat_preference": "bar",
        "price_ceiling": 3,
    }


def _load_profile_lines() -> list[str]:
    try:
        from palate.profile.build import load_profile
        from palate.profile.copy import render_plain

        profile = load_profile()
        if isinstance(profile, dict) and profile:
            lines = render_plain(profile)
            if lines:
                return [str(x) for x in lines]
    except Exception:
        pass
    return []


def _day_index_for_stop(itin: dict, stop_id: str) -> int:
    for i, day in enumerate(itin.get("days") or []):
        for stop in day.get("stops") or []:
            if stop.get("id") == stop_id:
                return i
    return 0


def _find_stop(itin: dict, stop_id: str) -> dict | None:
    for _, stop in contracts.iter_stops(itin):
        if stop.get("id") == stop_id:
            return stop
    return None


def _stop_snapshot(itin: dict) -> dict[str, dict]:
    return {s["id"]: dict(s) for _, s in contracts.iter_stops(itin)}


def send_full_itinerary(phone: str, city: str, days: int = 3) -> list[str]:
    """Build, persist, and send profile + negative + one message per stop."""
    profile = _load_profile()
    itin = build_itinerary(profile, city, days=days)
    session.reset_message_map(phone)
    session.save_session(phone, itin)

    sent: list[str] = []
    lines = _load_profile_lines()
    if lines:
        text = fmt.format_profile(lines)
        mid = photon.send(phone, text)
        sent.append(mid)

    neg = itin.get("negative_recommendation")
    if neg:
        text = fmt.format_negative(neg)
        mid = photon.send(phone, text)
        sent.append(mid)

    for day_index, day in enumerate(itin.get("days") or []):
        for stop in day.get("stops") or []:
            text = fmt.format_stop(stop, day_index)
            mid = photon.send(phone, text)
            session.map_message(phone, mid, stop["id"])
            sent.append(mid)
    return sent


def _send_changed_stops(phone: str, before: dict, after: dict) -> list[str]:
    """Re-send stops that are new or whose content changed; remap message ids."""
    prev = _stop_snapshot(before)
    sent: list[str] = []
    for day_index, day in enumerate(after.get("days") or []):
        for stop in day.get("stops") or []:
            sid = stop["id"]
            old = prev.get(sid)
            changed = old is None or any(
                old.get(k) != stop.get(k)
                for k in ("name", "time", "because", "category", "price_band")
            )
            if not changed:
                continue
            text = fmt.format_stop(stop, day_index)
            mid = photon.send(phone, text)
            session.map_message(phone, mid, sid)
            sent.append(mid)
    return sent


def _swap_stop_and_send(phone: str, itin: dict, stop_id: str) -> list[str]:
    before = itin
    after = swap_stop(itin, stop_id, reason="tapback_down")
    session.save_session(phone, after)

    before_ids = {s["id"] for _, s in contracts.iter_stops(before)}
    replacement = None
    day_index = 0
    for di, day in enumerate(after.get("days") or []):
        for stop in day.get("stops") or []:
            if stop["id"] not in before_ids:
                replacement = stop
                day_index = di
                break
        if replacement:
            break
    if replacement is None:
        replacement = _find_stop(after, stop_id)
        if replacement:
            day_index = _day_index_for_stop(after, stop_id)

    if replacement and replacement["id"] != stop_id:
        text = fmt.format_stop(replacement, day_index)
        mid = photon.send(phone, text)
        session.map_message(phone, mid, replacement["id"])
    elif replacement:
        # Locked or no-op swap — nothing to send.
        before_stop = _find_stop(before, stop_id)
        if before_stop and any(
            before_stop.get(k) != replacement.get(k)
            for k in ("name", "time", "because")
        ):
            text = fmt.format_stop(replacement, day_index)
            mid = photon.send(phone, text)
            session.map_message(phone, mid, replacement["id"])
    return []


def handle_text(phone: str, text: str) -> list[str]:
    """Route: state -> replan | 'plan <city>' -> build | number -> swap | else DECLINE."""
    raw = (text or "").strip()
    if not raw:
        return [DECLINE]

    m = _PLAN_RE.match(raw)
    if m:
        city = m.group(1).strip()
        send_full_itinerary(phone, city)
        return []

    # Numbered swap fallback (1-based across the itinerary).
    nm = _NUMBER_RE.match(raw)
    if nm:
        n = int(nm.group(1))
        sess = session.get_session(phone)
        itin = sess.get("itinerary")
        if not itin:
            return [DECLINE]
        stops = [s for _, s in contracts.iter_stops(itin)]
        if n < 1 or n > len(stops):
            return [DECLINE]
        return _swap_stop_and_send(phone, itin, stops[n - 1]["id"])

    kind = classify_state(raw)
    if kind:
        sess = session.get_session(phone)
        itin = sess.get("itinerary")
        if not itin:
            return ["No itinerary yet — text plan <city> first."]
        before = itin
        after = plan_replan(itin, from_iso=db.now(), state_text=raw)
        session.save_session(phone, after)
        _send_changed_stops(phone, before, after)
        return []

    return [DECLINE]


def handle_tapback(phone: str, message_id: str, reaction: str) -> list[str]:
    """down -> plan.swap_stop, send the replacement as a NEW message, remap.
    up   -> mark the stop locked, no reply.
    """
    stop_id = session.stop_for_message(phone, message_id)
    if not stop_id:
        return []

    sess = session.get_session(phone)
    itin = sess.get("itinerary")
    if not itin:
        return []

    if reaction == "up":
        for _, stop in contracts.iter_stops(itin):
            if stop.get("id") == stop_id:
                stop["locked"] = True
                break
        session.save_session(phone, itin)
        return []

    if reaction != "down":
        return []

    return _swap_stop_and_send(phone, itin, stop_id)
