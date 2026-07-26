"""Drive EXIF -> visits. OWNER D. Merge Unified API, File Storage category.

Value: places visited with NO booking trail — the ones no email knows about.
Only write a row when you have BOTH a timestamp and a geotag. Anything else is
noise.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from palate import config, contracts, db
from palate.plan import places

_BASE = "https://api.merge.dev/api/filestorage/v1"
_IMAGE_PREFIX = "image/"


def _headers() -> dict[str, str]:
    if not config.MERGE_API_KEY or not config.MERGE_FILESTORAGE_ACCOUNT_TOKEN:
        raise RuntimeError(
            "MERGE_API_KEY and MERGE_FILESTORAGE_ACCOUNT_TOKEN are required"
        )
    return {
        "Authorization": f"Bearer {config.MERGE_API_KEY}",
        "X-Account-Token": config.MERGE_FILESTORAGE_ACCOUNT_TOKEN,
    }


def _ratio(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        numerator = getattr(value, "numerator", None)
        denominator = getattr(value, "denominator", None)
        if numerator is None or not denominator:
            raise ValueError(f"invalid GPS rational: {value!r}")
        return float(numerator) / float(denominator)


def _coordinate(values: Any, ref: str) -> float:
    degrees, minutes, seconds = values
    result = _ratio(degrees) + _ratio(minutes) / 60 + _ratio(seconds) / 3600
    return -result if str(ref).upper() in {"S", "W"} else result


def _metadata(content: bytes) -> tuple[str, float, float] | None:
    """Return local EXIF wall-clock plus latitude/longitude."""
    from PIL import Image

    with Image.open(BytesIO(content)) as image:
        exif = image.getexif()
        if not exif:
            return None
        raw_date = exif.get(36867) or exif.get(36868) or exif.get(306)
        try:
            gps = exif.get_ifd(34853)
        except (AttributeError, KeyError):
            gps = exif.get(34853) or {}
        if not raw_date or not isinstance(gps, dict):
            return None
        lat_values, lat_ref = gps.get(2), gps.get(1)
        lng_values, lng_ref = gps.get(4), gps.get(3)
        if not all((lat_values, lat_ref, lng_values, lng_ref)):
            return None
        try:
            taken = datetime.strptime(str(raw_date), "%Y:%m:%d %H:%M:%S")
            lat = _coordinate(lat_values, str(lat_ref))
            lng = _coordinate(lng_values, str(lng_ref))
        except (TypeError, ValueError):
            return None
        return taken.strftime("%Y-%m-%dT%H:%M"), lat, lng


def _files(limit: int):
    import httpx

    cursor = None
    yielded = 0
    with httpx.Client(headers=_headers(), timeout=45.0) as client:
        while yielded < limit:
            params: dict[str, Any] = {"page_size": min(100, limit - yielded)}
            if cursor:
                params["cursor"] = cursor
            response = client.get(f"{_BASE}/files", params=params)
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("results", []):
                if not isinstance(item, dict):
                    continue
                yielded += 1
                yield client, item
                if yielded >= limit:
                    return
            cursor = payload.get("next")
            if not cursor:
                return


def sync(limit: int = 200) -> int:
    """Drive images -> EXIF timestamp + GPS -> reverse-geocode -> visit rows
    with source='drive_exif', status='attended_unbooked'."""
    limit = max(0, min(int(limit), 2000))
    written = 0
    for client, item in _files(limit):
        if not str(item.get("mime_type") or "").startswith(_IMAGE_PREFIX):
            continue
        file_id = item.get("id")
        if not file_id:
            continue
        response = client.get(f"{_BASE}/files/{file_id}/download")
        response.raise_for_status()
        meta = _metadata(response.content)
        if meta is None:
            continue
        scheduled_at, lat, lng = meta
        place = places.nearby(lat, lng)
        if not place:
            continue
        name = str(place["name"]).strip()
        visit = {
            "id": contracts.visit_id("drive_exif", str(file_id), name, scheduled_at),
            "source": "drive_exif",
            "source_ref": str(file_id),
            "vendor": None,
            "place_name_raw": name,
            "place_id": place.get("place_id"),
            "city": None,
            "category": place.get("category") or "activity",
            "cuisine": place.get("cuisine") or None,
            "price_band": place.get("price_band"),
            "party_size": None,
            "scheduled_at": scheduled_at,
            "booked_at": None,
            "status": "attended_unbooked",
            "cancelled_at": None,
            "is_travel": 0,
            "intent_only": 0,
            "seat": None,
            "raw_total_cents": None,
            "created_at": db.now(),
        }
        if contracts.valid_visit(visit):
            db.upsert_visit(visit)
            written += 1
    return written
