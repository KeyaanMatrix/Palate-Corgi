"""Stage-1 deterministic pre-filter. OWNER A. See docs/trd-a-ingest.md step 5.

Build this list by looking at the presenter's ACTUAL inbox, not from memory.
Fifteen accurate vendors beats forty guessed ones.
"""

VENDORS: dict[str, dict] = {
    "resy":       {"domains": ["resy.com"],        "subjects": ["reservation", "confirmed", "cancel"]},
    "opentable":  {"domains": ["opentable.com"],   "subjects": ["reservation", "table", "cancel"]},
    "tock":       {"domains": ["exploretock.com", "tock.com"], "subjects": ["reservation", "ticket"]},
    "sevenrooms": {"domains": ["sevenrooms.com"],  "subjects": ["reservation"]},
    "eventbrite": {"domains": ["eventbrite.com"],  "subjects": ["ticket", "order confirm"]},
    "dice":       {"domains": ["dice.fm"],         "subjects": ["ticket"]},
    "airbnb":     {"domains": ["airbnb.com"],      "subjects": ["reservation", "itinerary"]},
    # TODO(A): add hotels, airlines, and any direct-restaurant senders you find.
}

# Marketing lives on the same domains as confirmations. This is the line between
# a clean profile and a profile full of newsletters.
DROP_SUBJECTS = ["newsletter", "hottest", "this week", "unsubscribe", "% off", "now open"]

QUERY_FRAGMENT = ""  # TODO(A): "from:(resy.com OR ...) newer_than:2y"


def classify(sender: str, subject: str) -> str | None:
    """Return a vendor key, or None to DROP. Precision over recall (PRD 5.4)."""
    raise NotImplementedError
