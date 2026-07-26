"""Inbound routing. OWNER C. See docs/trd-c-photon.md step 7.

Keyword-match BEFORE reaching for the model. The demo says "raining" out loud;
a keyword match cannot fail on stage, and a model call on venue wifi at 7:30 AM
can.
"""

STATE_PATTERNS = {
    "weather": ["raining", "rain", "storm", "pouring"],
    "energy":  ["wrecked", "exhausted", "tired", "dead", "hungover"],
    "running": ["still at lunch", "running late", "behind"],
    "closed":  ["closed", "shut", "not open"],
}

DECLINE = ("I only handle stops — tap a thumbs-down to swap one, or tell me "
           "what changed (raining, running late, museum closed).")


def classify_state(text: str) -> str | None:
    raise NotImplementedError


def handle_text(phone: str, text: str) -> list[str]:
    """Route: state -> replan | 'plan <city>' -> build | else -> DECLINE.

    Out of scope by design: general Q&A. If it answers arbitrary questions it
    becomes a worse Claude app and the Photon argument collapses (PRD 4).
    """
    raise NotImplementedError


def handle_tapback(phone: str, message_id: str, reaction: str) -> list[str]:
    """down -> plan.swap_stop, send the replacement as a NEW message, remap.
    up   -> mark the stop locked, no reply.

    The demo moment is that one stop changes and the rest of the day does not.
    """
    raise NotImplementedError
