"""The 'because'. OWNER D. Routed through Merge Gateway.

Bad:  Recommended because you like Italian food.
Good: You've been to Cotogna four times and always at the counter. This is the
      one counter-service place in Lisbon that runs the same way — booked
      Wednesday 8:45, which is your slot.
"""

from palate import llm  # noqa: F401

PROMPT_RULES = """\
Explain this recommendation by referencing a SPECIFIC behavior from the user's
history: a named place they went to repeatedly, a count, a time slot, a
cancellation. Never use genre labels — "because you like Italian food" is a
failure. Two sentences maximum. No preamble.
"""


def write_because(stop: dict, profile: dict, evidence_rows: list[dict]) -> str:
    """Cache by (stop_id, profile_version) — a swap must not regenerate the day."""
    raise NotImplementedError
