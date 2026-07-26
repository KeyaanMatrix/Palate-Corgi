# TRD — Palate

**Technical requirements for the PRD in `/prd.md` (v3).** This is the master document: architecture, contracts, and the rules that let four laptops merge cleanly. Each owner also has a sub-TRD with their exact build steps:

| Owner | Branch | Sub-TRD | Owns |
|---|---|---|---|
| A — Data | `a-ingest` | [trd-a-ingest.md](trd-a-ingest.md) | `palate/ingest/` |
| B — Profile | `b-profile` | [trd-b-profile.md](trd-b-profile.md) | `palate/profile/` |
| C — Photon | `c-photon` | [trd-c-photon.md](trd-c-photon.md) | `palate/chat/`, `web/` |
| D — Gateway + Plan | `d-gateway-plan` | [trd-d-gateway-plan.md](trd-d-gateway-plan.md) | `palate/llm.py`, `palate/enrich/`, `palate/plan/` |

Read **§1–§6 of this document before opening your sub-TRD.** Everything in §3 (contracts) is frozen — if you need it changed, that is a conversation with the whole team, not a commit.

---

## 1. Stack, and why

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Everyone knows it; Google/Anthropic SDKs are first-class |
| Store | SQLite via stdlib `sqlite3` | Zero setup, one file, trivially inspectable at 3 AM |
| Profile math | **Pure SQL + stdlib `statistics`** | No pandas. Fewer wheels to fight at 2 AM, and PRD §5.4 requires every number trace to a row count |
| Model calls | `anthropic` SDK, `claude-opus-5`, pointed at **Merge Gateway** via `base_url` | One wrapper file, one env flag to fall back |
| Web | FastAPI + uvicorn | Photon needs an inbound webhook; nothing else needs a server |
| Google | `google-auth-oauthlib` + `google-api-python-client` | Well-trodden OAuth path |
| Submission page | Static HTML on Vercel | Built post-freeze; not a product surface (PRD §10) |

**Dependency rule:** each owner has their own `requirements/<letter>.txt`. Nobody edits a shared requirements file — that is a guaranteed merge conflict at 2 AM. `requirements/base.txt` is frozen at the base commit.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/base.txt -r requirements/a.txt   # your letter
cp .env.example .env                                          # then fill it in
make db                                                       # create palate.db
```

---

## 2. Repository layout — ownership is the point

Every file has exactly one owner. **Do not edit a file you do not own.** If you need a change in someone else's file, text them; a two-minute wait beats a merge conflict.

```
palate/
  config.py        BASE — frozen. Env vars, paths.
  db.py            BASE — frozen. Connection, migrations, JSON helpers.
  contracts.py     BASE — frozen. Dataclasses + field lists + the cross-owner signatures.
  cli.py           BASE — frozen. Auto-discovers subcommands; never needs editing.
  llm.py           OWNER D — Merge Gateway wrapper. A and B call it, never edit it.

  ingest/          OWNER A          profile/         OWNER B
    commands.py                       commands.py
    google_auth.py                    metrics.py
    gmail_sync.py                     distaste.py
    calendar_sync.py                  copy.py
    vendors.py                        build.py
    prefilter.py
    extract.py

  chat/            OWNER C          enrich/          OWNER D
    commands.py                       commands.py     (shared with plan/)
    photon.py                         merge_link.py
    app.py                            filestorage_exif.py
    format.py                         knowledge_base.py
    session.py
    replan.py                       plan/            OWNER D
                                      places.py
web/               OWNER C            candidates.py
  index.html                          assemble.py
                                      rationale.py

schema.sql         BASE — frozen after the base commit. Additive-only changes, announced.
seed/seed.sql      BASE — fake visits so B, C, D can work before A's pipeline lands.
requirements/      base.txt frozen; a.txt / b.txt / c.txt / d.txt owned per-letter.
docs/              This TRD + four sub-TRDs.
```

### Why `cli.py` never changes

It discovers subcommands by importing `palate.<package>.commands` and reading a `COMMANDS` dict. Adding a command means editing **your own** `commands.py`. The shared entry point is never touched, so it can never conflict.

```python
# palate/ingest/commands.py  (Owner A's file)
COMMANDS = {
    "sync": lambda args: run_sync(limit=int(args[0]) if args else 500),
    "extract": lambda args: extract_pending(),
}
```

```bash
python -m palate ingest.sync 500
python -m palate profile.build
python -m palate plan.itinerary Lisbon 3
```

---

## 3. Contracts — frozen at the base commit

These are the seams between owners. They are in `palate/contracts.py` and `schema.sql` on `main` **before anyone branches**, so all four branches share a common ancestor for every shared file. Changing one after 9:30 PM requires telling the other three.

### 3.1 The data contract — `visit`

Every row in `visit` is one thing the user did or intended to do. A writes them (Gmail/Calendar); D also writes them (Drive EXIF, Notion). B only reads.

```sql
CREATE TABLE visit (
  id                TEXT PRIMARY KEY,   -- sha256(source|source_ref|place_name_raw|scheduled_at)[:32]
  source            TEXT NOT NULL,      -- gmail | calendar | drive_exif | notion
  source_ref        TEXT,               -- provider message/event/file id
  vendor            TEXT,               -- resy | opentable | tock | eventbrite | airline | hotel | unknown
  place_name_raw    TEXT NOT NULL,
  place_id          TEXT,               -- Google Places, resolved late, nullable
  city              TEXT,
  category          TEXT,               -- restaurant | bar | event | lodging | activity
  cuisine           TEXT,               -- JSON array, nullable
  price_band        INTEGER,            -- 1..4, nullable
  party_size        INTEGER,
  scheduled_at      TEXT,               -- ISO-8601 local, 'YYYY-MM-DDTHH:MM'
  booked_at         TEXT,               -- ISO-8601, lead-time signal
  status            TEXT NOT NULL,      -- confirmed | cancelled | modified | attended_unbooked
  cancelled_at      TEXT,
  is_travel         INTEGER DEFAULT 0,  -- 0/1, inferred city != home_city
  intent_only       INTEGER DEFAULT 0,  -- 1 for Notion saves never matched to a visit
  seat              TEXT,               -- bar | table | unknown
  raw_total_cents   INTEGER,            -- receipt total when parseable
  created_at        TEXT NOT NULL
);
```

**Rules everyone must honour:**
- `id` is deterministic (see `contracts.visit_id()`), so re-running ingest is idempotent — `INSERT OR REPLACE`, never blind `INSERT`.
- `scheduled_at` is **local wall-clock time, no timezone suffix.** Every hour-of-day metric depends on this. Do not store UTC.
- A row with `status='cancelled'` still counts as a booking that was made — the distaste model needs it. Never delete it.
- Nullable means nullable. B must handle `None` on `price_band`, `city`, `party_size`, and `seat` without crashing.

### 3.2 The profile contract — `taste_profile`

B writes one row per computation (append-only, so you can diff runs). D and C read the latest via `profile.build.load_profile()`.

Stored as a JSON blob keyed by `TASTE_PROFILE_KEYS` in `contracts.py`:

```python
{
  "home_city": "San Francisco",
  "earliest_activity_hour": 11,          # p5 of scheduled hour
  "peak_dining_hour": 20,                # mode
  "preferred_days": ["Tue", "Wed"],
  "typical_party_size": 2,
  "price_ceiling": 3,
  "cancellation_threshold": 4,           # min band where cancel rate > 0.5; None if never
  "revisit_ratio": 1.9,
  "novelty_appetite": "low",             # low | medium | high
  "cuisine_affinity": {"italian": 0.31},
  "cuisine_aversion": ["sushi"],
  "booking_lead_time_median_days": 6,
  "seat_preference": "bar",
  "pace": 2.4,                           # stops per active day
  "avoided_categories": ["activity"],
  "aspiration_gap": [{"name": "Bar Mario", "saved_at": "..."}],
  "evidence": { "<metric>": {"n": 23, "of": 30, "note": "..."} }
}
```

**`evidence` is not optional.** Every headline number must have an entry with the row counts behind it. PRD §5.4: the one thing that kills this demo is a profile line the presenter knows is wrong. `contracts.py` ships an `Evidence` helper — use it.

### 3.3 The itinerary contract — D → C

D implements these three functions; C calls them and nothing else.

```python
def build_itinerary(profile: dict, city: str, days: int = 3) -> dict
def swap_stop(itinerary: dict, stop_id: str, reason: str | None = None) -> dict
def replan(itinerary: dict, from_iso: str, state_text: str) -> dict
```

All three take and return the same dict shape:

```python
{
  "id": "itin_a1b2c3",
  "city": "Lisbon",
  "created_at": "2026-07-25T21:40",
  "negative_recommendation": {"name": "...", "why": "..."},   # exactly one per city
  "days": [
    {"date": "2026-08-02", "stops": [
       {
         "id": "stop_x1",            # stable across swaps; C keys tapbacks on this
         "seq": 0,
         "name": "Taberna Sal Grosso",
         "category": "restaurant",
         "time": "20:45",
         "price_band": 2,
         "because": "You've been to Cotogna four times, always at the counter...",
         "is_stretch": False,        # exactly one True per itinerary
         "locked": False,            # C sets True on 👍
         "place_id": "ChIJ..."
       }
    ]}
  ]
}
```

**Invariants D must guarantee and C may rely on:**
- `swap_stop` changes exactly one stop, preserves every `stop.id` except the swapped one, and never touches a stop with `locked=True`.
- `replan` rewrites only stops at or after `from_iso`, preserves all `locked=True` stops, and preserves stop ids for anything it keeps.
- Exactly one stop across the whole itinerary has `is_stretch=True` (PRD §3.2).
- No stop is scheduled before `profile["earliest_activity_hour"]`.
- Both functions are **pure**: they take an itinerary and return a new one. C owns persistence.

### 3.4 The model contract — D → A, B

D owns `palate/llm.py`. A and B import it and never edit it.

```python
def complete_json(prompt: str, schema: dict, *, purpose: str, max_tokens: int = 8000) -> dict | None
def complete_text(prompt: str, *, purpose: str, max_tokens: int = 2000) -> str
```

- `purpose` is a free-text tag (`"extract"`, `"profile_copy"`, `"rationale"`) logged to the `llm_call` table for spend tracking against the $20 Gateway credit.
- `complete_json` returns `None` on schema-validation failure rather than raising or repairing. **Callers drop the row.** PRD §5.4: precision over recall.
- Routing: `MERGE_GATEWAY_BASE_URL` set → calls go through Merge Gateway. Unset or `LLM_DIRECT=1` → straight to Anthropic. One env var is the whole fallback.

---

## 4. Architecture

```
Google APIs (Gmail, Calendar)          Merge Unified API (Drive, Notion)
        │ OAuth + sync                          │ Merge Link
        ▼                                       ▼
   raw_message                        EXIF extract / Notion parse
        │                                       │
        ▼                                       │
 vendor pre-filter (deterministic rules)        │
        │                                       │
        ▼                                       │
 LLM batch extraction ──────────► visit ◄───────┘
   via palate/llm.py               (SQLite)
   → MERGE GATEWAY                   │
                                     ▼
                     profile computation (pure SQL, no model)
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
  profile copy gen           candidate retrieval          itinerary assembly
  via MERGE GATEWAY           (Google Places)          (constraints → rationale)
        │                                                         │
        └──────────────────► Photon / iMessage ◄──────────────────┘
                             (tapbacks, re-plan)
                                     │
                                     ▼
                        Vercel static page (submission only)
```

Single process, SQLite, no queue, no auth, no accounts. Session state keyed by phone number.

---

## 5. Branch and merge protocol

### 5.1 Setup (every laptop, before 7:30 PM)

```bash
git clone https://github.com/KeyaanMatrix/Palate-Corgi.git && cd Palate-Corgi
git checkout <your-branch>          # a-ingest | b-profile | c-photon | d-gateway-plan
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/base.txt -r requirements/<your-letter>.txt
cp .env.example .env
make db && make seed                # seed data so you can work before A's pipeline lands
make check                          # must pass before you start and before every push
```

### 5.2 The four rules

1. **Only touch files you own** (§2). Everything else is read-only to you.
2. **Rebase, never merge, on your branch.** `git pull --rebase origin main` before every push.
3. **Push to your branch at least once an hour.** An unpushed laptop is a single point of failure at 4 AM, and it's how work gets lost when someone's battery dies.
4. **Integration checkpoints are wall-clock, not "when I'm ready."**

### 5.3 Integration checkpoints

At each checkpoint, one person (Owner B, by default — the profile sits in the middle of every dependency) runs the merge in this order: **A → B → D → C**. That order is deliberate: it follows the data flow, so if something breaks you find out at the earliest layer.

| Time | Checkpoint | Gate |
|---|---|---|
| 9:30 PM | First integration | `make check` passes on merged `main`; contracts confirmed real, not theoretical |
| 11:30 PM | Second | Seeded end-to-end: profile → itinerary → iMessage message |
| 1:00 AM | **Hard gate (PRD §7)** | Real inbox → real visit rows. If not, switch to seeded data and stop debugging live sync |
| 2:00 AM | Third | Real profile numbers read aloud; itinerary assembly on real data |
| **4:00 AM** | **FREEZE** | Last merge to `main`. After this, only bugfix commits, and only with two people looking |

```bash
# The checkpoint merge (run by one person, on main)
git checkout main && git pull
for b in a-ingest b-profile d-gateway-plan c-photon; do
  git merge --no-ff origin/$b -m "integrate $b" || echo "CONFLICT in $b — get its owner"
done
make check && git push origin main
# then everyone: git checkout <branch> && git pull --rebase origin main
```

### 5.4 If you hit a conflict

You shouldn't — ownership is disjoint. If you do, it means someone edited outside their lane. **Do not resolve it yourself.** Get the other owner, resolve together, in under five minutes. A conflict resolved by guessing at 3 AM is how you lose the demo.

---

## 6. Environment

`.env.example` is committed; `.env` is gitignored. Fill this in before 7:30 PM.

```bash
# Anthropic — direct fallback path
ANTHROPIC_API_KEY=
LLM_MODEL=claude-opus-5
LLM_DIRECT=0                 # set to 1 to bypass Merge Gateway entirely

# Merge Gateway (critical path; $20 credit, code CORGI-CAFE)
MERGE_GATEWAY_BASE_URL=
MERGE_GATEWAY_API_KEY=

# Merge Unified API (enrichment: Drive EXIF, Notion)
MERGE_API_KEY=
MERGE_ACCOUNT_TOKEN=

# Google (Gmail + Calendar, test-user OAuth mode)
GOOGLE_CLIENT_SECRETS=./client_secret.json
GOOGLE_TOKEN_PATH=./.google_token.json
GOOGLE_PLACES_API_KEY=

# Photon ($25 credit, code Hackwithphoton)
PHOTON_API_KEY=
PHOTON_WEBHOOK_SECRET=
PHOTON_FROM_NUMBER=

# App
PALATE_DB=./palate.db
HOME_CITY=San Francisco
```

**Never commit `.env`, `client_secret.json`, `.google_token.json`, or `palate.db`.** They're in `.gitignore`; check `git status` before every commit anyway.

---

## 7. Cost control — the $20 Gateway credit

The full-history backfill is the only thing that can burn the credit. Rules:

- Batch **~20 messages per extraction call** (PRD §5.4). Never one call per message.
- The deterministic pre-filter runs first, always. Unmatched messages are dropped, not sent to the model.
- Before the full backfill (2:00 AM), run `python -m palate llm.spend` and look at the number. If projected spend exceeds ~$12, cap the backfill window to 18 months.
- Every model call is logged to `llm_call`. If spend looks wrong, that table tells you which `purpose` is eating it.

---

## 8. Testing — what "done" means

There is no test suite worth writing tonight. There are **five smoke checks**, wired into `make check`, and each owner owns one:

| Check | Owner | Passes when |
|---|---|---|
| `make check-db` | base | Schema applies to a fresh DB; seed loads |
| `make check-ingest` | A | Pre-filter classifies the 12 fixture subjects correctly |
| `make check-profile` | B | Profile builds on seed data; every headline key has an `evidence` entry |
| `make check-plan` | D | `build_itinerary` on seed profile returns a valid itinerary per §3.3 invariants |
| `make check-chat` | C | `format_stop()` renders a stop; `swap`/`replan` round-trip preserves locked stops |

`make check` runs all five. **It must pass before every push.** It takes under ten seconds; there is no excuse.

---

## 9. Failure modes and what to do

| If this breaks | Do this |
|---|---|
| Gmail OAuth won't clear consent screen | Test-user mode, add the presenter's address as a test user. If still stuck at 1:00 AM → seeded data, stop debugging |
| Merge Gateway erroring | `LLM_DIRECT=1` in `.env`. One line. Tell Owner D, keep building |
| Merge Link won't authorize personal Drive/Notion | Drop to EXIF-only, or drop the Unified API track entirely. The demo does not depend on it (PRD §5.2) |
| Extraction producing garbage rows | Tighten the pre-filter, not the prompt. Drop rows that fail schema; never repair |
| Photon webhook not receiving | Check the tunnel first (ngrok URL changes on restart), then the signature check |
| Profile number looks wrong | Stop. Trace it to a row count with `python -m palate profile.evidence <key>`. Do not ship a number you can't source |
| Venue wifi dies at 2 AM | Everything except live sync works offline against `palate.db`. Places results are cached in `place_cache` |
| It's 3:50 AM and something is half-finished | Freeze it anyway. A working demo of less beats a broken demo of more |

---

## 10. Post-freeze runbook (4:00 AM → 6:00 AM)

1. **4:00** — Freeze. `git tag freeze && git push --tags`. Nothing merges without two people agreeing.
2. **4:00–4:30** — Owner C: record the 60-second video (profile → city → itinerary in iMessage → tapback swap → "it's raining" re-plan). One take, no narration of features.
3. **4:00–4:45** — Owner B: `python -m palate profile.render > submission/profile.md`. Read every line. Anything you can't source, cut.
4. **4:30–5:15** — Owner C: build `web/index.html`, deploy to Vercel (`V0-CORGIMERGE30`). Static export, no backend.
5. **4:45–5:30** — Owner D: submission copy per PRD §8.1 — one-liner, six profile lines, video, three technical claims, real-vs-seeded note.
6. **5:30–5:50** — Owner A: submit. Screenshot the confirmation.
7. **5:50–6:00** — Buffer for submission-form friction only.
8. **6:00–7:15** — Sleep in shifts. One person owns the demo phone, charged, fallback thread loaded.
9. **7:15** — Presenter runs the flow once cold.
