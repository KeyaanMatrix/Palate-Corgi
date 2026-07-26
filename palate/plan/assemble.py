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

from palate import contracts  # noqa: F401


def build_itinerary(profile: dict, city: str, days: int = 3) -> dict:
    """discover -> filter_by_profile -> rank -> lay out -> stretch -> negative
    -> rationale -> validate."""
    raise NotImplementedError


def swap_stop(itinerary: dict, stop_id: str, reason: str | None = None) -> dict:
    raise NotImplementedError


def replan(itinerary: dict, from_iso: str, state_text: str) -> dict:
    raise NotImplementedError
