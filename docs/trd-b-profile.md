# Sub-TRD B — Taste Profile

**Branch:** `b-profile` **Owns:** `palate/profile/`, `requirements/b.txt`
**Read `docs/TRD.md` §1–§6 first.** Sections 3.1 and 3.2 are your contracts.

## Your mission

**You own the demo.** PRD §3.1 is explicit: the Taste Profile is the artifact judges remember, and the itinerary is proof the profile was right. It is also the direct answer to the event's "make it feel human" theme — it is the thing that expresses rather than executes.

Two non-negotiables:

1. **Every number is pure SQL over the `visit` table. No model involvement.** The model writes prose about your numbers; it never produces one.
2. **Every headline number carries an `evidence` entry with row counts.** `contracts.EVIDENCE_REQUIRED` lists the mandatory ones. A profile line the presenter can't source is the single fastest way to lose the room.

You also run the **integration merges** at each checkpoint (TRD §5.3) — the profile sits in the middle of every dependency, so you find out first when something breaks.

You do **not** own: ingest (A), the itinerary (D), the chat layer (C).

---

## Hour 0 (7:30–9:30 PM) — Metrics on seed data

`make reset` gives you 30 seeded visits shaped to exercise every metric. You are not blocked on A. Start now.

### `palate/profile/metrics.py`

One function per metric, each returning `(value, Evidence-args)`. Write them as SQL; use `statistics` for percentiles and mode.

```python
def earliest_activity_hour() -> tuple[int | None, dict]:
    """p5 of the scheduled hour across confirmed visits. The 'nothing before 11am' line."""

def peak_dining_hour() -> tuple[int | None, dict]:
    """Mode of scheduled hour, restaurants + bars only."""

def preferred_days() -> tuple[list[str], dict]:
    """Days holding >1.5x their uniform share. Usually two of them; that's the line."""

def typical_party_size() -> tuple[int | None, dict]:
    """Mode. Evidence must be 'N of M reservations' — that count IS the line."""

def price_ceiling() -> tuple[int | None, dict]:
    """Highest band with a confirmed, non-cancelled visit."""

def revisit_ratio() -> tuple[float, dict]:
    """total confirmed visits / distinct places. >1.8 reads as 'you go back'."""

def novelty_appetite(revisit: float) -> str:
    """low <1.5x ... high. Derived, not measured — no evidence entry needed."""

def cuisine_affinity() -> tuple[dict[str, float], dict]:
    """Weighted by REPEAT count, not raw count (PRD 5.3). One visit is not a preference."""

def booking_lead_time_median_days() -> tuple[int | None, dict]:
    """median(scheduled_at - booked_at)."""

def seat_preference() -> tuple[str, dict]:
    """Modal seat. The strongest version is scoped: 'every solo reservation was a bar seat.'"""

def pace() -> tuple[float, dict]:
    """Stops per active day (days with >=1 visit). Feeds D's density constraint."""

def home_city() -> tuple[str, dict]:
    """Modal city. Everything else is is_travel."""
```

Handle nulls everywhere. Seeded rows have nulls on purpose; real rows will have more.

### Gate — 9:30 PM

`python -m palate profile.build` produces a full profile dict on seed data and prints it.

---

## Hour 2 (9:30–11:30 PM) — Distaste. This is the differentiator.

PRD §1: every recommender models preference; none model revealed aversion. This file is the technical claim.

### `palate/profile/distaste.py`

```python
def cancellation_threshold() -> tuple[int | None, dict]:
    """Lowest price_band where cancel rate > 0.5.

    Evidence MUST be 'k of n at band B' — the demo line is "You cancel above
    $180/head. Four for four." A bare threshold with no count is worthless.
    Return None when there is no such band; never fabricate one.
    """

def cuisine_aversion(min_alternatives: int = 3) -> tuple[list[str], dict]:
    """Cuisines tried exactly once and never returned to, where the user had
    >= min_alternatives other options in that window. The guard is what stops
    'you hate Ethiopian' from meaning 'you went once, in 2024'."""

def avoided_categories() -> tuple[list[str], dict]:
    """Categories that are booked-then-cancelled, or saved-never-visited, at a
    rate well above baseline. The seeded 9am tour is the archetype."""

def aspiration_gap() -> tuple[list[dict], dict]:
    """intent_only=1 rows (Notion saves) with no matching confirmed visit.

    PRD 8.2 step 4: 'I saved 14. I went to 2.' Biggest emotional hit in the demo,
    and it exists only because Merge is in the stack. Match on normalized name.
    """
```

Threshold guidance: require **n >= 3** before reporting a cancellation threshold, and **n >= 2** for a cuisine aversion. Below that you are reporting noise as insight, and someone will ask.

### `palate/profile/build.py`

```python
def build_profile() -> dict:
    """Run every metric, assemble the dict, write a taste_profile row, return it."""

def load_profile() -> dict | None:
    """Latest row, parsed. THIS IS WHAT C AND D CALL. Keep the signature stable."""
```

At the end of `build_profile`, before writing:

```python
missing = contracts.profile_is_sourced(profile)
if missing:
    raise ValueError(f"unsourced profile keys: {missing}")
```

Fail loudly. An unsourced number must never reach the stage.

---

## Hour 4 (11:30 PM–1:00 AM) — Prose

### `palate/profile/copy.py`

```python
def render_profile_copy(profile: dict) -> list[str]:
    """Model turns your numbers into 5-7 lines. Routed through Merge Gateway."""

def render_plain(profile: dict) -> list[str]:
    """Deterministic template fallback. No model. Works with no network at 3 AM."""
```

Build `render_plain` **first**. It is your wifi-outage insurance and it forces you to check that every line has a number behind it.

Prompt rules for the model version — put these in the prompt verbatim:

> You are given computed statistics with exact counts. Write 5–7 short lines, second person. **Use only the numbers provided; never invent, round, or soften one.** No preamble, no "based on your data", no bullet characters. One observation per line. Prefer the specific over the general: "23 of your last 30 reservations were parties of two" beats "you usually dine with one other person."

Then `assert` that every number appearing in the output also appears in the profile dict. If the model rounds 23 to "about two dozen", drop that line. This check takes five minutes to write and it is the reason nothing false gets read aloud.

### Target output (PRD §3.1)

```
You book Tuesdays and Wednesdays, almost always between 8:30 and 9:15pm.
Parties of two. 23 of your last 30 reservations.
You go back. Three visits before you'll try somewhere new — the same six places, 41 times this year.
You have never scheduled anything before 11am on a trip. You booked a 9am tour in Mexico City and cancelled it the night before.
You cancel above $180/head. Four for four.
You sit at the bar. Every solo reservation in two years was a bar seat.
```

---

## The 1:00–2:00 AM dinner break is part of your job

Bring the profile to the table and **read it out loud** (PRD §7). Every line that makes someone say "wait, is that right?" is a bug you would otherwise have shipped. This is the cheapest bug-catch available tonight and it only works if you actually do it.

---

## Hour 6 (2:00–4:00 AM) — Real data

Rebuild on A's real rows. Expect metrics that were clean on seed data to be ugly on real data: null cities, party sizes missing, one restaurant appearing under three spellings. Fix the metric to tolerate it; do not fix it by filtering rows until the number looks good.

Add `python -m palate profile.evidence <key>` — prints the rows behind one metric. When someone challenges a number at 3 AM, this settles it in ten seconds.

---

## Your smoke check

```python
def check(args) -> None:
    from palate import contracts
    from .build import build_profile
    p = build_profile()
    missing = contracts.profile_is_sourced(p)
    assert not missing, f"unsourced keys: {missing}"
    for key in ("earliest_activity_hour", "typical_party_size", "revisit_ratio"):
        assert p.get(key) is not None, f"{key} is None on seed data"
    print(f"profile.check OK ({len(p.get('evidence', {}))} sourced metrics)")
```

## Commands you expose

```python
COMMANDS = {
    "build":    lambda a: print(contracts.dumps(build_profile())),
    "render":   lambda a: print("\n".join(render_profile_copy(load_profile()))),
    "evidence": lambda a: print(explain(a[0])),
    "check":    check,
}
```

## If it goes wrong

| Symptom | Move |
|---|---|
| A's rows aren't there yet | Seed data. You are not blocked; that's why it exists |
| A metric is null on real data | Return `None` and drop the line from the copy. Never fabricate a fallback value |
| Cancellation threshold has n=1 | Don't report it. A four-for-four is a great line; a one-for-one is a lie |
| The model rounds a number in the copy | Drop that line. Your assertion should already catch it |
| Profile reads generic | You're reporting averages. Go narrower — scope to solo reservations, or to travel days. Specificity is the whole product |
