"""CLI commands for the profile package. OWNER: see docs/TRD.md section 2.

Add commands to the COMMANDS dict below. You own this file — nobody else edits
it, so it can never be a merge conflict. Keep 'check' working: `make check`
runs it before every push, and a broken check blocks the whole team's merge.
"""


def check(args) -> None:
    """Smoke check for this package. Replace the stub with a real assertion."""
    print("profile.check: stub — not implemented yet (see docs/trd-*.md)")


COMMANDS = {
    "check": check,
}
