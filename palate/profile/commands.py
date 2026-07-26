"""CLI commands for the profile package. OWNER: see docs/TRD.md section 2.

Add commands to the COMMANDS dict below. You own this file — nobody else edits
it, so it can never be a merge conflict. Keep 'check' working: `make check`
runs it before every push, and a broken check blocks the whole team's merge.
"""

from palate import contracts

from .build import EXTRA_KEYS, build_profile, explain, load_profile
from .copy import render_plain, render_profile_copy, unsourced_numbers

# Metrics that must survive contact with any dataset worth demoing. Deliberately
# short: these three are the spine of the profile, and D's planner reads the
# first one as a hard constraint. Everything else is allowed to be None on thin
# data — the copy drops the line rather than inventing a value.
REQUIRED_VALUES = ("earliest_activity_hour", "typical_party_size", "revisit_ratio")

# Enough sourced lines to be worth reading. Kept low on purpose: this check
# gates the whole team's push, and on thin real data the honest outcome is a
# short profile, not a failed merge.
MIN_COPY_LINES = 3


def check(args) -> None:
    """Smoke check for this package. TRD section 8: profile builds on seed data,
    every headline key has an evidence entry."""
    profile = build_profile()

    missing = contracts.profile_is_sourced(profile)
    assert not missing, f"unsourced keys: {missing}"

    absent = [k for k in (*contracts.TASTE_PROFILE_KEYS, *EXTRA_KEYS) if k not in profile]
    assert not absent, f"profile is missing keys: {absent}"

    for key in REQUIRED_VALUES:
        assert profile.get(key) is not None, f"{key} is None on seed data"

    for key, entry in (profile.get("evidence") or {}).items():
        assert entry.get("n") is not None, f"evidence for {key} has no count"

    # load_profile() is the seam C and D call. If the round trip through SQLite
    # loses anything, they find out here rather than at 3 AM.
    loaded = load_profile()
    assert loaded == profile, "load_profile() did not round-trip the profile it wrote"

    # The copy check, run against the deterministic renderer so it needs no
    # network: every number that would be read aloud traces back to the dict.
    lines = render_plain(profile)
    assert len(lines) >= MIN_COPY_LINES, f"render_plain produced only {len(lines)} lines"
    for line in lines:
        bad = unsourced_numbers(line, profile)
        assert not bad, f"unsourced number {bad} in: {line}"

    print(
        f"profile.check OK ({len(profile.get('evidence', {}))} sourced metrics,"
        f" {len(lines)} copy lines, every number traced)"
    )


COMMANDS = {
    "build": lambda a: print(contracts.dumps(build_profile())),
    "render": lambda a: print("\n".join(render_profile_copy(load_profile() or build_profile()))),
    "plain": lambda a: print("\n".join(render_plain(load_profile() or build_profile()))),
    "evidence": lambda a: print(explain(a[0]) if a else "usage: profile.evidence <key>"),
    "check": check,
}
