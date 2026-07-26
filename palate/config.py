"""Environment and paths. BASE — frozen. Do not edit on a feature branch."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


DB_PATH = ROOT / get("PALATE_DB", "./palate.db").lstrip("./")
SCHEMA_PATH = ROOT / "schema.sql"
SEED_PATH = ROOT / "seed" / "seed.sql"

HOME_CITY = get("HOME_CITY", "San Francisco")

LLM_MODEL = get("LLM_MODEL", "claude-opus-5")
LLM_DIRECT = get("LLM_DIRECT", "0") == "1"
ANTHROPIC_API_KEY = get("ANTHROPIC_API_KEY")
MERGE_GATEWAY_BASE_URL = get("MERGE_GATEWAY_BASE_URL")
MERGE_GATEWAY_API_KEY = get("MERGE_GATEWAY_API_KEY")

MERGE_API_KEY = get("MERGE_API_KEY")
MERGE_ACCOUNT_TOKEN = get("MERGE_ACCOUNT_TOKEN")

GOOGLE_CLIENT_SECRETS = get("GOOGLE_CLIENT_SECRETS", "./client_secret.json")
GOOGLE_TOKEN_PATH = get("GOOGLE_TOKEN_PATH", "./.google_token.json")
GOOGLE_PLACES_API_KEY = get("GOOGLE_PLACES_API_KEY")

PHOTON_API_KEY = get("PHOTON_API_KEY")
PHOTON_WEBHOOK_SECRET = get("PHOTON_WEBHOOK_SECRET")
PHOTON_FROM_NUMBER = get("PHOTON_FROM_NUMBER")
