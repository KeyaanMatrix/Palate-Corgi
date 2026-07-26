"""CLI commands for the plan package. OWNER: see docs/TRD.md section 2.

Add commands to the COMMANDS dict below. You own this file — nobody else edits
it, so it can never be a merge conflict. Keep 'check' working: `make check`
runs it before every push, and a broken check blocks the whole team's merge.
"""

import copy


def check(args) -> None:
    from palate import contracts
    from palate.profile.build import build_profile, load_profile

    from .assemble import build_itinerary, replan, swap_stop

    profile = load_profile() or build_profile()
    itinerary = build_itinerary(profile, "Lisbon", days=2)
    assert not contracts.validate_itinerary(itinerary, profile)

    original = copy.deepcopy(itinerary)
    stops = [stop for _, stop in contracts.iter_stops(itinerary)]
    assert len(stops) >= 3
    stops[0]["locked"] = True
    locked = copy.deepcopy(stops[0])
    before_swap = copy.deepcopy(itinerary)
    after = swap_stop(itinerary, stops[1]["id"], reason="smoke")
    assert itinerary == before_swap, "swap_stop mutated its input"
    after_stops = [stop for _, stop in contracts.iter_stops(after)]
    assert next(stop for stop in after_stops if stop["id"] == locked["id"]) == locked
    unchanged = {
        stop["id"]: stop
        for _, stop in contracts.iter_stops(before_swap)
        if stop["id"] != stops[1]["id"]
    }
    for _, stop in contracts.iter_stops(after):
        if stop["id"] in unchanged:
            assert stop == unchanged[stop["id"]], "swap changed a non-target stop"

    before_replan = copy.deepcopy(after)
    replanned = replan(
        after,
        f"{after['days'][0]['date']}T00:00",
        "it's raining",
    )
    assert after == before_replan, "replan mutated its input"
    kept_locked = next(
        stop
        for _, stop in contracts.iter_stops(replanned)
        if stop["id"] == locked["id"]
    )
    assert kept_locked == locked
    assert not contracts.validate_itinerary(replanned)
    assert original != replanned
    print("plan.check OK (build, pure swap, locked-stop replan, contract invariants)")


def itinerary(args) -> None:
    from palate import contracts
    from palate.profile.build import build_profile, load_profile

    from .assemble import build_itinerary

    if not args:
        raise SystemExit("usage: python -m palate plan.itinerary <city> [days]")
    profile = load_profile() or build_profile()
    print(
        contracts.dumps(
            build_itinerary(profile, args[0], int(args[1]) if len(args) > 1 else 3)
        )
    )


def places_cmd(args) -> None:
    from palate import contracts

    from .places import discover

    if not args:
        raise SystemExit("usage: python -m palate plan.places <city> [category]")
    print(
        contracts.dumps(discover(args[0], args[1] if len(args) > 1 else "restaurant"))
    )


COMMANDS = {
    "itinerary": itinerary,
    "places": places_cmd,
    "check": check,
}
