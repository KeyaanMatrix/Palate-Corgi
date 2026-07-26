"""Merge Link. OWNER D. See docs/trd-d-gateway-plan.md step 4.

HARD GATE 7:50 PM: does Link authorize PERSONAL Google Drive / Notion accounts,
or workspace-only? Report the answer at the 9:30 checkpoint either way — B is
waiting on it before building the aspiration gap.
"""

from palate import config  # noqa: F401


def exchange_link_token(public_token: str) -> str:
    """Link public token -> account token. Store it in .env."""
    raise NotImplementedError
