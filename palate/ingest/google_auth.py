"""Google OAuth. OWNER A. See docs/trd-a-ingest.md step 2.

Consent screen in TESTING mode with the presenter as a test user — no
verification needed for a demo, and it is where teams lose two hours tonight.
Cache the token so the demo never needs a live browser prompt.
"""

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def credentials():
    """Cached token → refresh if stale → InstalledAppFlow as last resort."""
    raise NotImplementedError


def gmail_service():
    raise NotImplementedError


def calendar_service():
    raise NotImplementedError
