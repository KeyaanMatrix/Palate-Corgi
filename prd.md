# PRD — Personalized Itinerary Agent

**Working title:** Palate (alternates: Revisit, Second Time, Regular)

**One line:** TripAdvisor tells you what strangers liked. This knows what *you* liked.

**Status:** Hackathon build spec — Corgi × Merge × Photon, 12hr overnight, 1000+ RSVPs
**Revision:** v3 — rebases the plan on the event's actual schedule and prize structure, and moves Merge onto the critical path via Gateway (LLM routing) rather than treating it as an enrichment side-track. v2 corrected the data-source architecture; v1 wrongly assumed Merge brokered Gmail/Calendar.
**Stack partners in play:** Google APIs (primary corpus), **Merge Gateway** (LLM routing — every model call), Merge (File Storage + Knowledge Base enrichment), Photon (iMessage interface), Google Places (resolution), Vercel (submission artifact)

---

## 0. Event constraints

Non-negotiables from the kickoff, because several of them change the plan:

| Constraint | Consequence |
|---|---|
| Build window **7:30 PM → 6:00 AM** (doors 6:00, presentation to 7:30) | ~10.5 hours of build, minus a 1:00–2:00 AM dinner break → **~9.5 hours of real work** |
| **6:00 AM hard stop — submit to be judged** | The submission artifact is the primary judged object. Judges review submissions *before* anyone demos |
| **Top 5 only demo, 7:30 AM.** Prizes 8:00 AM | You may never get a live demo. The submission must carry the thesis on its own |
| Teams of **3–4** | Build plan below is written for 4 with an explicit 3-person collapse |
| Everyone must be in **Startup School** | Verify for all members before 7:30 PM. Trivially fixable now, disqualifying later |
| Wifi: CORGI Guest / `woofwoof2024` | Assume it degrades at 2 AM with 1000 people on it. Cache aggressively; never let a demo path require a cold network round trip |

**Credits available — claim all three in the first 15 minutes, before the sign-up flows get congested:**

- **Merge Gateway — $20** ($10 on signup + $10 with code `CORGI-CAFE`). Plus **Merge Agent Handler**, generous free tier.
- **Photon Pro — $25**, code `Hackwithphoton`. Sign in at `app.photon.codes/sign-in`, create project, apply the code on the billings page.
- **Vercel — $30**, code `V0-CORGIMERGE30`. Expires 1 month after redemption.

**Judging bar, stated explicitly by the organizers:** *build something you'd be proud to show a room of YC Partners*, and *make it feel human — use AI to make something that expresses, not just executes.* The Taste Profile (§3.1) is the direct answer to the second one. It is the reason to build this rather than another workflow-wiring demo, and it should be the first thing a judge sees in the submission.

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

Merge positions itself as **the connectivity layer for AI**: connect your product or agents to external systems *and route to LLM models*, with auth, security, and observability built in. Three surfaces matter tonight, and they are not the same product:

1. **Merge Gateway** — LLM routing. Point model calls at Merge instead of directly at a provider. **This is the piece that belongs on the critical path**, and $20 of credit covers this workload comfortably.
2. **Merge Agent Handler** — an MCP endpoint that connects an agent to 200+ systems. Free tier.
3. **Merge Unified API** — the classic categories: HRIS, ATS, CRM, Accounting, Ticketing, File Storage, Knowledge Base, Chat. **There is no email category and no calendar category.** It does not provide camera roll photos or iMessage history.

Consequences:
- The reservation-confirmation corpus comes from **Gmail API directly** (`gmail.readonly`), not Merge. Google OAuth is a well-trodden 30-minute path. Calendar likewise via **Google Calendar API**.
- **Every LLM call — Stage 2 extraction, profile copy, stop rationales — routes through Merge Gateway.** This is a config-level change, not an architectural one, and it makes the Merge story true on the critical path rather than a bolt-on: the extraction pipeline literally does not run without it. Keep a direct-provider env flag as a one-line fallback if the Gateway misbehaves at 3 AM.
- Merge's *Unified API* role remains **enrichment, not critical path** — see 5.2. Do not let the Unified API prize argument drive the data architecture into something that doesn't work.

### 5.2 Sources and honest assessment

| Source | Access | Signal | Priority |
|---|---|---|---|
| Gmail | Google API direct | Reservation confirms, **cancellations**, ticket purchases, hotel/flight receipts | **Critical — this is the product** |
| Calendar | Google API direct | Pace, gaps, trip date ranges, deletions | High |
| File Storage (Drive/Dropbox/Box) | **Merge Unified API** | Photo EXIF: timestamp + geotag → places visited with no booking trail | Medium |
| Knowledge Base (Notion) | **Merge** | Saved restaurant lists, trip notes — *declared* taste, to contrast against revealed | Medium, high demo value |
| Chat (Teams) | **Merge** | Place recommendations exchanged in messages | Low, skip tonight |
| HRIS / ATS / CRM / Accounting | Merge Unified API | Irrelevant here | Skip |
| **All model calls** | **Merge Gateway** | Not a data source — the routing layer for extraction and generation | **Critical path** |

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
- **Stage 2 — LLM structured extraction, routed through Merge Gateway.** Batch matched messages, extract to the `visit` schema with strict JSON output, one call per ~20 messages. Discard rows failing schema validation rather than repairing them. Batch size is also the cost control on the $20 Gateway credit — check spend before kicking off the full backfill.

**Profile computation is pure SQL/pandas over the visit table. No model involvement.** The model's only jobs are extraction (Stage 2) and prose generation (profile copy, stop rationales). Every number in the profile must trace to a row count, because the one thing that kills this demo is a profile line the presenter knows is wrong.

### 5.5 Resolution

Google Places text search on `place_name_raw + city` for candidate discovery in the destination city. Filter candidates by profile constraints *before* ranking. Do this last — nearly free, not where the risk lives.

---

## 6. Architecture

```
Google APIs (Gmail, Calendar)        Merge Unified API (File Storage, Knowledge Base)
        │ OAuth + sync                        │ Merge Link + sync
        ▼                                     ▼
   raw_message store              EXIF extract  /  Notion list parse
        │                                     │
        ▼                                     │
 vendor pre-filter (rules)                    │
        │                                     │
        ▼                                     │
 LLM batch extraction ──────► visit table ◄───┘
   via MERGE GATEWAY          (SQLite)
                                   │
                                   ▼
                    profile computation (deterministic)
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   profile copy gen        candidate retrieval      itinerary assembly
   via MERGE GATEWAY        (Google Places)        (constraints + rationale)
          │                                                 │
          └──────────────► Photon / iMessage ◄──────────────┘
                          (tapback handlers, re-plan)
                                   │
                                   ▼
                       Vercel — static profile page
                        (submission artifact only)
```

Single service, SQLite is fine, no queue, no auth system, no accounts. Session state keyed by phone number.

All model traffic goes through **Merge Gateway** behind a single client wrapper with a direct-provider fallback flag. One file, swappable in thirty seconds if the Gateway is the thing that breaks.

The **Vercel** deployment is not a product surface — it is a permalink for the 6:00 AM submission (§8.1): the profile, the itinerary, and a 60-second video, in one page a judge can open without a phone in front of them. Static export, no backend, built in the freeze window.

---

## 7. Build plan — wall clock, 4 people

Front-load the only real risk: **Gmail OAuth + sync + extraction working end to end on one real inbox.** Everything else is recoverable; that is not. The Merge *Unified API* track runs in parallel, owned by one person off the critical path. Merge *Gateway* is critical path but is thirty minutes of work, done at the start.

Times are actual clock times, not elapsed hours. The 1:00–2:00 AM dinner break is real — plan around it rather than through it, and use it to sanity-check profile numbers out loud with someone who is not the person who wrote the query.

| Clock | Owner A — Data | Owner B — Profile | Owner C — Photon | Owner D — Merge + generation |
|---|---|---|---|---|
| **6:00–7:30 PM** (before build) | Everyone: claim all three credits, confirm Startup School membership, Google Cloud project + OAuth consent screen in test-user mode, pick the presenter inbox | | | |
| 7:30–9:30 PM | Google OAuth, Gmail sync, raw store landing | Vendor pattern list, schema + SQLite migrations | Photon hello-world, inbound/outbound, tapback events | Merge Gateway wired + smoke-tested; **verify Merge personal-account support**; Places wrapper |
| 9:30–11:30 PM | Pre-filter + LLM extraction → visit rows | Profile metrics on seed data | One-stop-per-message formatting | Merge Link flow; Drive EXIF → visit rows; Notion list → intent_only rows |
| 11:30 PM–1:00 AM | **Gate: real inbox → real visit rows** | Distaste metrics (cancellations, one-and-done) | Tapback → swap handler | Aspiration-gap computation; profile copy prompt |
| **1:00–2:00 AM** | Dinner. Read the profile aloud to the table — every line that sounds wrong is a bug you would otherwise ship | | | |
| 2:00–4:00 AM | Backfill full history, dedupe repeats | Profile v2 on real data, sanity-check every number | Re-plan on text state | Itinerary assembly: constraint filter then rationale gen |
| **4:00 AM — FREEZE** | Freeze | Freeze | Fallback thread pre-loaded and run end to end | Freeze |
| 4:00–5:30 AM | Bugfix only | Record the 60s video | Vercel submission page | Write submission copy |
| 5:30–6:00 AM | **Submit.** Buffer for submission-form friction only | | | |
| 6:00–7:30 AM | Sleep in shifts. One person stays awake owning the demo phone | | | |
| 7:30 AM | Demo if top 5 | | | |

**Three people instead of four:** cut the Merge Unified API track entirely — Gateway stays (it is on the critical path and nearly free to wire), EXIF and Notion go. Owner D's generation work moves to Owner B. The aspiration-gap line in §3.1 and §8 is the casualty; the demo still stands without it.

**Hard gates:**
- **7:50 PM** — Merge personal-account question answered. If negative, Owner D drops the Unified API track to EXIF-only, or entirely, and moves to generation.
- **8:00 PM** — Merge Gateway confirmed serving live model calls, or the direct-provider flag flips and the Gateway becomes a post-freeze retry.
- **1:00 AM** — real inbox produces real visit rows. If not, switch to seeded data immediately and stop trying to fix live sync. This is a decision, not a discussion.
- **4:00 AM — feature freeze, no exceptions.** Two hours to submission is not slack; it is the time it takes to record, write, deploy, and submit while exhausted.
- **6:00 AM — submitted.** A perfect unsubmitted build scores zero.
- **7:15 AM** — demo phone charged, fallback thread loaded, presenter has run the flow once cold since waking up.

---

## 8. Submission and demo

Two distinct deliverables. Judges see the first; only the top 5 get to give the second. Weight effort accordingly — **the submission is the qualifying round.**

### 8.1 The 6:00 AM submission

Assume it is read at speed, on a laptop, by someone who has been awake all night and has dozens of these to get through. It must land the thesis in the first fifteen seconds without a phone in hand.

- **One-liner, verbatim at the top:** *TripAdvisor tells you what strangers liked. This knows what you liked.*
- **The Taste Profile, shown as output, not described.** Six real lines off a real inbox, counts included. This is the artifact that answers "make it feel human" — lead with it, above any architecture diagram.
- **60-second screen recording:** profile appears → judge-picked city → itinerary lands in iMessage → tapback swaps one stop → "it's raining" re-plans the afternoon. No narration of features; just the thing working.
- **Vercel page** hosting the above, one link.
- **Three technical claims, one line each:** revealed-taste extraction from transactional history; distaste modeling (cancellations, one-and-done, saved-never-visited) which no recommender does; every model call routed through Merge Gateway.
- **What is real vs. seeded,** stated plainly. Judges at a Merge/Photon event will find the seam anyway, and volunteering it buys more credibility than it costs.

### 8.2 Live demo (3 min, top 5 only)

Runs at 7:30 AM after a night with no sleep. Every step below must survive being executed badly.

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
| **Build slips past 6:00 AM and never gets submitted** | **Critical** | 4:00 AM freeze is the mitigation. It only works if it is treated as real at 3:45 AM |
| Venue wifi degrades overnight with 1000 people on it | High | Cache Places results and the last-good itinerary locally; no demo path may require a cold network call |
| Demo at 7:30 AM after zero sleep | High | One person owns the phone and sleeps in shifts 6:00–7:15; presenter runs the flow once cold before going on |
| Merge Gateway rate-limits or errors mid-build | Medium | One-line env flag to direct provider; wrapper isolated to a single file |
| $20 Gateway credit exhausted by extraction volume | Medium | Batch ~20 messages per call, cap backfill window, monitor spend at 11:30 PM before the full backfill |

---

## 10. Out of scope tonight

Accounts, settings, interactive web UI, companion/multi-user threads, bookings or payments, flights, budget optimization, maps rendering, Chat category, any Merge Unified API category outside File Storage and Knowledge Base.

The Vercel page is the one exception and is not a product surface: static, read-only, built after freeze, exists solely so the submission is a link (§8.1).

---

## 11. Prize alignment

Four things are actually on the table. The build is aimed at the first three; the fourth is the theme all of them are judged against.

- **Overall Best Project** *(AirPods Max ×4 + merch; 2nd: $100 in gift cards + merch; 3rd: Corgi/Merge/Vercel merch)* — real product thesis, working pipeline, defensible technical claim (revealed-taste extraction + distaste modeling), and an artifact that appears live rather than being described.
- **Merge Specific Prize** *(Plaude Note Taker per team member)* — the strongest possible version of this claim: **every model call in the pipeline routes through Merge Gateway**, so the product does not run without Merge. On top of that, File Storage EXIF adds visits with no booking trail, and Knowledge Base produces the declared-vs-revealed contrast that is the single best line in the demo. Be honest that Gmail is direct — claiming Merge does email in front of Merge engineers is the one unrecoverable mistake available tonight.
- **Photon Prize** *(Best Photon Interfaces ×2 — 1 month Photon Business line, ~$500 value)* — the stated ask is "bring your agent to iMessage using Photon," and the differentiator is that the interface is **load-bearing, not a wrapper**: tapback-as-control-surface and mid-trip re-plan only make sense in a messaging thread. Say why iMessage beats a web app here — the day falls apart while you are walking around a foreign city with one hand free — rather than claiming novelty.
- **"Make it feel human"** — the organizers' framing is *express, don't just execute*. This is the whole reason the Taste Profile ships before the itinerary. The output is an act of noticing: it tells you something true about yourself you never told it, then acts on it with restraint. A workflow that wires four APIs together does not clear this bar; a paragraph that makes someone say "how did it know that" does.

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
