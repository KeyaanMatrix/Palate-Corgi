"""Deterministic Stage-1 filtering of raw messages."""

from palate import db

from .vendors import classify


def run(limit: int | None = None) -> dict[str, int]:
    """Classify raw Gmail messages and set matched_vendor.

    Unmatched messages remain NULL and will not be sent to the LLM.
    Returns counts by matched vendor.
    """
    sql = """
        SELECT id, sender, subject
        FROM raw_message
        WHERE source = 'gmail'
          AND extracted = 0
        ORDER BY fetched_at
    """

    params = ()

    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)

    with db.connect() as conn:
        rows = conn.execute(sql, params).fetchall()

        counts: dict[str, int] = {}

        for row in rows:
            vendor = classify(
                row["sender"] or "",
                row["subject"] or "",
            )

            conn.execute(
                """
                UPDATE raw_message
                SET matched_vendor = ?,
                    extracted = CASE WHEN ? IS NULL THEN 1 ELSE extracted END,
                    sender = CASE WHEN ? IS NULL THEN NULL ELSE sender END,
                    subject = CASE WHEN ? IS NULL THEN NULL ELSE subject END,
                    body = CASE WHEN ? IS NULL THEN NULL ELSE body END
                WHERE id = ?
                """,
                (vendor, vendor, vendor, vendor, vendor, row["id"]),
            )

            if vendor is not None:
                counts[vendor] = counts.get(vendor, 0) + 1

    return counts
