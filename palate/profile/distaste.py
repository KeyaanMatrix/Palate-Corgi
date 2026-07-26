"""Revealed aversion. OWNER B. See docs/trd-b-profile.md.

This file is the technical claim (PRD section 1): every recommender models
preference, none model revealed distaste. Guard every metric with a minimum n —
reporting noise as insight is worse than reporting nothing.
"""

MIN_N_THRESHOLD = 3   # cancellation threshold
MIN_N_AVERSION = 2    # cuisine aversion


def cancellation_threshold() -> tuple[int | None, dict]:
    """Lowest price_band where cancel rate > 0.5.

    Evidence MUST carry 'k of n at band B'. The line is "You cancel above
    $180/head. Four for four." A threshold with no count is worthless.
    Return None when there is no such band. Never fabricate one.
    """
    raise NotImplementedError


def cuisine_aversion(min_alternatives: int = 3) -> tuple[list[str], dict]:
    """Tried once, never returned, with >= min_alternatives options available.

    The alternatives guard is what stops 'you hate Ethiopian' from meaning
    'you went once, in 2024'.
    """
    raise NotImplementedError


def avoided_categories() -> tuple[list[str], dict]:
    """Booked-then-cancelled or saved-never-visited, well above baseline."""
    raise NotImplementedError


def aspiration_gap() -> tuple[list[dict], dict]:
    """intent_only rows with no matching confirmed visit.

    "You saved 14 places to this list. You went to two." Biggest emotional hit
    in the demo, and it exists only because Merge is in the stack.
    """
    raise NotImplementedError
