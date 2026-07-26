"""FastAPI webhook. OWNER C. See docs/trd-c-photon.md step 3.

Expose with `ngrok http 8000` and register the URL with Photon. The ngrok URL
CHANGES ON EVERY RESTART — when the webhook goes silent at 2 AM, check that
first. It is the most common Photon dead-end.
"""

from __future__ import annotations

import json
import traceback

from fastapi import FastAPI, Request, Response

from palate.chat import photon
from palate.chat.replan import handle_tapback, handle_text

app = FastAPI()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/photon/webhook")
async def webhook(request: Request):
    raw = await request.body()
    headers = {k: v for k, v in request.headers.items()}

    if not photon.verify(raw, headers):
        return Response(content="bad signature", status_code=401)

    try:
        body = json.loads(raw.decode("utf-8") if raw else "{}")
    except json.JSONDecodeError:
        return Response(content="bad json", status_code=400)

    print("[photon] inbound:", json.dumps(body, ensure_ascii=False)[:2000])

    event = photon.parse_inbound(body, headers)
    if event is None:
        print("[photon] ignored (no handler)")
        return {"ok": True}

    print("[photon] normalized:", event)

    try:
        replies: list[str] = []
        if event["kind"] == "text":
            replies = handle_text(event["from"], event["text"])
        elif event["kind"] == "tapback":
            replies = handle_tapback(
                event["from"],
                event["target_message_id"],
                event["reaction"],
            )

        for text in replies or []:
            if text:
                photon.send(event["from"], text)
    except Exception:
        traceback.print_exc()
        # Still 200 so Spectrum does not hammer retries on handler bugs.
        return {"ok": True, "error": True}

    return {"ok": True}
