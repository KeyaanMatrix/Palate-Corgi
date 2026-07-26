"""Profile prose. OWNER B. See docs/trd-b-profile.md.

Build render_plain FIRST — it is the wifi-outage fallback and it forces you to
check that every line has a number behind it.
"""

from palate import llm  # noqa: F401  (routed through Merge Gateway)

PROMPT_RULES = """\
You are given computed statistics with exact counts. Write 5-7 short lines,
second person. Use ONLY the numbers provided; never invent, round, or soften
one. No preamble, no "based on your data", no bullet characters. One
observation per line. Prefer the specific over the general: "23 of your last 30
reservations were parties of two" beats "you usually dine with one other person".
"""


def render_plain(profile: dict) -> list[str]:
    """Deterministic template. No model, no network. Build this one first."""
    raise NotImplementedError


def render_profile_copy(profile: dict) -> list[str]:
    """Model version, via Merge Gateway.

    Then assert every number in the output also appears in the profile dict —
    if the model rounds 23 to "about two dozen", drop that line. Five minutes to
    write, and it is why nothing false gets read aloud.
    """
    raise NotImplementedError
