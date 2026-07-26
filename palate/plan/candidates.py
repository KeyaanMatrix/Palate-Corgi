"""Candidate filtering and ranking. OWNER D.

Filter BEFORE ranking. Filtering after ranking gives you popular places that
violate the profile — which is the exact product we exist to reject.
"""


def filter_by_profile(candidates: list[dict], profile: dict) -> list[dict]:
    """Drop: above cancellation_threshold, cuisine_aversion, avoided_categories."""
    raise NotImplementedError


def rank(candidates: list[dict], profile: dict) -> list[dict]:
    """Score by cuisine_affinity, price fit, category fit.

    NOT by rating. Rating is the popularity engine (PRD section 1).
    """
    raise NotImplementedError
