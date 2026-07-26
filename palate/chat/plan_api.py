"""Stable chat-facing import of the itinerary contract."""

from __future__ import annotations

from palate.plan.assemble import (
    build_itinerary as _build_itinerary,
)
from palate.plan.assemble import (
    replan as _replan,
)
from palate.plan.assemble import (
    swap_stop as _swap_stop,
)


def build_itinerary(profile: dict, city: str, days: int = 3) -> dict:
    return _build_itinerary(profile, city, days)


def swap_stop(itinerary: dict, stop_id: str, reason: str | None = None) -> dict:
    return _swap_stop(itinerary, stop_id, reason)


def replan(itinerary: dict, from_iso: str, state_text: str) -> dict:
    return _replan(itinerary, from_iso, state_text)
