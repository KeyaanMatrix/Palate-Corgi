"""CLI commands for the chat package. OWNER: see docs/TRD.md section 2."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from palate import contracts
from palate.chat import photon
from palate.chat.replan import send_full_itinerary

BRIDGE_DIR = Path(__file__).resolve().parent / "bridge"
BRIDGE_PORT = os.environ.get("PHOTON_BRIDGE_PORT", "8787")


def check(args) -> None:
    from palate import contracts
    from palate.chat.format import format_stop
    from palate.chat.plan_api import build_itinerary, swap_stop

    stop = {
        "id": "stop_x1",
        "seq": 0,
        "name": "Taberna Sal Grosso",
        "category": "restaurant",
        "time": "20:45",
        "price_band": 2,
        "because": "You've been to Cotogna four times, always at the counter.",
        "is_stretch": False,
        "locked": False,
        "place_id": None,
    }
    text = format_stop(stop, 0)
    assert stop["name"] in text and ("20:45" in text or "8:45" in text)
    assert "*" not in text and "#" not in text, "no markdown — iMessage renders none"

    profile = {
        "home_city": "San Francisco",
        "earliest_activity_hour": 11,
        "seat_preference": "bar",
        "price_ceiling": 3,
    }
    itin = build_itinerary(profile, "Lisbon", days=1)
    stops = [s for _, s in contracts.iter_stops(itin)]
    assert len(stops) >= 2, "need at least two stops for lock/swap check"
    locked_stop = stops[0]
    swap_target = stops[1]
    locked_stop["locked"] = True
    locked_id = locked_stop["id"]
    after = swap_stop(itin, swap_target["id"], reason="check")
    assert locked_id in {s["id"] for _, s in contracts.iter_stops(after)}
    still = next(s for _, s in contracts.iter_stops(after) if s["id"] == locked_id)
    assert still.get("locked") is True
    assert still.get("name") == locked_stop["name"]

    print("chat.check OK")


def _ensure_bridge_deps() -> None:
    node_modules = BRIDGE_DIR / "node_modules"
    if node_modules.is_dir():
        return
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm not found — install Node to run the Photon send bridge")
    print("[chat.serve] npm install in", BRIDGE_DIR)
    subprocess.check_call([npm, "install"], cwd=str(BRIDGE_DIR))


def _start_bridge() -> subprocess.Popen | None:
    """Spawn the spectrum-ts bridge; return None if credentials are missing."""
    env = os.environ.copy()
    env.update(photon.bridge_credentials())
    has_creds = bool(
        (env.get("SPECTRUM_PROJECT_ID") and env.get("SPECTRUM_PROJECT_SECRET"))
        or (":" in (env.get("PHOTON_API_KEY") or ""))
    )
    if not has_creds:
        print(
            "[chat.serve] WARNING: no Spectrum credentials — "
            "webhook receive works; send/bridge disabled until "
            "SPECTRUM_PROJECT_ID/SECRET or PHOTON_API_KEY=id:secret are set"
        )
        return None

    _ensure_bridge_deps()
    node = shutil.which("node")
    if not node:
        raise SystemExit("node not found — install Node to run the Photon send bridge")

    server = BRIDGE_DIR / "server.mjs"
    print(f"[chat.serve] starting bridge on 127.0.0.1:{BRIDGE_PORT}")
    proc = subprocess.Popen(  # noqa: S603
        [node, str(server)],
        cwd=str(BRIDGE_DIR),
        env=env,
    )
    # Brief wait so /send isn't raced on first message.
    deadline = time.time() + 8
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"bridge exited early with code {proc.returncode}")
        try:
            import httpx

            r = httpx.get(f"http://127.0.0.1:{BRIDGE_PORT}/health", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.25)
    return proc


def serve(args) -> None:
    import uvicorn

    bridge = _start_bridge()
    try:
        uvicorn.run("palate.chat.app:app", host="0.0.0.0", port=8000, reload=False)
    finally:
        if bridge and bridge.poll() is None:
            bridge.terminate()
            try:
                bridge.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bridge.kill()


def send_cmd(args) -> None:
    if len(args) < 2:
        print("usage: python -m palate chat.send <phone> <text...>", file=sys.stderr)
        raise SystemExit(2)
    print(photon.send(args[0], " ".join(args[1:])))


def demo(args) -> None:
    if len(args) < 2:
        print("usage: python -m palate chat.demo <phone> <city>", file=sys.stderr)
        raise SystemExit(2)
    ids = send_full_itinerary(args[0], args[1])
    print(f"sent {len(ids)} messages")


def preview(args) -> None:
    """Print the real chat flow without requiring Photon credentials."""
    from palate.chat import format as fmt
    from palate.chat.plan_api import build_itinerary, replan, swap_stop
    from palate.chat.replan import _load_profile, _load_profile_lines

    city = args[0].strip() if args else "Lisbon"
    try:
        days = int(args[1]) if len(args) > 1 else 1
    except ValueError as exc:
        raise SystemExit("usage: python -m palate chat.preview [city] [days]") from exc

    itinerary = build_itinerary(_load_profile(), city, days=days)
    lines = _load_profile_lines()
    if lines:
        print("PROFILE")
        print(fmt.format_profile(lines))

    negative = itinerary.get("negative_recommendation")
    if negative:
        print("\nNEGATIVE RECOMMENDATION")
        print(fmt.format_negative(negative))

    print("\nITINERARY")
    for day_index, day in enumerate(itinerary.get("days") or []):
        print(day.get("date") or f"Day {day_index + 1}")
        for stop in day.get("stops") or []:
            print(fmt.format_stop(stop, day_index))

    before_stops = [stop for _, stop in contracts.iter_stops(itinerary)]
    if before_stops:
        target = before_stops[-1]
        swapped = swap_stop(itinerary, target["id"], reason="preview_tapback")
        previous_ids = {stop["id"] for stop in before_stops}
        replacement = next(
            (
                stop
                for _, stop in contracts.iter_stops(swapped)
                if stop["id"] not in previous_ids
            ),
            None,
        )
        if replacement:
            print("\nTAPBACK 👎 — ONLY THIS STOP CHANGES")
            print(fmt.format_stop(replacement, 0))

        cutoff = f"{swapped['days'][0]['date']}T00:00"
        rain = replan(swapped, cutoff, "it's raining")
        prior = {
            stop["id"]: stop for _, stop in contracts.iter_stops(swapped)
        }
        changed = [
            stop
            for _, stop in contracts.iter_stops(rain)
            if prior.get(stop["id"]) != stop
        ]
        if changed:
            print("\nTEXT: IT'S RAINING — FUTURE UNLOCKED STOPS ONLY")
            for stop in changed:
                print(fmt.format_stop(stop, 0))


COMMANDS = {
    "serve": serve,
    "send": send_cmd,
    "demo": demo,
    "preview": preview,
    "check": check,
}
