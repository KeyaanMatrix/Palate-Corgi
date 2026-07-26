"""Cross-owner contracts. BASE — FROZEN at the base commit.

Everything here is a seam between two people working on different laptops.
Changing anything in this file after 9:30 PM means telling the other three
owners, because their code is written against it. See docs/TRD.md section 3.
"""

import hashlib
import json
from typing import Any

# ---------------------------------------------------------------- visit (A, D → B)

VISIT_FIELDS = [
    "id", "source", "source_ref", "vendor", "place_name_raw", "place_id", "city",
    "category", "cuisine", "price_band", "party_size", "scheduled_at", "booked_at",
    "status", "cancelled_at", "is_travel", "intent_only", "seat", "raw_total_cents",
    "created_at",
]

SOURCES = ("gmail", "calendar", "drive_exif", "notion")
CATEGORIES = ("restaurant", "bar", "event", "lodging", "activity")
STATUSES = ("confirmed", "cancelled", "modified", "attended_unbooked")
SEATS = ("bar", "table", "unknown")


def visit_id(source: str, source_ref: str, place: str, scheduled_at: str) -> str:
    """Deterministic id so re-running ingest is idempotent (TRD 3.1)."""
    key = f"{source}|{source_ref}|{(place or '').strip().lower()}|{scheduled_at or ''}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


# The JSON schema handed to the model for Stage-2 extraction. Owner A passes this
# to llm.complete_json(); rows that fail validation are DROPPED, never repaired.
VISIT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "visits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_ref": {"type": "string"},
                    "vendor": {"type": "string"},
                    "place_name_raw": {"type": "string"},
                    "city": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"], "enum": [*CATEGORIES, None]},
                    "cuisine": {"type": ["array", "null"], "items": {"type": "string"}},
                    "price_band": {"type": ["integer", "null"], "minimum": 1, "maximum": 4},
                    "party_size": {"type": ["integer", "null"]},
                    "scheduled_at": {"type": ["string", "null"]},
                    "booked_at": {"type": ["string", "null"]},
                    "status": {"type": "string", "enum": list(STATUSES)},
                    "cancelled_at": {"type": ["string", "null"]},
                    "seat": {"type": ["string", "null"], "enum": [*SEATS, None]},
                    "raw_total_cents": {"type": ["integer", "null"]},
                },
                "required": ["source_ref", "place_name_raw", "status"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["visits"],
    "additionalProperties": False,
}


def valid_visit(v: dict) -> bool:
    """Cheap gate before writing. Precision over recall — when in doubt, drop."""
    if not v.get("place_name_raw") or not str(v["place_name_raw"]).strip():
        return False
    if v.get("status") not in STATUSES:
        return False
    if v.get("category") not in (None, *CATEGORIES):
        return False
    band = v.get("price_band")
    if band is not None and band not in (1, 2, 3, 4):
        return False
    return True


# -------------------------------------------------------------- profile (B → C, D)

TASTE_PROFILE_KEYS = [
    "home_city", "earliest_activity_hour", "peak_dining_hour", "preferred_days",
    "typical_party_size", "price_ceiling", "cancellation_threshold", "revisit_ratio",
    "novelty_appetite", "cuisine_affinity", "cuisine_aversion",
    "booking_lead_time_median_days", "seat_preference", "pace", "avoided_categories",
    "aspiration_gap", "evidence",
]

# Keys that MUST have an entry in profile["evidence"]. PRD 5.4: a profile line the
# presenter can't source is the one thing that kills the demo.
EVIDENCE_REQUIRED = [
    "earliest_activity_hour", "peak_dining_hour", "typical_party_size",
    "cancellation_threshold", "revisit_ratio", "seat_preference",
]


class Evidence:
    """Collects the row counts behind every headline number.

        ev = Evidence()
        ev.add("typical_party_size", n=23, of=30, note="parties of two")
    """

    def __init__(self) -> None:
        self._d: dict[str, dict] = {}

    def add(self, key: str, n: int, of: int | None = None, note: str = "") -> None:
        self._d[key] = {"n": int(n), "of": None if of is None else int(of), "note": note}

    def as_dict(self) -> dict:
        return dict(self._d)


def profile_is_sourced(profile: dict) -> list[str]:
    """Return the keys missing evidence. Empty list == safe to put on stage."""
    ev = profile.get("evidence") or {}
    return [k for k in EVIDENCE_REQUIRED if profile.get(k) is not None and k not in ev]


# ------------------------------------------------------------ itinerary (D → C)

ITINERARY_KEYS = ["id", "city", "created_at", "negative_recommendation", "days"]
STOP_KEYS = [
    "id", "seq", "name", "category", "time", "price_band", "because",
    "is_stretch", "locked", "place_id",
]


def iter_stops(itinerary: dict):
    for day in itinerary.get("days", []):
        for stop in day.get("stops", []):
            yield day, stop


def validate_itinerary(itinerary: dict, profile: dict | None = None) -> list[str]:
    """Return a list of contract violations. Empty == valid. See TRD 3.3."""
    problems: list[str] = []
    for key in ITINERARY_KEYS:
        if key not in itinerary:
            problems.append(f"missing key: {key}")
    stops = [s for _, s in iter_stops(itinerary)]
    if not stops:
        problems.append("itinerary has no stops")
    ids = [s.get("id") for s in stops]
    if len(ids) != len(set(ids)):
        problems.append("duplicate stop ids")
    stretches = [s for s in stops if s.get("is_stretch")]
    if len(stretches) != 1:
        problems.append(f"expected exactly 1 stretch stop, found {len(stretches)}")
    if not itinerary.get("negative_recommendation"):
        problems.append("missing negative_recommendation")
    for s in stops:
        if not s.get("because"):
            problems.append(f"stop {s.get('id')} has no 'because'")
    if profile:
        floor = profile.get("earliest_activity_hour")
        if floor is not None:
            for s in stops:
                t = s.get("time") or ""
                if t[:2].isdigit() and int(t[:2]) < int(floor):
                    problems.append(f"stop {s.get('id')} at {t} is before revealed floor {floor}:00")
    return problems


def locked_ids(itinerary: dict) -> set[str]:
    return {s["id"] for _, s in iter_stops(itinerary) if s.get("locked")}


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
