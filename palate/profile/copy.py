"""Profile prose. OWNER B. See docs/trd-b-profile.md.

Build render_plain FIRST — it is the wifi-outage fallback and it forces you to
check that every line has a number behind it.

The number check in this file is the reason nothing false gets read aloud:
every numeral in a rendered line has to appear in the profile dict. It guards
the model's output, and it guards the template's output too — the template is
hand-written, which is exactly the kind of code that drifts from the data.
"""

import json
import re

from palate import contracts

# palate.llm is imported inside render_profile_copy, not here. It pulls in the
# anthropic SDK at module scope, and render_plain has to keep working on a
# laptop where that import fails — no venv, no wheels, no network. The fallback
# path must not depend on the thing it is the fallback for.

PROMPT_RULES = """\
You are given computed statistics with exact counts. Write 5-7 short lines,
second person. Use ONLY the numbers provided; never invent, round, or soften
one. No preamble, no "based on your data", no bullet characters. One
observation per line. Prefer the specific over the general: "23 of your last 30
reservations were parties of two" beats "you usually dine with one other person".
"""

MAX_LINES = 7
MIN_MODEL_LINES = 3  # below this the model output is not worth reading; use the template

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# Spelled-out numbers have to be checked too, in both directions. The target
# copy in PRD 3.1 ends "Four for four" — good prose, and verifiable. The
# failure the TRD names is "about two dozen" standing in for 23, which reads
# fine and is false. Both are words; only one of them traces to a row.
_WORD_VALUE = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_MULTIPLIER = {"dozen": 12, "hundred": 100}
_HEDGE = re.compile(
    r"\b(about|around|roughly|nearly|approximately|almost|some|over|under"
    r"|at least|more than|less than|fewer than|upwards of)\s+([\w.]+)",
    re.IGNORECASE,
)
# "one" is deliberately absent: in this copy it is almost always a pronoun
# ("every one of the 2 solo reservations"), and treating it as a claim would
# make the check fail on lines that are perfectly well sourced.

# Keys whose value is an hour of the day. "8pm" is a faithful rendering of 20,
# so the 12-hour form counts as sourced — the only derivation allowed here.
_HOUR_KEYS = ("earliest_activity_hour", "peak_dining_hour")

_DAY_WORDS = {
    "Sun": "Sundays", "Mon": "Mondays", "Tue": "Tuesdays", "Wed": "Wednesdays",
    "Thu": "Thursdays", "Fri": "Fridays", "Sat": "Saturdays",
}


# ------------------------------------------------------------ number checking


def _canon(token: str) -> str:
    """'08' and '8' and '8.0' are the same number. Compare on one spelling."""
    number = float(token)
    return str(int(number)) if number == int(number) else str(number)


def sourced_numbers(profile: dict) -> set[str]:
    """Every number the profile can legitimately be quoted as saying.

    Read straight off the serialized dict, so values AND the counts inside
    evidence notes both count — the notes are themselves built from row counts.
    Two derivations are added on top:

      - the 12-hour form of an hour key, because copy says "8pm", not "20"
      - the length of any list we publish, because "3 saved places" is sourced
        by the three places sitting in the list

    Anything else — a rounded ratio, a "nearly 30", a number that came from the
    model's own head — is not in this set, and the line carrying it is dropped.
    """
    allowed = {_canon(t) for t in _NUMBER.findall(contracts.dumps(profile))}
    for key in _HOUR_KEYS:
        hour = profile.get(key)
        if isinstance(hour, int):
            allowed.add(_canon(str(hour % 12 or 12)))
    for value in profile.values():
        if isinstance(value, list):
            allowed.add(_canon(str(len(value))))
    return allowed


def _spelled_numbers(line: str) -> list[str]:
    """Numbers written as words. 'twenty-three' is 23; 'two dozen' is 24."""
    words = re.findall(r"[a-z]+", line.lower())
    found: list[str] = []
    index = 0
    while index < len(words):
        word, following = words[index], words[index + 1] if index + 1 < len(words) else ""
        if word in _WORD_VALUE:
            value = _WORD_VALUE[word]
            if value >= 20 and value % 10 == 0 and _WORD_VALUE.get(following, 99) < 10:
                value += _WORD_VALUE[following]
                index += 1
            elif following in _MULTIPLIER:
                value *= _MULTIPLIER[following]
                index += 1
            found.append(str(value))
        elif word in _MULTIPLIER:  # a bare "a dozen"
            found.append(str(_MULTIPLIER[word]))
        index += 1
    return found


def _hedged_numbers(line: str) -> list[str]:
    """Counts wearing a hedge. "Nearly 30" survives the sourcing check — 30 is a
    real row count somewhere in the dict — and is still a softened number, which
    the prompt forbids. A count is exact or it is not read out."""
    hedged = []
    for hedge, target in _HEDGE.findall(line):
        word = target.lower()
        if _NUMBER.fullmatch(word) or word in _WORD_VALUE or word in _MULTIPLIER:
            hedged.append(f"{hedge.lower()} {word}")
    return hedged


def unsourced_numbers(line: str, profile: dict) -> list[str]:
    """The numbers in `line` the profile cannot account for. Empty is good."""
    allowed = sourced_numbers(profile)
    found = _NUMBER.findall(line) + _spelled_numbers(line)
    return [t for t in found if _canon(t) not in allowed] + _hedged_numbers(line)


def verify(lines: list[str], profile: dict) -> tuple[list[str], list[str]]:
    """Split rendered lines into (keeps, drops). A dropped line is not fixed up.

    Rounding is not a small error here. If the model turns 23 into "about two
    dozen" the line is gone; there is no version of this that negotiates with
    a number it cannot trace.
    """
    keeps, drops = [], []
    for line in lines:
        (drops if unsourced_numbers(line, profile) else keeps).append(line)
    return keeps, drops


# ------------------------------------------------------------------ rendering


def _fmt_hour(hour: int) -> str:
    return f"{hour % 12 or 12}{'am' if hour < 12 else 'pm'}"


def render_plain(profile: dict) -> list[str]:
    """Deterministic template. No model, no network. Build this one first."""
    ev = profile.get("evidence") or {}

    def e(key: str, field: str, default=None):
        return (ev.get(key) or {}).get(field, default)

    lines: list[str] = []

    days = profile.get("preferred_days") or []
    hour = profile.get("peak_dining_hour")
    if days and hour is not None:
        named = " and ".join(_DAY_WORDS.get(d, d) for d in days)
        lines.append(
            f"You book {named}, almost always in the {_fmt_hour(hour)} hour —"
            f" {e('peak_dining_hour', 'n')} of {e('peak_dining_hour', 'of')} dining bookings."
        )
    elif hour is not None:
        lines.append(
            f"You eat in the {_fmt_hour(hour)} hour — {e('peak_dining_hour', 'n')} of"
            f" {e('peak_dining_hour', 'of')} dining bookings."
        )

    party = profile.get("typical_party_size")
    if party is not None:
        lines.append(
            f"Parties of {party}. {e('typical_party_size', 'n')} of"
            f" {e('typical_party_size', 'of')} reservations."
        )

    repeats = profile.get("most_repeated") or []
    if profile.get("revisit_ratio"):
        line = f"You go back. {e('revisit_ratio', 'n')} visits across {e('revisit_ratio', 'of')} places"
        if repeats:
            line += f" — {e('most_repeated', 'n')} of them to the same {len(repeats)}"
        lines.append(line + ".")

    floor = profile.get("earliest_activity_hour")
    if floor is not None:
        lines.append(
            f"You have never scheduled anything before {_fmt_hour(floor)}."
            f" Not once in {e('earliest_activity_hour', 'of')} completed visits."
        )

    band = profile.get("cancellation_threshold")
    if band is not None:
        lines.append(
            f"You cancel at the top of your price range. {e('cancellation_threshold', 'n')} of"
            f" {e('cancellation_threshold', 'of')} bookings at band {band}."
        )

    seat = profile.get("seat_preference")
    if seat is not None:
        note = e("seat_preference", "note", "") or ""
        if note.startswith("every"):
            # The scoped version — "every solo reservation was a bar seat" — is
            # the line people remember, so it is used verbatim when it holds.
            lines.append(f"You sit at the {seat}. {note[0].upper()}{note[1:]}.")
        else:
            lines.append(
                f"You sit at the {seat} — {e('seat_preference', 'n')} of"
                f" {e('seat_preference', 'of')} reservations with a seat on record."
            )

    saves = profile.get("aspiration_gap") or []
    if saves:
        lines.append(f"You saved {len(saves)} places to a list. You have been to none of them.")

    aversions = profile.get("cuisine_aversion") or []
    if aversions:
        lines.append(
            f"You tried {' and '.join(aversions)} once and never went back."
        )

    lead = profile.get("booking_lead_time_median_days")
    if lead is not None:
        lines.append(f"You book {lead} days ahead, across {e('booking_lead_time_median_days', 'n')} reservations.")

    return lines[:MAX_LINES]


def render_profile_copy(profile: dict) -> list[str]:
    """Model turns the numbers into 5-7 lines. Routed through Merge Gateway.

    UNVERIFIED against a live model — this branch needs API keys, and it has
    not been run. render_plain() is the tested path; if the call fails, returns
    nothing, or survives the number check with too little left, this falls back
    to it rather than putting thin copy on stage.
    """
    try:  # deferred: see the import note at the top of this file
        from palate import llm
    except ImportError as exc:  # no SDK installed — that is what the template is for
        print(f"copy: model path unavailable ({exc}); rendering the template instead")
        return render_plain(profile)

    facts = json.dumps(profile, indent=2, sort_keys=True)
    prompt = f"{PROMPT_RULES}\nStatistics:\n{facts}\n"

    text = llm.complete_text(prompt, purpose="profile_copy", max_tokens=700)
    if not text.strip():
        return render_plain(profile)

    candidates = [ln.strip(" \t-•*").strip() for ln in text.splitlines()]
    keeps, drops = verify([ln for ln in candidates if ln], profile)
    for line in drops:
        print(f"copy: dropped unsourced line: {line}")
    if len(keeps) < MIN_MODEL_LINES:
        return render_plain(profile)
    return keeps[:MAX_LINES]
