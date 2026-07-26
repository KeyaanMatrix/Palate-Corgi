"""Google OAuth. OWNER A. See docs/trd-a-ingest.md step 2."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from palate import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _resolve_path(value: str) -> Path:
    """Resolve config paths relative to the repository root."""
    path = Path(value)
    if path.is_absolute():
        return path
    return config.ROOT / path


def credentials() -> Credentials:
    """Load cached token, refresh if stale, else run InstalledAppFlow.

    Token is cached at config.GOOGLE_TOKEN_PATH so repeat runs do not
    require browser consent.
    """
    token_path = _resolve_path(config.GOOGLE_TOKEN_PATH)
    secrets_path = _resolve_path(config.GOOGLE_CLIENT_SECRETS)

    creds = None

    # 1. Reuse cached credentials if we have them.
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_path),
                SCOPES,
            )
        except ValueError:
            # Bad/stale token file: fall through to a new OAuth flow.
            creds = None

    # 2. Refresh expired credentials without reopening the browser.
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # 3. No usable credentials -> run OAuth consent flow.
    if not creds or not creds.valid:
        if not secrets_path.exists():
            raise FileNotFoundError(
                f"Google OAuth client secrets not found at: {secrets_path}\n"
                "Download the Desktop OAuth client JSON from Google Cloud "
                "and save it as client_secret.json in the repo root."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(secrets_path),
            SCOPES,
        )
        creds = flow.run_local_server(port=0)

    # 4. Always persist the latest token/refresh state.
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    token_path.chmod(0o600)

    return creds


def gmail_service():
    """Return an authenticated Gmail API v1 client."""
    return build(
        "gmail",
        "v1",
        credentials=credentials(),
        cache_discovery=False,
    )


def calendar_service():
    """Return an authenticated Google Calendar API v3 client."""
    return build(
        "calendar",
        "v3",
        credentials=credentials(),
        cache_discovery=False,
    )
