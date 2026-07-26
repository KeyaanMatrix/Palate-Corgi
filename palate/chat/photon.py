"""Photon adapter. OWNER C. See docs/trd-c-photon.md step 2.

THIS IS THE ONLY FILE THAT CHANGES if Photon's API differs from what we assumed.
Everything downstream depends only on the normalized dict from parse_inbound.
Read Photon's actual docs and shape these three functions to reality.
"""

from palate import config  # noqa: F401


def send(to: str, text: str) -> str:
    """Send one message. Returns the provider message id.

    You need that id: it is how a tapback maps back to a stop.
    """
    raise NotImplementedError


def parse_inbound(body: dict, headers: dict) -> dict | None:
    """Normalize a webhook payload. None for anything we don't handle.

        {"kind": "text",    "from": "+1...", "text": "it's raining"}
        {"kind": "tapback", "from": "+1...", "reaction": "up"|"down",
         "target_message_id": "..."}
    """
    raise NotImplementedError


def verify(body: bytes, headers: dict) -> bool:
    """HMAC check against PHOTON_WEBHOOK_SECRET."""
    raise NotImplementedError
