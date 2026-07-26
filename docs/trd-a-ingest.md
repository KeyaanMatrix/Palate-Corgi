# Sub-TRD A — Ingest

**Branch:** `a-ingest` **Owns:** `palate/ingest/`, `requirements/a.txt`
**Read `docs/TRD.md` §1–§6 first.** Sections 3.1 and 3.4 are your contracts.

## Your mission

You own the only thing on the critical path that cannot be recovered from: **Gmail OAuth → sync → extraction → real `visit` rows on one real inbox.** Everything else in this build has a fallback. This does not. If you are behind at any checkpoint, say so loudly — the team's answer is to switch to seeded data, and that decision has to be made at 1:00 AM, not 4:00.

You do **not** own: the profile math (B), the model wrapper (D), anything in `chat/`.

---

## Hour 0 (7:30–9:30 PM) — OAuth and raw landing

The whole night's risk is front-loaded here. Do these in order and do not get distracted by extraction quality.

### 1. Google Cloud project (do this during the 6:00–7:30 presentation if you can)

1. console.cloud.google.com → new project.
2. Enable **Gmail API** and **Google Calendar API**.
3. OAuth consent screen → **External** → **Testing** mode. Add the presenter's Google account as a test user. Testing mode needs no verification and is fine for a demo — this is the single most common way teams lose two hours tonight.
4. Credentials → OAuth client ID → **Desktop app** → download JSON → save as `./client_secret.json` (gitignored).

### 2. `palate/ingest/google_auth.py`

```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

def credentials() -> Credentials:
    """Load cached token, refresh if stale, else run InstalledAppFlow.

    Token cached at config.GOOGLE_TOKEN_PATH so the demo does not require a
    live browser consent flow on stage.
    """

def gmail_service(): ...
def calendar_service(): ...
```

Use `google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)`. Cache the token as JSON. **Test the refresh path** — delete nothing, just re-run and confirm it does not reopen the browser. On stage you want zero browser prompts.

### 3. `palate/ingest/gmail_sync.py`

```python
def run_sync(limit: int = 500, since: str = "2y") -> int:
    """Fetch messages matching the vendor query into raw_message. Returns count."""
```

- Build one Gmail `q` from `vendors.QUERY_FRAGMENT` (see below) rather than fetching the whole mailbox. `newer_than:2y` plus a `from:` OR-list is dramatically faster than paging everything.
- `users().messages().list()` → paginate → `users().messages().get(format='full')`.
- Extract `From`, `Subject`, `Date` from headers; walk the MIME tree for `text/plain`, falling back to `text/html` with tags stripped. **Truncate bodies to ~4000 chars** before storing — confirmation emails put everything useful up top, and this is what keeps your extraction token cost down.
- `INSERT OR REPLACE INTO raw_message` keyed on the Gmail message id, so re-running is free.

### 4. `palate/ingest/calendar_sync.py`

```python
def run_sync(months_back: int = 24) -> int:
    """Calendar events → raw_message rows with source='calendar'."""
```

Calendar is lower value than Gmail — it gives you pace, trip date ranges, and deletions. Do the minimum: `events().list(timeMin=..., singleEvents=True)`, store summary + location + start. **If you are behind at 9:30 PM, skip Calendar entirely and come back at 2:00 AM.** Gmail is the product.

### Gate — 9:30 PM

`python -m palate ingest.sync 200` puts real rows in `raw_message`. Not extracted, not clean. Just landed. Report the row count at the checkpoint.

---

## Hour 2 (9:30–11:30 PM) — Pre-filter and extraction

### 5. `palate/ingest/vendors.py`

The deterministic Stage-1 filter (PRD §5.4). This is pure rules, no model, and it cuts LLM call volume by an order of magnitude.

```python
VENDORS = {
    "resy":       {"domains": ["resy.com"],       "subjects": ["reservation", "confirmed", "cancelled"]},
    "opentable":  {"domains": ["opentable.com"],  "subjects": ["reservation", "table", "cancel"]},
    "tock":       {"domains": ["exploretock.com", "tock.com"], "subjects": ["reservation", "ticket"]},
    "sevenrooms": {"domains": ["sevenrooms.com"], "subjects": ["reservation"]},
    "eventbrite": {"domains": ["eventbrite.com"], "subjects": ["ticket", "order confirm"]},
    "dice":       {"domains": ["dice.fm"],        "subjects": ["ticket"]},
    "airbnb":     {"domains": ["airbnb.com"],     "subjects": ["reservation", "itinerary"]},
    # ... target ~15 total: add hotels (marriott, hyatt), airlines (united, delta,
    # alaska), yelp/restaurant direct confirmations you actually see in the inbox.
}

QUERY_FRAGMENT: str   # "from:(resy.com OR opentable.com OR ...) newer_than:2y"

def classify(sender: str, subject: str) -> str | None:
    """Return a vendor key, or None to DROP. Precision over recall."""
```

**Build this list by looking at the presenter's actual inbox,** not from memory. Search their mail for "reservation" and see which senders come back. Fifteen accurate vendors beats forty guessed ones.

### 6. `palate/ingest/prefilter.py`

```python
def run(limit: int | None = None) -> dict[str, int]:
    """Classify unclassified raw_message rows; set matched_vendor or leave NULL.
    Returns {vendor: count} for the checkpoint report."""
```

Anything unmatched is **dropped, not queued.** Do not send it to the model to "see what happens" — that is how the $20 credit disappears.

### 7. `palate/ingest/extract.py` — Stage 2

```python
def extract_pending(batch_size: int = 20) -> int:
    """Batch matched messages → llm.complete_json → visit rows. Returns rows written."""
```

The loop:

1. `SELECT * FROM raw_message WHERE matched_vendor IS NOT NULL AND extracted = 0 LIMIT ?`
2. Build **one prompt per ~20 messages**, each message delimited and tagged with its id so the model can return `source_ref`.
3. `llm.complete_json(prompt, contracts.VISIT_EXTRACTION_SCHEMA, purpose="extract")`.
4. `None` back → mark the batch `extracted=1` and **move on**. Do not retry, do not repair. Precision over recall (PRD §5.4).
5. For each returned visit: `contracts.valid_visit(v)` → false means drop. True means compute `contracts.visit_id(...)`, set `is_travel = city != config.HOME_CITY`, `db.upsert_visit(v)`.
6. Mark the batch extracted.

Prompt guidance — put this in the system-level framing, and keep it short:

> Extract one entry per booking. Times are **local wall-clock, no timezone** — copy what the email says. If a field is not stated, return null; never infer or estimate. A cancellation email for a prior booking is `status: "cancelled"` with `cancelled_at` set. Ignore marketing email entirely.

The "never infer" line matters more than anything else in the prompt. A hallucinated party size becomes a wrong number on stage.

### Gate — 11:30 PM → 1:00 AM

**`python -m palate ingest.extract` produces real `visit` rows from the real inbox.** This is the PRD §7 hard gate. Then:

```bash
sqlite3 palate.db "SELECT vendor, status, place_name_raw, scheduled_at, party_size FROM visit LIMIT 25"
```

**Eyeball 20 rows before anyone trusts a metric.** You are looking for: times that match the emails, no null place names, cancellations captured as cancellations. If more than ~3 of 20 are wrong, the problem is the pre-filter letting junk through — tighten that, not the prompt.

If there are no real rows by **1:00 AM**: say so at the checkpoint, the team switches to seeded data, and you stop debugging live sync. That is a decision, not a discussion.

---

## Hour 6 (2:00–4:00 AM) — Backfill and dedupe

8. **Check spend first:** `make spend`. If projected cost is over ~$12, cap the backfill to 18 months.
9. Full-history backfill: `python -m palate ingest.sync 3000` then `extract`.
10. **Dedupe repeats.** Same restaurant across vendors, or a confirmation plus a modification, can produce near-duplicate rows. Normalize `place_name_raw` (lowercase, strip "The ", strip trailing location suffixes) and collapse rows with the same normalized name within a 3-hour window, keeping the latest `status`.
11. If Calendar was skipped at hour 0, add it now.

---

## Your smoke check

Replace the stub in `palate/ingest/commands.py`:

```python
def check(args) -> None:
    from .vendors import classify
    cases = [
        ("noreply@resy.com", "Your reservation at Cotogna is confirmed", "resy"),
        ("no-reply@opentable.com", "Your table is booked", "opentable"),
        ("orders@exploretock.com", "Your Tock reservation", "tock"),
        ("news@resy.com", "The 10 hottest new restaurants", None),  # marketing → drop
        ("hello@substack.com", "This week in food", None),
    ]
    for sender, subject, expected in cases:
        got = classify(sender, subject)
        assert got == expected, f"{sender!r}/{subject!r}: expected {expected}, got {got}"
    print(f"ingest.check OK ({len(cases)} fixtures)")
```

Add fixtures as you find real senders. **`make check` must pass before every push** — a broken check blocks the team's merge.

## Commands you expose

```python
COMMANDS = {
    "sync":    lambda a: print(f"{run_sync(int(a[0]) if a else 500)} messages"),
    "filter":  lambda a: print(prefilter.run()),
    "extract": lambda a: print(f"{extract_pending()} visits"),
    "check":   check,
}
```

## If it goes wrong

| Symptom | Move |
|---|---|
| Consent screen blocks you | Testing mode + presenter as test user. If still stuck 45 min in, escalate — this is the gate |
| Inbox too thin for a good profile | Switch to whoever on the team books the most. Decide by 8:30 PM, not midnight |
| Gmail API quota | Batch `messages.get`, cache aggressively; you only need one full sync |
| Extraction returning junk | Tighten the pre-filter. Never loosen `valid_visit` |
| Nothing works by 1:00 AM | Seeded data. Say it out loud, then help D with rationale generation |
