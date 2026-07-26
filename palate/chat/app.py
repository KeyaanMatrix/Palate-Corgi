"""FastAPI webhook. OWNER C. See docs/trd-c-photon.md step 3.

Expose with `ngrok http 8000` and register the URL with Photon. The ngrok URL
CHANGES ON EVERY RESTART — when the webhook goes silent at 2 AM, check that
first. It is the most common Photon dead-end.
"""

from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/photon/webhook")
async def webhook(request: Request):
    raise NotImplementedError
