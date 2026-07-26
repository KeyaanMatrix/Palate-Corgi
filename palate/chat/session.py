"""Per-phone state. OWNER C. See docs/trd-c-photon.md step 5.

The message-id -> stop-id map is what makes tapbacks work. Persist it in the
session table; never keep it only in memory, or a 3 AM restart kills the demo.
"""

from __future__ import annotations

import json
from typing import Any

from palate import db


def _parse_state(raw: str | None) -> dict:
    if not raw:
        return {"message_map": {}}
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return {"message_map": {}}
    if not isinstance(state, dict):
        return {"message_map": {}}
    state.setdefault("message_map", {})
    if not isinstance(state["message_map"], dict):
        state["message_map"] = {}
    return state


def get_session(phone: str) -> dict:
    """Return {phone, itinerary_id, itinerary, state, updated_at}."""
    row = db.one(
        "SELECT phone, itinerary_id, state, updated_at FROM session WHERE phone = ?",
        (phone,),
    )
    if row is None:
        return {
            "phone": phone,
            "itinerary_id": None,
            "itinerary": None,
            "state": {"message_map": {}},
            "updated_at": None,
        }
    state = _parse_state(row["state"])
    itinerary = None
    if row["itinerary_id"]:
        itin_row = db.one(
            "SELECT payload FROM itinerary WHERE id = ?",
            (row["itinerary_id"],),
        )
        if itin_row and itin_row["payload"]:
            try:
                itinerary = json.loads(itin_row["payload"])
            except json.JSONDecodeError:
                itinerary = None
    return {
        "phone": row["phone"],
        "itinerary_id": row["itinerary_id"],
        "itinerary": itinerary,
        "state": state,
        "updated_at": row["updated_at"],
    }


def save_session(phone: str, itinerary: dict) -> None:
    """Persist itinerary payload and point the phone session at it."""
    itin_id = itinerary["id"]
    city = itinerary.get("city") or ""
    created_at = itinerary.get("created_at") or db.now()
    payload = json.dumps(itinerary, ensure_ascii=False)

    existing = db.one("SELECT state FROM session WHERE phone = ?", (phone,))
    state_raw = existing["state"] if existing else json.dumps({"message_map": {}})

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO itinerary (id, city, created_at, payload)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              city = excluded.city,
              created_at = excluded.created_at,
              payload = excluded.payload
            """,
            (itin_id, city, created_at, payload),
        )
        conn.execute(
            """
            INSERT INTO session (phone, itinerary_id, state, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
              itinerary_id = excluded.itinerary_id,
              updated_at = excluded.updated_at
            """,
            (phone, itin_id, state_raw, db.now()),
        )


def _write_state(phone: str, state: dict) -> None:
    raw = json.dumps(state, ensure_ascii=False)
    with db.connect() as conn:
        row = conn.execute(
            "SELECT phone FROM session WHERE phone = ?", (phone,)
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO session (phone, itinerary_id, state, updated_at)
                VALUES (?, NULL, ?, ?)
                """,
                (phone, raw, db.now()),
            )
        else:
            conn.execute(
                """
                UPDATE session SET state = ?, updated_at = ? WHERE phone = ?
                """,
                (raw, db.now(), phone),
            )


def reset_message_map(phone: str) -> None:
    """Clear tapback mappings (e.g. before sending a fresh itinerary)."""
    sess = get_session(phone)
    state = sess["state"]
    state["message_map"] = {}
    _write_state(phone, state)


def map_message(phone: str, message_id: str, stop_id: str) -> None:
    sess = get_session(phone)
    state: dict[str, Any] = sess["state"]
    state.setdefault("message_map", {})
    state["message_map"][message_id] = stop_id
    _write_state(phone, state)


def stop_for_message(phone: str, message_id: str) -> str | None:
    sess = get_session(phone)
    mapping = sess["state"].get("message_map") or {}
    stop_id = mapping.get(message_id)
    return str(stop_id) if stop_id else None
