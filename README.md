# Palate

**TripAdvisor tells you what strangers liked. This knows what *you* liked.**

A taste graph extracted from transactional history — a decade of reservation confirmations, cancellations, and calendar entries — turned into an itinerary where every stop carries a *because* traced to something you actually did.

Built at the Corgi × Merge × Photon overnight hackathon.

## Documents

- **[prd.md](prd.md)** — what we're building and why.
- **[docs/TRD.md](docs/TRD.md)** — architecture, contracts, branch/merge protocol. **Read §1–§6 before you write code.**
- Sub-TRDs, one per laptop: [A — ingest](docs/trd-a-ingest.md) · [B — profile](docs/trd-b-profile.md) · [C — Photon](docs/trd-c-photon.md) · [D — Gateway + plan](docs/trd-d-gateway-plan.md)

## Setup

```bash
git checkout <your-branch>          # a-ingest | b-profile | c-photon | d-gateway-plan
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/base.txt -r requirements/<your-letter>.txt
cp .env.example .env                # fill it in — see TRD §6
make seed                           # 30 fake visits; nobody is blocked on anyone
make check                          # must pass before every push
```

## The two rules that keep four laptops mergeable

1. **Only edit files you own** (TRD §2). Ownership is disjoint by design, so conflicts should be impossible. If you hit one, someone edited outside their lane — get them, don't guess.
2. **`make check` passes before every push.** It takes ten seconds and a broken check blocks everyone's merge.

Integration checkpoints are wall-clock, not "when I'm ready": **9:30 PM, 11:30 PM, 2:00 AM, and a 4:00 AM freeze.** Submission is 6:00 AM.
