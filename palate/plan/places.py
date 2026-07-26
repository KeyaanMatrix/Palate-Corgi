"""Google Places. OWNER D. See docs/trd-d-gateway-plan.md.

CACHE EVERYTHING in place_cache. Places is the only network call in the demo
path, and venue wifi at 2 AM is unreliable. A cached city builds offline.
"""

from __future__ import annotations

import json
import re
from typing import Any

from palate import config, db

_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
_FIELDS = (
    "places.id,places.displayName,places.formattedAddress,places.primaryType,"
    "places.types,places.priceLevel,places.rating,places.userRatingCount,places.location"
)
_MISSING = object()

_PRICE = {
    "PRICE_LEVEL_FREE": 1,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

_CATEGORY_TYPES = {
    "restaurant": "restaurant",
    "bar": "bar",
    "event": "event_venue",
    "lodging": "hotel",
    "activity": "tourist_attraction",
}

# This pool is the deterministic venue-wifi fallback for the city named in the
# product spec. Live plans use Google Places whenever a key is configured.
_LISBON = [
    {
        "name": "Pastéis de Belém",
        "category": "restaurant",
        "cuisine": ["portuguese", "bakery"],
        "price_band": 1,
        "types": ["cafe", "bakery"],
        "user_ratings_total": 62000,
    },
    {
        "name": "O Velho Eurico",
        "category": "restaurant",
        "cuisine": ["portuguese"],
        "price_band": 2,
        "types": ["restaurant"],
        "user_ratings_total": 5200,
    },
    {
        "name": "Taberna Sal Grosso",
        "category": "restaurant",
        "cuisine": ["portuguese"],
        "price_band": 2,
        "types": ["restaurant"],
        "user_ratings_total": 6800,
    },
    {
        "name": "Cervejaria Ramiro",
        "category": "restaurant",
        "cuisine": ["seafood", "portuguese"],
        "price_band": 3,
        "types": ["seafood_restaurant", "restaurant"],
        "user_ratings_total": 19000,
    },
    {
        "name": "Prado",
        "category": "restaurant",
        "cuisine": ["portuguese"],
        "price_band": 3,
        "types": ["restaurant"],
        "user_ratings_total": 2800,
    },
    {
        "name": "A Cevicheria",
        "category": "restaurant",
        "cuisine": ["peruvian", "seafood"],
        "price_band": 3,
        "types": ["restaurant"],
        "user_ratings_total": 15000,
    },
    {
        "name": "Red Frog",
        "category": "bar",
        "cuisine": ["cocktails"],
        "price_band": 3,
        "types": ["bar"],
        "user_ratings_total": 2400,
    },
    {
        "name": "Foxtrot",
        "category": "bar",
        "cuisine": ["cocktails"],
        "price_band": 2,
        "types": ["bar"],
        "user_ratings_total": 2100,
    },
    {
        "name": "Museu Nacional do Azulejo",
        "category": "activity",
        "cuisine": [],
        "price_band": 1,
        "types": ["museum", "tourist_attraction"],
        "user_ratings_total": 16000,
    },
    {
        "name": "Museu Calouste Gulbenkian",
        "category": "activity",
        "cuisine": [],
        "price_band": 2,
        "types": ["museum", "tourist_attraction"],
        "user_ratings_total": 17000,
    },
    {
        "name": "MAAT",
        "category": "activity",
        "cuisine": [],
        "price_band": 2,
        "types": ["museum", "tourist_attraction"],
        "user_ratings_total": 14000,
    },
    {
        "name": "Feira da Ladra",
        "category": "activity",
        "cuisine": [],
        "price_band": 1,
        "types": ["market", "tourist_attraction"],
        "user_ratings_total": 12000,
    },
]


def _key(*parts: object) -> str:
    return "|".join(re.sub(r"\s+", " ", str(part).strip().casefold()) for part in parts)


def _cache_get(key: str) -> Any:
    db.migrate()
    row = db.one("SELECT payload FROM place_cache WHERE query = ?", (key,))
    if row is None:
        return _MISSING
    try:
        return json.loads(row["payload"]).get("value")
    except (json.JSONDecodeError, AttributeError):
        return _MISSING


def _cache_put(key: str, value: Any) -> None:
    db.execute(
        "INSERT INTO place_cache (query, payload, fetched_at) VALUES (?, ?, ?)"
        " ON CONFLICT(query) DO UPDATE SET payload=excluded.payload,"
        " fetched_at=excluded.fetched_at",
        (key, json.dumps({"value": value}, ensure_ascii=False), db.now()),
    )


def _request(url: str, body: dict) -> dict | None:
    if not config.GOOGLE_PLACES_API_KEY:
        return None
    try:
        import httpx

        response = httpx.post(
            url,
            json=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY,
                "X-Goog-FieldMask": _FIELDS,
            },
            timeout=12.0,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception as exc:  # venue-wifi fallback is a product requirement
        print(
            f"places: live request unavailable ({exc}); using cached/offline candidates"
        )
        return None


def _category(types: list[str], primary: str = "") -> str:
    values = {str(value).casefold() for value in [primary, *types]}
    if "bar" in values or "night_club" in values:
        return "bar"
    if "lodging" in values or "hotel" in values:
        return "lodging"
    if any("restaurant" in value for value in values) or values & {"cafe", "bakery"}:
        return "restaurant"
    if values & {"event_venue", "concert_hall", "performing_arts_theater"}:
        return "event"
    return "activity"


def _normalize(place: dict) -> dict | None:
    display = place.get("displayName")
    name = display.get("text") if isinstance(display, dict) else display
    if not name:
        return None
    types = [str(value) for value in (place.get("types") or [])]
    primary = str(place.get("primaryType") or "")
    cuisines = []
    for value in [primary, *types]:
        if value.endswith("_restaurant") and value != "restaurant":
            cuisines.append(value.removesuffix("_restaurant").replace("_", " "))
    location = place.get("location") if isinstance(place.get("location"), dict) else {}
    return {
        "name": str(name),
        "place_id": place.get("id"),
        "category": _category(types, primary),
        "cuisine": sorted(set(cuisines)),
        "price_band": _PRICE.get(str(place.get("priceLevel") or "")),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("userRatingCount") or 0,
        "types": types,
        "lat": location.get("latitude"),
        "lng": location.get("longitude"),
        "address": place.get("formattedAddress"),
    }


def _fallback(city: str, category: str, limit: int) -> list[dict]:
    if city.strip().casefold() == "lisbon":
        found = [dict(item) for item in _LISBON if item["category"] == category]
    else:
        labels = {
            "restaurant": (
                "Independent counter",
                "Neighborhood dining room",
                "Local kitchen",
                "Market table",
            ),
            "bar": (
                "Neighborhood bar",
                "Small cocktail room",
                "Late local bar",
                "Quiet nightcap",
            ),
            "activity": (
                "City museum",
                "Independent gallery",
                "Local market",
                "Historic walk",
            ),
            "event": (
                "Local music room",
                "Small theatre",
                "Evening performance",
                "Community venue",
            ),
            "lodging": (
                "Independent hotel",
                "Neighborhood guesthouse",
                "Small inn",
                "Local stay",
            ),
        }
        found = [
            {
                "name": f"{city} · {label} (offline candidate)",
                "place_id": None,
                "category": category,
                "cuisine": [],
                "price_band": 2,
                "rating": None,
                "user_ratings_total": 0,
                "types": [_CATEGORY_TYPES.get(category, category)],
                "offline_seed": True,
            }
            for label in labels.get(category, labels["activity"])
        ]
    return found[:limit]


def search(name: str, city: str) -> dict | None:
    """Text search, cached. A repeat query must never hit the network twice."""
    cache_key = _key("search", name, city)
    cached = _cache_get(cache_key)
    if cached is not _MISSING:
        return cached

    payload = _request(
        _TEXT_URL,
        {"textQuery": f"{name}, {city}", "maxResultCount": 1},
    )
    result = None
    if payload:
        normalized = [_normalize(item) for item in payload.get("places", [])]
        result = next((item for item in normalized if item), None)
    if result is None:
        result = next(
            (
                item
                for category in _CATEGORY_TYPES
                for item in _fallback(city, category, 20)
                if item["name"].casefold() == name.strip().casefold()
            ),
            None,
        )
    _cache_put(cache_key, result)
    return result


def discover(
    city: str, category: str, price_band: int | None = None, limit: int = 20
) -> list[dict]:
    """Candidate pool: name, place_id, price_level, rating, user_ratings_total."""
    category = category if category in _CATEGORY_TYPES else "activity"
    limit = max(1, min(int(limit), 20))
    cache_key = _key("discover", city, category, price_band or "any", limit)
    cached = _cache_get(cache_key)
    if cached is not _MISSING:
        return list(cached or [])

    query = {
        "restaurant": f"independent restaurants in {city}",
        "bar": f"cocktail bars in {city}",
        "activity": f"museums and attractions in {city}",
        "event": f"live music and events in {city}",
        "lodging": f"independent hotels in {city}",
    }[category]
    body: dict[str, Any] = {
        "textQuery": query,
        "includedType": _CATEGORY_TYPES[category],
        "strictTypeFiltering": False,
        "maxResultCount": limit,
    }
    payload = _request(_TEXT_URL, body)
    results = [
        normalized
        for item in ((payload or {}).get("places") or [])
        if (normalized := _normalize(item)) is not None
    ]
    if price_band is not None:
        results = [
            item for item in results if item.get("price_band") in (None, price_band)
        ]
    if not results:
        results = _fallback(city, category, limit)
        if price_band is not None:
            results = [
                item for item in results if item.get("price_band") in (None, price_band)
            ]
    _cache_put(cache_key, results[:limit])
    return results[:limit]


def most_reviewed(city: str, category: str = "restaurant") -> dict | None:
    """The obvious thing. This is the TARGET of the negative recommendation."""
    candidates = discover(city, category, limit=20)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            int(item.get("user_ratings_total") or 0),
            str(item.get("name") or ""),
        ),
    )


def nearby(lat: float, lng: float, radius_m: float = 120.0) -> dict | None:
    """Closest relevant place to EXIF coordinates, cached for Drive enrichment."""
    cache_key = _key(
        "nearby", round(float(lat), 5), round(float(lng), 5), int(radius_m)
    )
    cached = _cache_get(cache_key)
    if cached is not _MISSING:
        return cached
    payload = _request(
        _NEARBY_URL,
        {
            "includedTypes": [
                "restaurant",
                "cafe",
                "bar",
                "museum",
                "tourist_attraction",
                "lodging",
            ],
            "maxResultCount": 1,
            "rankPreference": "DISTANCE",
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": float(lat), "longitude": float(lng)},
                    "radius": float(radius_m),
                }
            },
        },
    )
    result = None
    if payload:
        result = next(
            (
                normalized
                for item in payload.get("places", [])
                if (normalized := _normalize(item)) is not None
            ),
            None,
        )
    _cache_put(cache_key, result)
    return result
