"""Gmail -> raw_message. OWNER A. See docs/trd-a-ingest.md step 3."""

import base64
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser

from palate import db

from .google_auth import gmail_service
from .vendors import QUERY_FRAGMENT

BODY_LIMIT = 4000


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        return " ".join(self.parts)


def _decode(data: str | None) -> str:
    """Decode Gmail's URL-safe base64 payload."""
    if not data:
        return ""

    try:
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()

    try:
        parser.feed(html)
        text = parser.text()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)

    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _walk_parts(part: dict) -> tuple[list[str], list[str]]:
    """Return all text/plain and text/html bodies from a MIME tree."""
    plain = []
    html = []

    mime_type = part.get("mimeType", "")
    data = part.get("body", {}).get("data")

    if mime_type == "text/plain" and data:
        plain.append(_decode(data))

    elif mime_type == "text/html" and data:
        html.append(_decode(data))

    for child in part.get("parts", []) or []:
        child_plain, child_html = _walk_parts(child)
        plain.extend(child_plain)
        html.extend(child_html)

    return plain, html


def _message_body(payload: dict) -> str:
    """Prefer text/plain; fall back to stripped HTML."""
    plain, html = _walk_parts(payload)

    if plain:
        body = "\n".join(x for x in plain if x.strip())
    elif html:
        body = "\n".join(_html_to_text(x) for x in html if x.strip())
    else:
        # Some simple non-multipart emails put data directly on payload.body.
        raw = _decode(payload.get("body", {}).get("data"))

        if payload.get("mimeType") == "text/html":
            body = _html_to_text(raw)
        else:
            body = raw

    return body.strip()[:BODY_LIMIT]


def _headers(payload: dict) -> dict[str, str]:
    return {
        h.get("name", "").lower(): h.get("value", "")
        for h in payload.get("headers", [])
    }


def _received_at(message: dict, headers: dict[str, str]) -> str | None:
    """Convert email Date to ISO where possible, falling back to Gmail internalDate."""
    date_header = headers.get("date")

    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.isoformat()
        except (TypeError, ValueError, OverflowError):
            pass

    internal_date = message.get("internalDate")

    if internal_date:
        try:
            return datetime.fromtimestamp(
                int(internal_date) / 1000,
                tz=timezone.utc,
            ).isoformat()
        except (TypeError, ValueError):
            pass

    return None


def run_sync(limit: int = 500, since: str = "2y") -> int:
    """Fetch vendor messages into raw_message. Return number fetched."""
    if limit <= 0:
        return 0

    service = gmail_service()

    query = f"{QUERY_FRAGMENT} newer_than:{since}".strip()

    fetched = 0
    page_token = None

    while fetched < limit:
        remaining = limit - fetched

        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=min(remaining, 500),
                pageToken=page_token,
            )
            .execute()
        )

        messages = response.get("messages", [])

        if not messages:
            break

        for item in messages:
            if fetched >= limit:
                break

            message = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=item["id"],
                    format="full",
                )
                .execute()
            )

            payload = message.get("payload", {})
            headers = _headers(payload)

            sender = headers.get("from", "")
            subject = headers.get("subject", "")
            received_at = _received_at(message, headers)
            body = _message_body(payload)

            fetched_at = datetime.now(timezone.utc).isoformat()

            # UPSERT rather than blindly replacing the entire row:
            # if filter/extraction already ran, re-syncing should not erase it.
            db.execute(
                """
                INSERT INTO raw_message (
                    id,
                    source,
                    sender,
                    subject,
                    body,
                    received_at,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(id) DO UPDATE SET
                    source      = excluded.source,
                    sender      = CASE
                        WHEN raw_message.extracted = 0 THEN excluded.sender
                        ELSE NULL
                    END,
                    subject     = CASE
                        WHEN raw_message.extracted = 0 THEN excluded.subject
                        ELSE NULL
                    END,
                    body        = CASE
                        WHEN raw_message.extracted = 0 THEN excluded.body
                        ELSE NULL
                    END,
                    received_at = excluded.received_at,
                    fetched_at  = excluded.fetched_at
                """,
                (
                    message["id"],
                    "gmail",
                    sender,
                    subject,
                    body,
                    received_at,
                    fetched_at,
                ),
            )

            fetched += 1

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return fetched
