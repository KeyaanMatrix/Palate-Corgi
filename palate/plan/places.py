"""Google Places. OWNER D. See docs/trd-d-gateway-plan.md.

CACHE EVERYTHING in place_cache. Places is the only network call in the demo
path, and venue wifi at 2 AM is unreliable. A cached city builds offline.
"""

from palate import config, db  # noqa: F401


def search(name: str, city: str) -> dict | None:
    """Text search, cached. A repeat query must never hit the network twice."""
    raise NotImplementedError


def discover(city: str, category: str, price_band: int | None = None,
             limit: int = 20) -> list[dict]:
    """Candidate pool: name, place_id, price_level, rating, user_ratings_total."""
    raise NotImplementedError


def most_reviewed(city: str, category: str = "restaurant") -> dict | None:
    """The obvious thing. This is the TARGET of the negative recommendation."""
    raise NotImplementedError
