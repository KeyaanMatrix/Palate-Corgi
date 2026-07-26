"""Calendar → raw_message. OWNER A. See docs/trd-a-ingest.md step 4.

Lower value than Gmail: pace, trip date ranges, deletions. If you are behind at
9:30 PM, SKIP THIS and come back at 2:00 AM. Gmail is the product.
"""


def run_sync(months_back: int = 24) -> int:
    raise NotImplementedError
