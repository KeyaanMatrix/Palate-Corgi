"""Message rendering. OWNER C. See docs/trd-c-photon.md step 4.

Rules:
  - ONE STOP PER MESSAGE. A tapback targets a message, so this is what makes
    tapbacks work as a control surface.
  - No agent voice. No "Here's your itinerary!". Every message is written to be
    forwarded to a travel companion as-is (PRD section 4).
  - No markdown — iMessage renders none of it.
"""


def format_stop(stop: dict, day_index: int) -> str:
    """Time, name, then the 'because' on its own line."""
    raise NotImplementedError


def format_profile(lines: list[str]) -> str:
    raise NotImplementedError


def format_negative(neg: dict) -> str:
    """The one thing we tell them to skip. The line judges remember."""
    raise NotImplementedError
