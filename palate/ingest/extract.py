"""Stage-2 LLM extraction. OWNER A. See docs/trd-a-ingest.md step 7.

Routed through Merge Gateway via palate.llm — you do not call Anthropic directly.
"""

from palate import contracts, llm  # noqa: F401  (llm is the Gateway seam)

BATCH_SIZE = 20

PROMPT_RULES = """\
Extract one entry per booking. Times are LOCAL WALL-CLOCK with no timezone —
copy what the email says. If a field is not stated, return null; never infer or
estimate. A cancellation email for a prior booking is status "cancelled" with
cancelled_at set. Ignore marketing email entirely.
"""


def extract_pending(batch_size: int = BATCH_SIZE) -> int:
    """Batch matched messages → visit rows. Returns rows written.

    llm.complete_json returning None means DROP THE BATCH. Do not retry, do not
    repair. Recall is not the constraint tonight; precision is.
    """
    raise NotImplementedError
