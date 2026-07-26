# Sub-TRD D — Merge Gateway, Enrichment, Itinerary

**Branch:** `d-gateway-plan` **Owns:** `palate/llm.py`, `palate/enrich/`, `palate/plan/`, `requirements/d.txt`
**Read `docs/TRD.md` §1–§6 first.** Sections 3.3 and 3.4 are the contracts you provide to everyone else.

## Your mission

Three jobs, in strict priority order:

1. **Merge Gateway on the critical path** (30 minutes, hour 0). A and B cannot extract or write copy until `llm.py` works. Do this first, before anything else, and tell the team the moment it's live.
2. **Itinerary assembly** — the three functions C builds against.
3. **Merge Unified API enrichment** (Drive EXIF, Notion) — genuinely valuable, explicitly **not** on the critical path. Drop it without ceremony if you're behind.

You also answer the **7:50 PM hard gate**: does Merge Link authorize *personal* Google Drive / Notion accounts, or workspace-only? (PRD §5.2.) Have that answer before anyone builds against it.

---

## Hour 0 (7:30–8:00 PM) — Gateway. Nothing else until this works.

### 1. Claim the credit

Merge Gateway: $10 on signup + $10 with code `CORGI-CAFE`. Get `MERGE_GATEWAY_BASE_URL` and `MERGE_GATEWAY_API_KEY` into `.env`.

### 2. Verify the contract

`palate/llm.py` ships assuming the Gateway is a **`base_url` swap for the Anthropic Messages API**. Verify that against Merge's actual docs:

```bash
python -m palate llm.route     # should print: routing model calls via: gateway
python -c "from palate import llm; print(llm.complete_text('Say OK.', purpose='smoke'))"
```

If the Gateway speaks a different shape (OpenAI-compatible, its own envelope), **only `client()` and `_call()` in `llm.py` change.** Every caller depends on `complete_json` / `complete_text`, so the blast radius is one file. That isolation is the whole reason the wrapper exists — do not let a contract surprise turn into a refactor.

### 3. Tell the team

Post in the group chat: "Gateway live, `complete_json` and `complete_text` work." A and B are blocked on this. **8:00 PM gate:** working, or `LLM_DIRECT=1` and the Gateway becomes a post-freeze retry.

### 4. Answer the Merge Link question (by 7:50 PM)

Open Merge Link, try to authorize a **personal** Google Drive and a **personal** Notion. Answer is yes or no, and it decides whether §Enrichment below happens at all. Report it at the 9:30 checkpoint either way.

---

## Hour 0.5 (8:00–9:30 PM) — Places wrapper

### `palate/plan/places.py`

```python
def search(name: str, city: str) -> dict | None:
    """Google Places text search. Cached in place_cache — a repeat query must
    never hit the network twice."""

def discover(city: str, category: str, price_band: int | None = None,
             limit: int = 20) -> list[dict]:
    """Candidate pool for a city. Returns name, place_id, price_level, rating,
    user_ratings_total, types, lat/lng."""

def most_reviewed(city: str, category: str = "restaurant") -> dict | None:
    """The single most-reviewed place in the city. This is the target of the
    negative recommendation — the obvious thing you tell them to skip."""
```

**Cache everything in `place_cache`.** Venue wifi at 2 AM is unreliable and Places is the only network call in the demo path. A cached city means the itinerary builds offline.

---

## Hour 2 (9:30–11:30 PM) — Enrichment (parallel track, droppable)

Skip this entire section if the Link answer at 7:50 was "workspace-only" and nobody has a usable work account, or if you're behind on the itinerary. It is worth real prize points but the demo does not depend on it.

### `palate/enrich/merge_link.py`
Link token → account token flow. Store the account token in `.env`.

### `palate/enrich/filestorage_exif.py`

```python
def sync(limit: int = 200) -> int:
    """Drive images → EXIF timestamp + GPS → reverse-geocode → visit rows with
    source='drive_exif', status='attended_unbooked'."""
```

Value: places visited with **no booking trail** — the ones no email knows about. Use `pillow` for EXIF; convert GPS rationals to decimal degrees; reverse-geocode via Places. Only write a row when you have both a timestamp and a geotag; anything else is noise.

### `palate/enrich/knowledge_base.py`

```python
def sync() -> int:
    """Notion pages/databases that look like restaurant lists → visit rows with
    intent_only=1, no scheduled_at."""
```

**This is the highest-value-per-line-of-code thing you will write tonight.** It produces the aspiration gap: *"You saved 14 places to this list. You went to two."* (PRD §8.2 step 4.) B computes the gap; you just have to land the rows. Match a page as a list if it has ≥5 items and the title or items look restaurant-shaped.

---

## Hour 4 (11:30 PM–2:00 AM) — Itinerary assembly. This is your real deliverable.

### `palate/plan/candidates.py`

```python
def filter_by_profile(candidates: list[dict], profile: dict) -> list[dict]:
    """Apply revealed constraints BEFORE ranking. Order matters — filtering
    after ranking gives you popular places that violate the profile."""

def rank(candidates: list[dict], profile: dict) -> list[dict]:
    """Score by cuisine_affinity, price fit, category fit. NOT by rating —
    rating is the popularity engine this product exists to reject."""
```

Filters, from the profile:
- Drop anything above `cancellation_threshold` unless deliberately flagged.
- Drop cuisines in `cuisine_aversion`.
- Drop categories in `avoided_categories`.
- Nothing before `earliest_activity_hour`.

### `palate/plan/assemble.py` — the three functions C calls

```python
def build_itinerary(profile: dict, city: str, days: int = 3) -> dict: ...
def swap_stop(itinerary: dict, stop_id: str, reason: str | None = None) -> dict: ...
def replan(itinerary: dict, from_iso: str, state_text: str) -> dict: ...
```

Assembly order:

1. `places.discover` for each category → `filter_by_profile` → `rank`.
2. Lay out days at `pace` stops per day, dinner at `peak_dining_hour`, gaps matching revealed pace. Nothing before `earliest_activity_hour`.
3. Pick exactly **one stretch stop** — outside the pattern, with the reasoning stated. This ships the model's judgment, not just its retrieval (PRD §3.2).
4. Pick exactly **one negative recommendation** — `places.most_reviewed(city)`, with a reason drawn from the user's own history. *"It's the single most-reviewed restaurant in the city, and it's a two-hour tasting menu at $210/head. You've cancelled four of those."* PRD §8.2 step 6: this is the line judges will remember.
5. `rationale.write_because(stop, profile)` for every stop.
6. `contracts.validate_itinerary(itin, profile)` → must return `[]`. **Never return an itinerary that fails its own contract.**

The two mutation functions have hard invariants (TRD §3.3) that C relies on:

- `swap_stop`: changes exactly one stop; every other `stop.id` is byte-identical; refuses to touch `locked=True`.
- `replan`: rewrites only stops at/after `from_iso`; preserves every `locked=True` stop; keeps stop ids for anything it keeps.
- Both are **pure**. Take an itinerary, return a new one. C owns persistence.

Write a test that locks a stop, calls both, and asserts the locked stop is identical. That test is the difference between a clean demo and a visibly broken one.

### `palate/plan/rationale.py`

```python
def write_because(stop: dict, profile: dict, evidence_rows: list[dict]) -> str:
    """One or two sentences, traced to a SPECIFIC parsed behavior."""
```

Put this in the prompt verbatim — it is the difference between the product and a genre-matcher:

> Explain this recommendation by referencing a **specific** behavior from the user's history: a named place they went to repeatedly, a count, a time slot, a cancellation. Never use genre labels — "because you like Italian food" is a failure. Two sentences maximum. No preamble.

Bad: *Recommended because you like Italian food.*
Good: *You've been to Cotogna four times and always at the counter. This is the one counter-service place in Lisbon that runs the same way — booked Wednesday 8:45, which is your slot.*

Cache rationales by `(stop_id, profile_version)`. A swap should not re-generate the whole day's prose.

---

## Cost control — you own the $20

`make spend` before the 2:00 AM backfill. Extraction runs at `effort="low"` (structured output doesn't need deep reasoning); prose runs at `effort="medium"`. If projected spend crosses ~$12, tell A to cap the backfill window. You are the one watching this number — nobody else will.

---

## Your smoke check

```python
def check(args) -> None:
    from palate import contracts
    from palate.profile.build import load_profile
    from .assemble import build_itinerary, swap_stop
    profile = load_profile() or {"earliest_activity_hour": 11, "pace": 2.0,
                                 "peak_dining_hour": 20, "price_ceiling": 3}
    itin = build_itinerary(profile, "Lisbon", days=2)
    problems = contracts.validate_itinerary(itin, profile)
    assert not problems, problems
    # locked stops survive a swap
    day, first = next(contracts.iter_stops(itin))
    first["locked"] = True
    other = [s for _, s in contracts.iter_stops(itin) if s["id"] != first["id"]][0]
    after = swap_stop(itin, other["id"])
    kept = {s["id"] for _, s in contracts.iter_stops(after)}
    assert first["id"] in kept, "swap_stop clobbered a locked stop"
    print("plan.check OK")
```

## Commands you expose

```python
# palate/plan/commands.py
COMMANDS = {
    "itinerary": lambda a: print(contracts.dumps(build_itinerary(load_profile(), a[0], int(a[1]) if len(a)>1 else 3))),
    "places":    lambda a: print(places.discover(a[0], a[1] if len(a)>1 else "restaurant")),
    "check":     check,
}
# palate/enrich/commands.py
COMMANDS = {
    "drive":  lambda a: print(f"{filestorage_exif.sync()} visits"),
    "notion": lambda a: print(f"{knowledge_base.sync()} intent rows"),
    "check":  check,
}
```

## If it goes wrong

| Symptom | Move |
|---|---|
| Gateway erroring | `LLM_DIRECT=1`, tell the team, retry the Gateway post-freeze. **Don't block A and B on it** |
| Gateway rate-limits mid-backfill | Raise batch size to 30, lower effort to `low`, cap the window |
| Merge Link is workspace-only | Drop to EXIF-only, or drop enrichment entirely. Say so at the 9:30 checkpoint so B doesn't build the aspiration gap against nothing |
| Places quota | Everything is cached in `place_cache`. Pre-warm the two or three cities most likely to be picked |
| Rationales sound generic | The prompt is the problem, not the model. Force a named place and a count into every one |
| Behind on the itinerary at 2 AM | Cut enrichment, cut the stretch-stop selection logic to a simple "highest-rated item that violates one constraint". **Never cut the negative recommendation** — it's the memorable line |
