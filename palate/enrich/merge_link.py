"""Merge Link. OWNER D. See docs/trd-d-gateway-plan.md step 4.

HARD GATE 7:50 PM: does Link authorize PERSONAL Google Drive / Notion accounts,
or workspace-only? Report the answer at the 9:30 checkpoint either way — B is
waiting on it before building the aspiration gap.
"""

from __future__ import annotations

from urllib.parse import quote

from palate import config


def exchange_link_token(public_token: str) -> str:
    """Link public token -> account token. Store it in .env."""
    if not config.MERGE_API_KEY:
        raise RuntimeError("MERGE_API_KEY is required")
    public_token = str(public_token or "").strip()
    if not public_token:
        raise ValueError("public_token is required")

    import httpx

    response = httpx.get(
        "https://api.merge.dev/api/integrations/account-token/"
        + quote(public_token, safe=""),
        headers={"Authorization": f"Bearer {config.MERGE_API_KEY}"},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    account_token = payload.get("account_token") if isinstance(payload, dict) else None
    if not account_token:
        raise RuntimeError("Merge returned no account_token")
    return str(account_token)
