# Sub-TRD C — Photon / iMessage

**Branch:** `c-photon` **Owns:** `palate/chat/`, `web/`, `requirements/c.txt`
**Read `docs/TRD.md` §1–§6 first.** Sections 3.2 and 3.3 are your contracts.

## Your mission

Make the interface **load-bearing, not a wrapper** — that is the entire Photon prize argument (PRD §11, "Best Photon Interfaces ×2"). The claim you must be able to defend on stage: tapback-as-control-surface and mid-trip re-plan only make sense in a messaging thread, because the day falls apart while you're walking around a foreign city with one hand free.

**Explicitly out of scope:** a general chat agent over text. If it answers arbitrary questions it becomes a worse Claude app and the Photon argument collapses (PRD §4). Every inbound message routes to one of four handlers or gets a polite "I only do stops."

You also own the **Vercel submission page** after freeze — see §Post-freeze below. It is a permalink, not a product surface.

You do **not** own: itinerary logic (D — you call `build_itinerary`/`swap_stop`/`replan` and nothing else), the profile (B).

---

## Hour 0 (7:30–9:30 PM) — Photon hello-world

The risk here is the unknown API surface, so isolate it in one adapter file and build everything else against your own interface.

### 1. Claim the credit first

`app.photon.codes/sign-in` → create project → billing page → code `Hackwithphoton` ($25). Do this before the sign-up flow gets congested.

### 2. `palate/chat/photon.py` — the adapter, and the only file that changes if Photon's API differs from your assumption

```python
def send(to: str, text: str) -> str:
    """Send one message. Returns the provider message id — you need it to map
    tapbacks back to stops."""

def parse_inbound(body: dict, headers: dict) -> dict | None:
    """Normalize a webhook payload into our own shape. Returns None for
    anything we don't handle (delivery receipts, typing indicators).

        {"kind": "text",    "from": "+1...", "text": "it's raining"}
        {"kind": "tapback", "from": "+1...", "reaction": "up"|"down",
         "target_message_id": "..."}
    """

def verify(body: bytes, headers: dict) -> bool:
    """HMAC signature check against PHOTON_WEBHOOK_SECRET."""
```

**Read Photon's actual docs and shape these three functions to reality.** Everything downstream depends only on the normalized dict, so when the payload turns out to be different from what you guessed, you change one file.

### 3. `palate/chat/app.py` — FastAPI

```python
@app.post("/photon/webhook")
async def webhook(request: Request): ...

@app.get("/health")
def health(): return {"ok": True}
```

Expose it with ngrok (`ngrok http 8000`) and register the URL with Photon. **The ngrok URL changes every restart** — when the webhook stops firing at 2 AM, that is the first thing to check, and it is the single most common Photon debugging dead-end.

### Gate — 9:30 PM

You can text the Photon number and see the payload land in your console. Nothing else. That is the gate.

---

## Hour 2 (9:30–11:30 PM) — One stop per message

### 4. `palate/chat/format.py`

```python
def format_stop(stop: dict, day_index: int) -> str: ...
def format_profile(lines: list[str]) -> str: ...
def format_negative(neg: dict) -> str: ...
```

**Every stop is its own message.** That is what makes tapbacks work as a control surface — a tapback targets a message, so one stop per message means one tapback per stop.

Formatting rules (PRD §4, "forwardable output"):

- No agent voice. No "Here's your itinerary!", no "I've scheduled...". The message is written to be forwarded to a travel companion **as-is**.
- Time, name, then the `because` on its own line.
- No markdown — iMessage renders none of it. Line breaks and plain text only.

```
8:45pm · Taberna Sal Grosso

You've been to Cotogna four times and always at the counter. This is
the one counter-service place in Lisbon that runs the same way.
Booked Wednesday 8:45 — your slot.
```

### 5. `palate/chat/session.py`

```python
def get_session(phone: str) -> dict: ...
def save_session(phone: str, itinerary: dict) -> None: ...
def map_message(phone: str, message_id: str, stop_id: str) -> None: ...
def stop_for_message(phone: str, message_id: str) -> str | None: ...
```

State goes in the `session` table, keyed by phone. **The message-id → stop-id map is the thing that makes tapbacks work** — build it as you send, persist it, and never keep it only in memory (a server restart at 3 AM would otherwise kill the demo).

---

## Hour 4 (11:30 PM–1:00 AM) — Tapbacks

### 6. Tapback handler

```
👎 on a stop message  →  itin = plan.swap_stop(itin, stop_id, reason="tapback_down")
                      →  send the replacement stop as a NEW message
                      →  map the new message id to the new stop id
                      →  touch nothing else in the day

👍 on a stop message  →  mark stop locked=True; save; no reply, or a single "👍"
```

The demo moment is that **one stop changes and the rest of the day doesn't** (PRD §8.2 step 7). Verify that literally: send a day, tapback stop 2, confirm stops 1 and 3 are untouched in the stored itinerary.

Zero typing is the point. If a swap requires the user to type anything, it isn't a control surface.

---

## Hour 6 (2:00–4:00 AM) — Re-plan on natural language state

### 7. `palate/chat/replan.py`

```python
STATE_PATTERNS = {
    "weather":  ["raining", "rain", "storm", "pouring"],
    "energy":   ["wrecked", "exhausted", "tired", "dead", "hungover"],
    "running":  ["still at lunch", "running late", "behind"],
    "closed":   ["closed", "shut", "not open"],
}

def classify_state(text: str) -> str | None:
    """Keyword match FIRST. Model only as fallback. Deterministic beats clever
    when the demo depends on it firing on the word 'raining'."""

def handle_text(phone: str, text: str) -> list[str]:
    """Route: state → replan | 'plan <city>' → build | otherwise → the polite decline."""
```

Then: `plan.replan(itin, from_iso=now, state_text=text)` → re-send only the changed stops, preserving locked ones.

**Keyword-match "raining" before you reach for the model.** The demo says the word "raining" out loud; a keyword match cannot fail on stage, and a model call at 7:30 AM on venue wifi can.

The polite decline for everything else:

> I only handle stops — tap 👎 to swap one, or tell me what changed (raining, running late, museum closed).

### 8. Fallback thread (before 4:00 AM — this is a PRD §7 gate)

Pre-load a phone that has **already run the whole flow end to end**: profile, itinerary, one swap, one re-plan. If live anything fails at 7:30 AM, you scroll. Charge the phone. Screenshot each step as a second-level backup.

---

## Post-freeze (4:00–5:30 AM) — video and the Vercel page

**4:00–4:30 — the 60-second video.** One take, screen recording of the phone: profile appears → judge-picked city → itinerary lands one stop per message → tapback swaps one stop → "it's raining" re-plans the afternoon. No narration of features, no voiceover explaining the architecture. Just the thing working.

**4:30–5:15 — `web/index.html`.** Static, single file, no backend, no framework. Contents in order:
1. The one-liner: *TripAdvisor tells you what strangers liked. This knows what you liked.*
2. The six profile lines, as output.
3. The embedded video.
4. Three technical claims, one line each.
5. The real-vs-seeded note.

Deploy: `npx vercel --prod` with code `V0-CORGIMERGE30`. Test the link on a phone before you call it done.

---

## Your smoke check

```python
def check(args) -> None:
    from palate import contracts
    from .format import format_stop
    stop = {"id": "stop_x1", "seq": 0, "name": "Taberna Sal Grosso",
            "category": "restaurant", "time": "20:45", "price_band": 2,
            "because": "You've been to Cotogna four times, always at the counter.",
            "is_stretch": False, "locked": False, "place_id": None}
    text = format_stop(stop, 0)
    assert stop["name"] in text and "20:45" in text or "8:45" in text
    assert "*" not in text and "#" not in text, "no markdown — iMessage renders none"
    print("chat.check OK")
```

Once D's functions land, extend it: build a seeded itinerary, lock a stop, `swap_stop` a different one, assert the locked stop survived with the same id.

## Commands you expose

```python
COMMANDS = {
    "serve": lambda a: uvicorn.run("palate.chat.app:app", port=8000, reload=True),
    "send":  lambda a: print(photon.send(a[0], " ".join(a[1:]))),
    "demo":  lambda a: send_full_itinerary(a[0], a[1]),   # phone, city
    "check": check,
}
```

## If it goes wrong

| Symptom | Move |
|---|---|
| Webhook silent | ngrok URL rotated on restart — re-register. Check that before anything else |
| Tapback payload isn't what you assumed | It's one function (`parse_inbound`). Fix there, nothing downstream changes |
| Tapbacks unsupported on your Photon plan | Fall back to numbered replies ("2" swaps stop 2). Weaker demo, still zero-typing-ish. Decide by 1:00 AM |
| D's functions aren't ready | Build against a hand-written itinerary JSON matching TRD §3.3. You are not blocked |
| Venue wifi dies | Last-good itinerary is in SQLite; keyword re-plan needs no network. Do not add a demo path that requires a cold network call |
