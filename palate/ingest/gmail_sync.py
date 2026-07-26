"""Gmail → raw_message. OWNER A. See docs/trd-a-ingest.md step 3.

Truncate bodies to ~4000 chars: confirmation emails put everything useful up
top, and this is what keeps extraction token cost inside the $20 credit.
"""

BODY_LIMIT = 4000


def run_sync(limit: int = 500, since: str = "2y") -> int:
    """Fetch messages matching vendors.QUERY_FRAGMENT into raw_message.

    INSERT OR REPLACE on the Gmail message id, so re-running is free.
    """
    raise NotImplementedError
