"""Stage-1 runner. OWNER A. See docs/trd-a-ingest.md step 6."""


def run(limit: int | None = None) -> dict[str, int]:
    """Classify unclassified raw_message rows. Returns {vendor: count}.

    Unmatched messages are DROPPED, not queued. Sending them to the model to
    'see what happens' is how the $20 Gateway credit disappears.
    """
    raise NotImplementedError
