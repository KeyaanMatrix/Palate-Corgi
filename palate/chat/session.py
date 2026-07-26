"""Per-phone state. OWNER C. See docs/trd-c-photon.md step 5.

The message-id -> stop-id map is what makes tapbacks work. Persist it in the
session table; never keep it only in memory, or a 3 AM restart kills the demo.
"""

from palate import db  # noqa: F401


def get_session(phone: str) -> dict:
    raise NotImplementedError


def save_session(phone: str, itinerary: dict) -> None:
    raise NotImplementedError


def map_message(phone: str, message_id: str, stop_id: str) -> None:
    raise NotImplementedError


def stop_for_message(phone: str, message_id: str) -> str | None:
    raise NotImplementedError
