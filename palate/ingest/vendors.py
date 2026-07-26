"""Known booking vendors and deterministic Stage-1 filtering."""

VENDORS = {
    "resy": {
        "domains": ["resy.com"],
        "subjects": ["reservation", "confirmed", "cancelled", "canceled"],
    },
    "opentable": {
        "domains": ["opentable.com"],
        "subjects": ["reservation", "table", "booked", "cancel"],
    },
    "tock": {
        "domains": ["exploretock.com", "tock.com"],
        "subjects": ["reservation", "ticket"],
    },
    "sevenrooms": {
        "domains": ["sevenrooms.com"],
        "subjects": ["reservation"],
    },
    "eventbrite": {
        "domains": ["eventbrite.com"],
        "subjects": ["ticket", "order confirm"],
    },
    "dice": {
        "domains": ["dice.fm"],
        "subjects": ["ticket"],
    },
    "airbnb": {
        "domains": ["airbnb.com"],
        "subjects": ["reservation", "itinerary"],
    },
    "marriott": {
        "domains": ["marriott.com"],
        "subjects": ["reservation", "confirmation"],
    },
    "hyatt": {
        "domains": ["hyatt.com"],
        "subjects": ["reservation", "confirmation"],
    },
    "united": {
        "domains": ["united.com"],
        "subjects": ["confirmation", "reservation", "itinerary"],
    },
    "delta": {
        "domains": ["delta.com"],
        "subjects": [
            "confirmation",
            "reservation",
            "itinerary",
            "check in",
            "check-in",
        ],
    },
    "alaska": {
        "domains": ["alaskaair.com"],
        "subjects": ["confirmation", "reservation", "itinerary"],
    },
}


def _all_domains() -> list[str]:
    return sorted(
        {
            domain
            for vendor in VENDORS.values()
            for domain in vendor["domains"]
        }
    )


QUERY_FRAGMENT = (
    "from:("
    + " OR ".join(_all_domains())
    + ")"
)


def classify(sender: str, subject: str) -> str | None:
    """Return vendor key for likely transactional mail, otherwise None.

    Require both a known sender domain and a booking-related subject.
    Precision is more important than recall.
    """
    sender_lower = (sender or "").lower()
    subject_lower = (subject or "").lower()

    for vendor, rules in VENDORS.items():
        domain_match = any(
            domain.lower() in sender_lower
            for domain in rules["domains"]
        )

        if not domain_match:
            continue

        subject_match = any(
            keyword.lower() in subject_lower
            for keyword in rules["subjects"]
        )

        if subject_match:
            return vendor

    return None