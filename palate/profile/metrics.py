"""Preference metrics. OWNER B. See docs/trd-b-profile.md.

PURE SQL + stdlib statistics. No pandas, no model. Every function returns
(value, evidence_kwargs) so build.py can populate profile["evidence"] — a
number without a row count behind it must never reach the stage.
"""

from palate import db  # noqa: F401


def home_city() -> tuple[str | None, dict]:
    """Modal city. Everything else is is_travel."""
    raise NotImplementedError


def earliest_activity_hour() -> tuple[int | None, dict]:
    """p5 of scheduled hour. The 'nothing before 11am' line."""
    raise NotImplementedError


def peak_dining_hour() -> tuple[int | None, dict]:
    """Mode of scheduled hour, restaurants + bars only."""
    raise NotImplementedError


def preferred_days() -> tuple[list[str], dict]:
    """Days holding >1.5x their uniform share."""
    raise NotImplementedError


def typical_party_size() -> tuple[int | None, dict]:
    """Mode. Evidence is 'N of M reservations' — that count IS the demo line."""
    raise NotImplementedError


def price_ceiling() -> tuple[int | None, dict]:
    raise NotImplementedError


def revisit_ratio() -> tuple[float, dict]:
    """confirmed visits / distinct places. >1.8 reads as 'you go back'."""
    raise NotImplementedError


def novelty_appetite(revisit: float) -> str:
    """Derived from revisit_ratio; no evidence entry needed."""
    raise NotImplementedError


def cuisine_affinity() -> tuple[dict[str, float], dict]:
    """Weighted by REPEAT count, not raw count. One visit is not a preference."""
    raise NotImplementedError


def booking_lead_time_median_days() -> tuple[int | None, dict]:
    raise NotImplementedError


def seat_preference() -> tuple[str | None, dict]:
    """Strongest form is scoped: 'every solo reservation was a bar seat.'"""
    raise NotImplementedError


def pace() -> tuple[float, dict]:
    """Stops per active day. Feeds D's density constraint."""
    raise NotImplementedError
