"""Notion -> intent rows. OWNER D. Merge Unified API, Knowledge Base category.

Highest value per line of code you will write tonight: this produces the
aspiration gap. "You saved 14 places to this list. You went to two."
B computes the gap; you just have to land the rows.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from palate import config, contracts, db

_BASE = "https://api.merge.dev/api/knowledgebase/v1"
_LIST_WORDS = (
    "restaurant",
    "restaurants",
    "dining",
    "places to eat",
    "food",
    "eats",
    "cafes",
    "cafés",
    "bars",
)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)]|\[[ xX]\])\s+(.+?)\s*$")


def _headers() -> dict[str, str]:
    if not config.MERGE_API_KEY or not config.MERGE_ACCOUNT_TOKEN:
        raise RuntimeError("MERGE_API_KEY and MERGE_ACCOUNT_TOKEN are required")
    return {
        "Authorization": f"Bearer {config.MERGE_API_KEY}",
        "X-Account-Token": config.MERGE_ACCOUNT_TOKEN,
        "Accept": "application/json",
    }


def _flatten(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            if key not in {
                "remote_data",
                "integration_params",
                "linked_account_params",
            }:
                yield from _flatten(child)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten(child)


def _items(article: dict) -> list[str]:
    """Extract list-item-shaped place names without asking a model to guess."""
    title = str(article.get("title") or article.get("name") or "").strip()
    content_values = [
        article.get("content"),
        article.get("body"),
        article.get("text"),
        article.get("description"),
    ]
    text = "\n".join(part for value in content_values for part in _flatten(value))
    title_is_list = any(word in title.casefold() for word in _LIST_WORDS)
    found: list[str] = []
    for line in text.splitlines():
        match = _BULLET.match(line)
        if not match:
            continue
        item = re.split(r"\s+[—–|-]\s+|https?://", match.group(1), maxsplit=1)[0]
        item = re.sub(r"\s+", " ", item).strip(" \t.,;:")
        if 2 <= len(item) <= 100:
            found.append(item)

    # Five entries is the precision gate from the TRD. A restaurant-shaped
    # title is required because arbitrary Notion checklists are not visits.
    if not title_is_list or len(found) < 5:
        return []
    return list(dict.fromkeys(found))


def _pages() -> Iterable[dict]:
    import httpx

    cursor = None
    with httpx.Client(headers=_headers(), timeout=30.0) as client:
        while True:
            params = {"page_size": 100}
            if cursor:
                params["cursor"] = cursor
            response = client.get(f"{_BASE}/articles", params=params)
            response.raise_for_status()
            payload = response.json()
            for article in payload.get("results", []):
                if isinstance(article, dict):
                    yield article
            cursor = payload.get("next")
            if not cursor:
                return


def sync() -> int:
    """Restaurant-list-shaped pages -> visit rows with intent_only=1 and no
    scheduled_at. Treat a page as a list if it has >=5 restaurant-shaped items."""
    written = 0
    for article in _pages():
        article_id = str(article.get("id") or article.get("remote_id") or "")
        if not article_id:
            continue
        created_at = str(
            article.get("modified_at") or article.get("created_at") or db.now()
        )[:16]
        for index, name in enumerate(_items(article)):
            source_ref = f"{article_id}:{index}:{name.casefold()}"
            visit = {
                "id": contracts.visit_id("notion", source_ref, name, ""),
                "source": "notion",
                "source_ref": source_ref,
                "vendor": None,
                "place_name_raw": name,
                "place_id": None,
                "city": None,
                "category": "restaurant",
                "cuisine": None,
                "price_band": None,
                "party_size": None,
                "scheduled_at": None,
                "booked_at": None,
                "status": "confirmed",
                "cancelled_at": None,
                "is_travel": 0,
                "intent_only": 1,
                "seat": None,
                "raw_total_cents": None,
                "created_at": created_at,
            }
            if contracts.valid_visit(visit):
                db.upsert_visit(visit)
                written += 1
    return written
