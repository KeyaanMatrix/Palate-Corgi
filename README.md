# Palate

**TripAdvisor tells you what strangers liked. This knows what _you_ liked.**

Palate extracts a taste graph from the reservations, cancellations, calendar
entries, and saved lists someone already created. It turns that revealed
behavior into a trip where every stop includes a reason grounded in something
the person actually did.

Built at the Corgi × Merge × Photon overnight hackathon.

## What is working

- Gmail and Calendar sync with sender-scoped pre-filtering, structured
  extraction, cross-source deduplication, and no raw-message dependency after
  extraction.
- A pure-SQL Taste Profile with evidence for every rendered number.
- Merge File Storage EXIF and Knowledge Base enrichment, plus Merge Link token
  exchange.
- Google Places discovery with durable SQLite caching and an honest offline
  fallback.
- Deterministic itinerary filtering, ranking, one intentional stretch, and one
  negative recommendation.
- A Spectrum/Photon iMessage path with persisted message-to-stop mappings:
  `👎` swaps one stop, `👍` locks it, and state texts re-plan only the future.
- A static judge-facing submission page in [`web/`](web/).

## Run it without credentials

Python 3.11+ and Node 20+ are recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install \
  -r requirements/base.txt \
  -r requirements/a.txt \
  -r requirements/b.txt \
  -r requirements/c.txt \
  -r requirements/d.txt

PALATE_DB=./palate.demo.db make seed
PALATE_DB=./palate.demo.db python -m palate profile.plain
PALATE_DB=./palate.demo.db python -m palate chat.preview Lisbon 1
python -m http.server 4173 --directory web
```

The preview uses the real profile, planner, swap, and re-plan code. It does not
send a message or require a network call.

## Verify the integrated build

```bash
PALATE_DB=./palate.check.db make PY=.venv/bin/python check
make PY=.venv/bin/python doctor
cd palate/chat/bridge && npm install && node --check server.mjs
```

`make check` applies the schema, runs every package smoke check, then runs the
isolated integration suite. `make doctor` reports which live integrations are
ready without printing any secrets.

## Connect real data

Copy [`.env.example`](.env.example) to `.env`, then provide the credentials
reported by `make doctor`.

```bash
# Gmail + Calendar → normalized visits
python -m palate ingest.sync 500
python -m palate ingest.calendar 24
python -m palate ingest.filter
python -m palate ingest.extract 20
python -m palate ingest.dedupe

# Rebuild and inspect every line before it is shown
python -m palate profile.build
python -m palate profile.plain
python -m palate profile.evidence cancellation_threshold

# Optional Merge enrichment
python -m palate enrich.exchange <merge-link-public-token>
# Save each returned token under its matching category in .env:
# MERGE_KNOWLEDGEBASE_ACCOUNT_TOKEN=... (Notion)
# MERGE_FILESTORAGE_ACCOUNT_TOKEN=...  (Drive)
python -m palate enrich.notion
python -m palate enrich.drive 200

# Planner and local rehearsal
python -m palate plan.itinerary Lisbon 3
python -m palate chat.preview Lisbon 1
```

For iMessage, install the bridge dependencies, expose port `8000`, register
`/photon/webhook` with Spectrum, and start both services:

```bash
cd palate/chat/bridge && npm install && cd ../../..
python -m palate chat.serve
# in another terminal
ngrok http 8000
```

Then send the first itinerary:

```bash
python -m palate chat.demo +15551234567 Lisbon
```

The exact rehearsal, fallback, and recording sequence is in
[`docs/demo-runbook.md`](docs/demo-runbook.md).

## Architecture

```text
Gmail + Calendar ─┐
Drive EXIF ───────┼─> visit ledger ─> sourced Taste Profile
Notion lists ─────┘                         │
                                            v
Google Places cache ─> filter aversions ─> itinerary
                                            │
                                            v
                                Spectrum/Photon iMessage
                              tapback swap + state re-plan
```

All model calls go through [`palate/llm.py`](palate/llm.py). The default route
is Merge Gateway; `LLM_DIRECT=1` is the explicit emergency fallback. Profile
math, itinerary mutation, webhook routing, and offline planning do not need a
model call.

## Product and engineering documents

- [`prd.md`](prd.md) — thesis, constraints, submission, and demo.
- [`docs/TRD.md`](docs/TRD.md) — contracts, schema, and architecture.
- [`docs/trd-a-ingest.md`](docs/trd-a-ingest.md) — Gmail and Calendar ingest.
- [`docs/trd-b-profile.md`](docs/trd-b-profile.md) — evidence-backed profile.
- [`docs/trd-c-photon.md`](docs/trd-c-photon.md) — iMessage control surface.
- [`docs/trd-d-gateway-plan.md`](docs/trd-d-gateway-plan.md) — Gateway,
  enrichment, Places, and planning.
