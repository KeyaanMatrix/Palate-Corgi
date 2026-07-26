"""Message rendering. OWNER C. See docs/trd-c-photon.md step 4.

Rules:
  - ONE STOP PER MESSAGE. A tapback targets a message, so this is what makes
    tapbacks work as a control surface.
  - No agent voice. No "Here's your itinerary!". Every message is written to be
    forwarded to a travel companion as-is (PRD section 4).
  - No markdown — iMessage renders none of it.
"""

from __future__ import annotations


def _format_time(time_str: str) -> str:
    """Convert '20:45' or '8:45' to '8:45pm'."""
    raw = (time_str or "").strip()
    if not raw:
        return ""
    lower = raw.lower().replace(" ", "")
    if lower.endswith("am") or lower.endswith("pm"):
        # Normalize e.g. 8:45PM -> 8:45pm
        body = lower[:-2].lstrip("0") or "0"
        return body + lower[-2:]
    parts = raw.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return raw
    suffix = "am" if hour < 12 else "pm"
    h12 = hour % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{minute:02d}{suffix}"


def format_stop(stop: dict, day_index: int) -> str:
    """Time, name, then the 'because' on its own line."""
    when = _format_time(str(stop.get("time") or ""))
    name = str(stop.get("name") or "").strip()
    because = str(stop.get("because") or "").strip()
    head = f"{when} · {name}" if when else name
    if because:
        return f"{head}\n\n{because}"
    return head


def format_profile(lines: list[str]) -> str:
    cleaned = [str(line).strip() for line in lines if str(line).strip()]
    return "\n".join(cleaned)


def format_negative(neg: dict) -> str:
    """The one thing we tell them to skip. The line judges remember."""
    name = str((neg or {}).get("name") or "").strip()
    why = str((neg or {}).get("why") or "").strip()
    if name and why:
        return f"Skip {name}\n\n{why}"
    if name:
        return f"Skip {name}"
    return why
