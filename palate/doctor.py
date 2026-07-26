"""Read-only readiness report for the hackathon build."""

from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

from palate import config


def _mark(ok: bool) -> str:
    return "READY" if ok else "WAITING"


def _path(value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else config.ROOT / candidate


def _row(label: str, ok: bool, detail: str) -> bool:
    print(f"{_mark(ok):<8} {label:<24} {detail}")
    return ok


def main() -> int:
    print("Palate readiness\n")

    packages = ("anthropic", "httpx", "fastapi", "uvicorn", "PIL", "googleapiclient")
    missing_packages = [
        package for package in packages if importlib.util.find_spec(package) is None
    ]
    _row(
        "Python dependencies",
        not missing_packages,
        "installed" if not missing_packages else "missing: " + ", ".join(missing_packages),
    )
    node_ready = bool(shutil.which("node") and shutil.which("npm"))
    _row("Node runtime", node_ready, "node + npm")
    bridge_packages = (
        config.ROOT
        / "palate/chat/bridge/node_modules/@spectrum-ts/core/package.json"
    ).is_file()
    _row("Photon bridge packages", bridge_packages, "palate/chat/bridge/node_modules")
    _row("Database", config.DB_PATH.exists(), str(config.DB_PATH))
    _row("Static submission", (config.ROOT / "web/index.html").exists(), "web/index.html")
    site_packages = (config.ROOT / "node_modules/vinext/package.json").is_file()
    _row("Submission packages", site_packages, "root node_modules")

    gateway = bool(config.MERGE_GATEWAY_BASE_URL and config.MERGE_GATEWAY_API_KEY)
    direct = bool(config.LLM_DIRECT and config.ANTHROPIC_API_KEY)
    llm_ready = gateway or direct
    route = "Merge Gateway" if gateway else "direct fallback" if direct else "credentials missing"
    _row("Model route", llm_ready, route)

    google_secret = _path(config.GOOGLE_CLIENT_SECRETS)
    google_ready = google_secret.is_file()
    _row("Google inbox/calendar", google_ready, str(google_secret))
    _row("Google Places", bool(config.GOOGLE_PLACES_API_KEY), "API key")

    merge_files_ready = bool(
        config.MERGE_API_KEY and config.MERGE_FILESTORAGE_ACCOUNT_TOKEN
    )
    merge_kb_ready = bool(
        config.MERGE_API_KEY and config.MERGE_KNOWLEDGEBASE_ACCOUNT_TOKEN
    )
    _row("Merge File Storage", merge_files_ready, "API key + File Storage token")
    _row("Merge Knowledge Base", merge_kb_ready, "API key + Knowledge Base token")

    spectrum_project = os.environ.get("SPECTRUM_PROJECT_ID")
    spectrum_secret = os.environ.get("SPECTRUM_PROJECT_SECRET")
    spectrum_send = bool(
        spectrum_project and spectrum_secret and config.PHOTON_FROM_NUMBER
    )
    _row("Spectrum outbound", spectrum_send, "project + secret + sending number")
    _row("Spectrum webhook", bool(config.PHOTON_WEBHOOK_SECRET), "signing secret")

    recording = config.ROOT / "web/demo.mp4"
    _row("Phone recording", recording.is_file(), str(recording))

    print(
        "\nCore seed/offline demo is local-only and ready after dependencies + database."
    )
    waiting = [
        name
        for name, ready in (
            ("model route", llm_ready),
            ("Google inbox/calendar", google_ready),
            ("Google Places", bool(config.GOOGLE_PLACES_API_KEY)),
            ("Merge File Storage", merge_files_ready),
            ("Merge Knowledge Base", merge_kb_ready),
            ("Spectrum outbound", spectrum_send),
            ("Spectrum webhook", bool(config.PHOTON_WEBHOOK_SECRET)),
            ("phone recording", recording.is_file()),
        )
        if not ready
    ]
    if waiting:
        print("External seams still waiting: " + ", ".join(waiting) + ".")
    else:
        print("Every live integration and submission asset is present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
