"""Resolve D's assemble API, falling back to C's stub_plan."""

from __future__ import annotations

from typing import Any, Callable


def _load() -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    try:
        from palate.plan import assemble  # type: ignore

        build = getattr(assemble, "build_itinerary", None)
        swap = getattr(assemble, "swap_stop", None)
        repl = getattr(assemble, "replan", None)
        if all(callable(x) for x in (build, swap, repl)):
            return build, swap, repl  # type: ignore[return-value]
    except Exception:
        pass
    from palate.chat import stub_plan

    return stub_plan.build_itinerary, stub_plan.swap_stop, stub_plan.replan


def build_itinerary(profile: dict, city: str, days: int = 3) -> dict:
    fn, _, _ = _load()
    try:
        return fn(profile, city, days)
    except NotImplementedError:
        from palate.chat import stub_plan

        return stub_plan.build_itinerary(profile, city, days)


def swap_stop(itinerary: dict, stop_id: str, reason: str | None = None) -> dict:
    _, fn, _ = _load()
    try:
        return fn(itinerary, stop_id, reason)
    except NotImplementedError:
        from palate.chat import stub_plan

        return stub_plan.swap_stop(itinerary, stop_id, reason)


def replan(itinerary: dict, from_iso: str, state_text: str) -> dict:
    _, _, fn = _load()
    try:
        return fn(itinerary, from_iso, state_text)
    except NotImplementedError:
        from palate.chat import stub_plan

        return stub_plan.replan(itinerary, from_iso, state_text)
