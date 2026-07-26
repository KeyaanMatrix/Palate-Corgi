"""Photon adapter. OWNER C. See docs/trd-c-photon.md step 2.

THIS IS THE ONLY FILE THAT CHANGES if Photon's API differs from what we assumed.
Everything downstream depends only on the normalized dict from parse_inbound.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

import httpx

from palate import config

_TOLERANCE_SEC = 5 * 60
_BRIDGE_URL = os.environ.get("PHOTON_BRIDGE_URL", "http://127.0.0.1:8787")

# iMessage tapbacks we care about (Spectrum ships emoji characters).
_UP = frozenset({"👍", "thumbs_up", "like", "+1"})
_DOWN = frozenset({"👎", "thumbs_down", "dislike", "-1"})


def _header(headers: dict, *names: str) -> str | None:
    lower = {str(k).lower(): v for k, v in headers.items()}
    for name in names:
        val = lower.get(name.lower())
        if val is not None:
            return val if isinstance(val, str) else str(val)
    return None


def send(to: str, text: str) -> str:
    """Send one message via the local spectrum-ts bridge. Returns message id."""
    with httpx.Client(timeout=60.0) as client:
        r = client.post(f"{_BRIDGE_URL.rstrip('/')}/send", json={"to": to, "text": text})
        r.raise_for_status()
        data = r.json()
    if not data.get("ok") or not data.get("id"):
        raise RuntimeError(f"bridge send failed: {data}")
    return str(data["id"])


def parse_inbound(body: dict, headers: dict) -> dict | None:
    """Normalize a webhook payload. None for anything we don't handle.

        {"kind": "text",    "from": "+1...", "text": "it's raining"}
        {"kind": "tapback", "from": "+1...", "reaction": "up"|"down",
         "target_message_id": "..."}
    """
    event = body.get("event") or _header(headers, "X-Spectrum-Event")
    if event and event != "messages":
        return None

    message = body.get("message")
    if not isinstance(message, dict):
        return None

    # Ignore our own outbound echoes if Spectrum ever delivers them.
    if message.get("direction") == "outbound":
        return None

    content = message.get("content") or {}
    if not isinstance(content, dict):
        return None

    sender = message.get("sender") or {}
    from_id = sender.get("id") if isinstance(sender, dict) else None
    if not from_id:
        return None

    ctype = content.get("type")
    if ctype == "text":
        text = content.get("text")
        if text is None:
            return None
        return {"kind": "text", "from": str(from_id), "text": str(text)}

    if ctype == "reaction":
        emoji = str(content.get("emoji") or "").strip()
        target = content.get("target") or {}
        target_id = target.get("id") if isinstance(target, dict) else None
        if not target_id:
            return None
        reaction: str | None = None
        if emoji in _UP:
            reaction = "up"
        elif emoji in _DOWN:
            reaction = "down"
        else:
            return None
        return {
            "kind": "tapback",
            "from": str(from_id),
            "reaction": reaction,
            "target_message_id": str(target_id),
        }

    return None


def verify(body: bytes, headers: dict) -> bool:
    """HMAC check against PHOTON_WEBHOOK_SECRET (Spectrum signing secret)."""
    secret = (config.PHOTON_WEBHOOK_SECRET or "").encode("utf-8")
    if not secret:
        return False

    timestamp = _header(headers, "X-Spectrum-Timestamp")
    signature = _header(headers, "X-Spectrum-Signature")
    if not timestamp or not signature:
        return False

    try:
        age = abs(int(time.time()) - int(timestamp))
    except ValueError:
        return False
    if age > _TOLERANCE_SEC:
        return False

    raw = body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)
    base = f"v0:{timestamp}:{raw}".encode("utf-8")
    expected = "v0=" + hmac.new(secret, base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def bridge_credentials() -> dict[str, str]:
    """Env passed into the Node bridge child process."""
    env: dict[str, Any] = {}
    for key in (
        "SPECTRUM_PROJECT_ID",
        "SPECTRUM_PROJECT_SECRET",
        "PHOTON_API_KEY",
        "PHOTON_BRIDGE_PORT",
        "PHOTON_FROM_NUMBER",
    ):
        val = os.environ.get(key) or getattr(config, key, None)
        if val:
            env[key] = str(val)
    return {k: v for k, v in env.items() if v}
