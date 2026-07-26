# Palate demo runbook

This is the three-minute top-five demo and the fallback path. Do one full cold
rehearsal from this page before presenting.

## Before the room

```bash
source .venv/bin/activate
make doctor
PALATE_DB=./palate.check.db make check
python -m palate profile.plain
python -m palate chat.preview Lisbon 1
```

Verify these by hand:

- The profile line you plan to read is true for the presenter. Use
  `profile.evidence <key>` to inspect its rows.
- The demo phone is charged, the presenter thread is already open, and the
  newest outbound stop messages accept tapbacks.
- `curl http://127.0.0.1:8000/health` and
  `curl http://127.0.0.1:8787/health` both return an OK response.
- The current public tunnel points to `/photon/webhook` in the Spectrum
  project. A restarted tunnel has a new URL.
- `web/demo.mp4` exists and the deployed submission page shows it.

## Three minutes

1. **Hook — 15 seconds**

   “Every travel app tells you what strangers liked. Watch this tell me what I
   liked, from data I never gave it on purpose.”

2. **Profile — 35 seconds**

   Open with `You book Wednesdays…`, then read the cancellation line and the
   saved-but-never-visited line. Do not explain the architecture yet.

3. **City — 45 seconds**

   Text `plan Lisbon` (or use the judge’s city only if its Places cache was
   warmed). Point out the negative recommendation first, then one stop and its
   grounded “because.”

4. **Control surface — 35 seconds**

   Tap `👎` on one stop. Say: “One reaction changed one stop. The rest of the
   day is identical.” Do not scroll away from the unchanged neighbors.

5. **State change — 30 seconds**

   Text `it’s raining`. The deterministic keyword path runs without a model
   call. Point out that completed and locked stops survive.

6. **Close — 20 seconds**

   “Popularity engines flatten a city toward everyone else. A taste graph gets
   more personal every time you book, cancel, return, or walk away.”

## Failure fallbacks

- **No venue Wi-Fi:** use Lisbon. Its candidate pool and last plan are local;
  profile, swap, and rain logic do not need a cold network call.
- **No outbound iMessage:** run
  `python -m palate chat.preview Lisbon 1` and show the self-running submission
  page.
- **Tapbacks unavailable:** reply with the one-based stop number. `2` swaps
  stop two through the same planner.
- **Gateway unavailable:** set `LLM_DIRECT=1` only if an Anthropic key is
  present. Profile computation, deterministic copy, and the warm plan still
  work without a model.
- **Google OAuth fails:** do not debug a stranger’s inbox on stage. Use the
  presenter’s reviewed local database and state plainly that the page’s sample
  profile is the 30-row fixture.
- **Tunnel went stale:** restart the tunnel, update the Spectrum webhook URL,
  and send one inbound text before going on stage.

## Replacing the seeded walkthrough with a live phone capture

`web/demo.mp4` contains a clearly disclosed 32-second walkthrough of the
working seeded interface. Once Spectrum credentials and the sending number are
available, replace it with a single vertical phone screen capture under 60
seconds:

1. Start on the profile message.
2. Send `plan Lisbon`.
3. Pause on the negative recommendation and one rationale.
4. Tap `👎` on the second stop and show its replacement.
5. Send `it’s raining` and show the changed future message.
6. Trim only dead time. Do not add narration or simulated UI.
7. Export to `web/demo.mp4`; the static page reveals it automatically.
