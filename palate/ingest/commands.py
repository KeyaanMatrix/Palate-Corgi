"""CLI commands for the ingest package. OWNER: see docs/TRD.md section 2.

Add commands to the COMMANDS dict below. You own this file — nobody else edits
it, so it can never be a merge conflict. Keep 'check' working: `make check`
runs it before every push, and a broken check blocks the whole team's merge.
"""

def check(args) -> None:
    from .vendors import classify

    cases = [
        ("noreply@resy.com", "Your reservation at Cotogna is confirmed", "resy"),
        ("no-reply@opentable.com", "Your table is booked", "opentable"),
        ("orders@exploretock.com", "Your Tock reservation", "tock"),
        ("news@resy.com", "The 10 hottest new restaurants", None),
        ("hello@substack.com", "This week in food", None),
    ]

    for sender, subject, expected in cases:
        got = classify(sender, subject)
        assert got == expected, (
            f"{sender!r}/{subject!r}: expected {expected}, got {got}"
        )

    print(f"ingest.check OK ({len(cases)} fixtures)")

def sync(args) -> None:
    from .gmail_sync import run_sync

    limit = int(args[0]) if args else 500
    count = run_sync(limit)
    print(f"{count} messages")

def filter_messages(args) -> None:
    from . import prefilter

    limit = int(args[0]) if args else None
    print(prefilter.run(limit))

def extract(args) -> None:
    from .extract import extract_pending

    batch_size = int(args[0]) if args else 20
    count = extract_pending(batch_size)
    print(f"{count} visits")

def calendar(args) -> None:
    from .calendar_sync import run_sync

    months = int(args[0]) if args else 24
    count = run_sync(months)
    print(f"{count} calendar events")

COMMANDS = {
    "sync": sync,
    "calendar": calendar,
    "filter": filter_messages,
    "extract": extract,
    "check": check,
}
