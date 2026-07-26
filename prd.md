# PRD — Personalized Itinerary Agent

**Working title:** Palate (alternates: Revisit, Second Time, Regular)

**One line:** TripAdvisor tells you what strangers liked. This knows what *you* liked.

**Status:** Hackathon build spec — 12hr event, ~10hr remaining at time of writing
**Revision:** v2 — corrects the data-source architecture. v1 assumed Merge brokered Gmail/Calendar. It does not.
**Stack partners in play:** Google APIs (primary corpus), Merge (File Storage + Knowledge Base enrichment), Photon (iMessage interface), Anthropic API (extraction + generation), Google Places (resolution)

---

## 1. Thesis

Every travel recommendation product is a popularity engine. TripAdvisor, Google Maps, Yelp, and every "AI trip planner" shipped in the last two years answer the same question: *what do most people rate highly here?* The output is the median tourist's day, and it is why every recommended itinerary in a city looks identical.

The signal that would actually personalize a trip already exists and nobody uses it: a decade of reservation confirmations, ticket purchases, and calendar entries. That corpus is more honest about taste than anything a user would self-report on an onboarding survey — it records what they *did*, repeatedly, with their own money, including the things they'd never claim to like.

**Core claim:** taste is recoverable from transactional history, and an itinerary built from recovered taste feels authored rather than aggregated.

**Second claim, and the actual differentiator:** model what the user *avoids*, not just what they like. Cancellations, one-visit-never-returned places, booked-and-skipped morning activities. Every recommender models preference. None model revealed distaste. Distaste is what makes a recommendation feel like it came from someone who knows you.

---

## 2. Users

**Primary (demo + wedge):** high-frequency urban diner-out, 25–40, books through Resy/OpenTable/Tock, buys event tickets, travels 3–6× a year, and has a strong sense of personal taste that no travel product has ever reflected back at them. This person does not want the top ten things in Lisbon. They want the version of Lisbon that matches how they already live.

**Non-user, explicitly:** the once-a-year family vacation planner. Low signal density, high sensitivity to logistics and price, and the value prop ("we know your taste") is weak because they have no strong revealed pattern.

---

## 3. Product surface

Two artifacts. Everything else is out of scope.

### 3.1 The Taste Profile

The first thing the user sees, before any recommendation. A short, specific, uncomfortably accurate read of their habits, derived entirely from parsed data, each line backed by a citable count.

Example shape:

> You book Tuesdays and Wednesdays, almost always between 8:30 and 9:15pm.
> Parties of two. 23 of your last 30 reservations.
> You go back. Three visits before you'll try somewhere new — you've been to the same six places 41 times this year.
> You have never once scheduled anything before 11am on a trip. You booked a 9am tour in Mexico City and cancelled it the night before.
> You cancel above $180/head. Four for four.
> You sit at the bar. Every solo reservation in two years was a bar seat.

**This is the demo.** The itinerary is proof the profile was right. Concentrate design and copy effort here, not on the trip view.

### 3.2 The Itinerary

A day-by-day plan for a named destination where every stop carries a **because**, traced to a specific parsed behavior — not a genre label.

Bad: *Recommended because you like Italian food.*
Good: *Because you've been to Cotogna four times and always at the counter — this is the one counter-service place in Lisbon that operates the same way. Booked Wednesday 8:45, which is your slot.*

Requirements:
- Nothing scheduled before the user's revealed earliest-activity hour
- Price bands capped at revealed cancellation threshold, with an explicit note when a stop is deliberately above it
- Density matched to revealed pace (stops per day, gap length between them)
- At least one stop flagged as a **deliberate stretch**, with reasoning stated: *this is outside your pattern, here's why I think you'd go anyway.* Ships the model's judgment, not just its retrieval.
- One **negative recommendation** per city: the highly-rated obvious thing it tells you to skip, reason drawn from your own history. This is the line judges will remember.

---

## 4. Interface: Photon / iMessage

The itinerary is used *while traveling*, on a phone, and the day falls apart constantly. That is the entire justification for iMessage over a web app — not novelty.

**Interactions, in priority order:**

1. **Tapbacks as the control surface.** Each proposed stop arrives as its own message. Thumbs-down swaps that single stop without disturbing the rest of the day. Thumbs-up locks it. Zero typing.
2. **Re-plan on natural language state.** "raining", "we're wrecked", "still at lunch", "museum was closed" → re-plans the remainder of the day only, preserving locked stops.
3. **Unprompted morning send.** Today's plan arrives at the revealed wake-adjacent hour, not at 7am.
4. **Forwardable output.** Every stop message is written to be forwarded to a travel companion as-is — no "here's your itinerary" preamble, no agent voice wrapping.

**Explicitly out of scope:** a general chat agent over text. If it answers arbitrary questions it becomes a worse Claude app and the Photon prize argument collapses.

---

## 5. Data

### 5.1 Correction: what Merge actually is

Merge is a B2B unified API. Its categories are HRIS, ATS, CRM, Accounting, Ticketing, File Storage, Knowledge Base, and Chat. **There is no email category and no calendar category.** It also does not provide camera roll photos or iMessage history.

Consequences:
- The reservation-confirmation corpus comes from **Gmail API directly** (`gmail.readonly`), not Merge. Google OAuth is a well-trodden 30-minute path. Calendar likewise via **Google Calendar API**.
- Merge's role is real but **enrichment, not critical path** — see 5.2. Do not put Merge on the hour-0 critical path, and do not let the Merge prize argument drive the architecture into something that doesn't work.

### 5.2 Sources and honest assessment

| Source | Access | Signal | Priority |
|---|---|---|---|
| Gmail | Google API direct | Reservation confirms, **cancellations**, ticket purchases, hotel/flight receipts | **Critical — this is the product** |
| Calendar | Google API direct | Pace, gaps, trip date ranges, deletions | High |
| File Storage (Drive/Dropbox/Box) | **Merge** | Photo EXIF: timestamp + geotag → places visited with no booking trail | Medium |
| Knowledge Base (Notion) | **Merge** | Saved restaurant lists, trip notes — *declared* taste, to contrast against revealed | Medium, high demo value |
| Chat (Teams) | **Merge** | Place recommendations exchanged in messages | Low, skip tonight |
| HRIS / ATS / CRM / Accounting | Merge | Irrelevant here | Skip |

The Notion angle is worth more than its build cost: a saved list of aspirational restaurants the user never actually went to is the cleanest possible demonstration of declared-vs-revealed preference. *You saved 14 places to this list. You went to two. Here's what your list says about who you think you are, and what your calendar says about who you are.* That is the most human line available in this dataset and it exists only because Merge is in the stack.

**Verify in the first 20 minutes:** whether Merge Link's File Storage and Knowledge Base connectors authorize *personal* Google Drive / Notion accounts, or workspace-only. If workspace-only, the Merge track degrades to whatever the team's own work accounts hold, and the Notion line above may not survive. Have this answer before anyone builds against it.

### 5.3 Extraction target schema

```
visit
  id
  source                -- gmail | calendar | drive_exif | notion
  source_ref
  vendor                -- resy | opentable | tock | eventbrite | airline | hotel | unknown
  place_name_raw
  place_id              -- resolved later, nullable
  city
  category              -- restaurant | bar | event | lodging | activity
  cuisine[]             -- nullable
  price_band            -- 1..4, from receipt total / party_size where available
  party_size
  scheduled_at          -- local datetime
  booked_at             -- lead-time signal
  status                -- confirmed | cancelled | modified | attended_unbooked
  cancelled_at          -- nullable, feeds distaste model
  is_travel             -- inferred: city != home_city
  intent_only           -- true for Notion saves never matched to a visit
```

```
taste_profile
  home_city
  earliest_activity_hour       -- p5 of scheduled_at hour
  peak_dining_hour             -- mode
  preferred_days[]
  typical_party_size
  price_ceiling                -- highest confirmed band
  cancellation_threshold       -- min price_band where cancel rate > 0.5
  revisit_ratio                -- repeat visits / distinct places
  novelty_appetite             -- derived: low | medium | high
  cuisine_affinity{}           -- weighted by repeat count, not raw count
  cuisine_aversion[]           -- tried once, never returned, >=N alternatives available
  booking_lead_time_median
  seat_preference              -- bar | table | unknown
  pace                         -- stops per active day
  avoided_categories[]         -- booked-then-cancelled, or saved-never-visited
  aspiration_gap[]             -- Notion saves with no matching visit
```

### 5.4 Extraction approach

Two-stage. The split matters for both cost and reliability:

- **Stage 1 — deterministic pre-filter.** Match sender domains and subject patterns for the top ~15 booking vendors. Cheap, fast, cuts LLM call volume by an order of magnitude. Anything unmatched is dropped rather than sent to the model — recall is not the constraint tonight, precision is.
- **Stage 2 — LLM structured extraction.** Batch matched messages, extract to the `visit` schema with strict JSON output, one call per ~20 messages. Discard rows failing schema validation rather than repairing them.

**Profile computation is pure SQL/pandas over the visit table. No model involvement.** The model's only jobs are extraction (Stage 2) and prose generation (profile copy, stop rationales). Every number in the profile must trace to a row count, because the one thing that kills this demo is a profile line the presenter knows is wrong.

### 5.5 Resolution

Google Places text search on `place_name_raw + city` for candidate discovery in the destination city. Filter candidates by profile constraints *before* ranking. Do this last — nearly free, not where the risk lives.

---

## 6. Architecture

```
Google APIs (Gmail, Calendar)        Merge (File Storage, Knowledge Base)
        │ OAuth + sync                        │ Merge Link + sync
        ▼                                     ▼
   raw_message store              EXIF extract  /  Notion list parse
        │                                     │
        ▼                                     │
 vendor pre-filter (rules)                    │
        │                                     │
        ▼                                     │
 LLM batch extraction ──────► visit table ◄───┘
                              (SQLite)
                                   │
                                   ▼
                    profile computation (deterministic)
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   profile copy gen        candidate retrieval      itinerary assembly
        (LLM)              (Google Places)        (constraints + rationale)
          │                                                 │
          └──────────────► Photon / iMessage ◄──────────────┘
                          (tapback handlers, re-plan)
```

Single service, SQLite is fine, no queue, no auth system, no accounts. Session state keyed by phone number.

---

## 7. Build plan — 10 hours, 4 people

Front-load the only real risk: **Gmail OAuth + sync + extraction working end to end on one real inbox.** Everything else is recoverable; that is not. Merge runs as a parallel track owned by one person who is not on the critical path.

| Hour | Owner A — Data | Owner B — Profile | Owner C — Photon | Owner D — Merge + generation |
|---|---|---|---|---|
| 0–2 | Google OAuth, Gmail sync, raw store landing | Vendor pattern list, schema + SQLite migrations | Photon hello-world, inbound/outbound, tapback events | **Verify Merge personal-account support**, then Link flow + Places wrapper |
| 2–4 | Pre-filter + LLM extraction → visit rows | Profile metrics on seed data | One-stop-per-message formatting | Drive EXIF → visit rows; Notion list → intent_only rows |
| 4–6 | **Gate: real inbox → real visit rows** | Distaste metrics (cancellations, one-and-done) | Tapback → swap handler | Aspiration-gap computation; profile copy prompt |
| 6–8 | Backfill full history, dedupe repeats | Profile v2 on real data, sanity-check every number | Re-plan on text state | Itinerary assembly: constraint filter then rationale gen |
| 8–9 | Freeze | Freeze | Fallback thread pre-loaded | Demo script, rehearse twice |
| 9–10 | Buffer / bugfix only | | | |

**Hard gates:**
- **Hour 0:20** — Merge personal-account question answered. If negative, Owner D drops the Merge track to EXIF-only and moves to generation.
- **Hour 4** — real inbox produces real visit rows. If not, switch to seeded data immediately and stop trying to fix live sync.
- **Hour 8** — feature freeze, no exceptions. Remaining time is rehearsal and bugfix.
- **Hour 9** — fully pre-loaded fallback thread on a phone that has already run the whole flow successfully.

---

## 8. Demo script (3 min)

1. **Hook, spoken:** "Every travel app tells you what strangers liked. Watch this tell me what I liked, from data I never gave it on purpose."
2. **Connect** — live OAuth on the presenter's own accounts. Pre-warmed, so the profile appears in seconds.
3. **Profile reveal.** Read three lines aloud. Land on the cancellation line — a specific dollar threshold with a 4-for-4 count is the moment.
4. **The aspiration gap.** "It also read my saved-places list. I saved 14. I went to 2." One sentence, biggest emotional hit in the demo.
5. **Ask for a city.** Judge picks. Itinerary arrives in iMessage on screen, one stop per message.
6. **The negative recommendation.** "It's telling me to skip the single most-reviewed restaurant in that city, and here's the reason from my own history."
7. **Tapback a stop down.** Single stop swaps, rest of day intact. No typing.
8. **Break the day.** Text "it's raining." Afternoon re-plans, locked stops preserved.
9. **Close on thesis:** popularity engines vs. a taste graph that compounds per user.

**Do not** offer to run this live on a judge's inbox. Their profile will be sparse, their vendors unmatched, and one wrong line about a stranger destroys the credibility the whole demo rests on.

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Gmail OAuth scope review / verification friction | **Critical** | Test-user mode on an unverified app is fine for a demo; confirm in first 20 min |
| Presenter inbox too sparse for a compelling profile | High | Verify volume in the first 30 minutes. If thin, use whoever on the team books most |
| Extraction precision poor → wrong profile numbers | High | Deterministic pre-filter; drop rather than repair; eyeball 20 rows before trusting any metric |
| Merge personal-account limitation kills the Notion line | Medium | Answered at hour 0:20; EXIF-only fallback; demo does not depend on it |
| Live sync stalls on stage | High | Pre-loaded fallback thread, phone in hand, already run end to end |
| Agent drifts into generic chatbot | Medium | Hard scope: tapbacks + re-plan only. No open Q&A |
| Trust objection: "you read my whole inbox" | Medium | Real answer: sender-scoped extraction, extract-then-discard, no raw message retention |

---

## 10. Out of scope tonight

Accounts, settings, web UI, companion/multi-user threads, bookings or payments, flights, budget optimization, maps rendering, Chat category, any Merge category outside File Storage and Knowledge Base.

---

## 11. Prize alignment

- **Overall best:** real product thesis, working pipeline, defensible technical claim (revealed-taste extraction + distaste modeling), demo where the artifact appears live.
- **Merge-specific:** File Storage EXIF adds visits with no booking trail; Knowledge Base produces the declared-vs-revealed contrast that is the single best line in the demo. Be honest on stage that Gmail is direct — claiming Merge does email in front of Merge engineers is the one unrecoverable mistake available tonight.
- **Photon:** tapback-as-control-surface and mid-trip re-plan are iMessage-native, not a chat wrapper — the interface is load-bearing.
- **"Make it feel human":** the output is an act of noticing. It tells you something true about yourself you never told it, then acts on it with restraint.

---

## 12. If it continues past tonight

The itinerary is the wedge, not the business. The asset is the **taste graph**: a per-user structured model of revealed preference *and* revealed aversion, extracted from transactional history, compounding with every booking.

Direction worth testing first: this is a better acquisition surface for restaurants and events than any ad product, because intent is inferred rather than declared — and the aversion model lets you promise not to send someone something they'd hate, which no ad network can.

Open questions before committing real time:
- Does inbox OAuth clear consumer trust at scale, or does it cap the funnel? Trust architecture is the founder-fit strength here — treat it as the first-class problem, not a footnote.
- Vendor coverage: how many booking platforms before profile quality is good enough for the median target user?
- Cold start on thin history — graceful degradation, or is this only for high-frequency bookers?
- **Kill criterion:** if a major booking platform (Resy/Amex, OpenTable) ships revealed-taste recommendations off first-party data, the neutral cross-vendor position is the only remaining edge. Verify none has, before week two.
- **Kill criterion:** if Google ships taste-based Places recommendations off Gmail + Maps history, this is dead on arrival. They have strictly more data and the same idea. Check before week two.
