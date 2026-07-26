"""Google Calendar -> raw_message. OWNER A."""

from datetime import datetime, timedelta, timezone

from palate import db

from .google_auth import calendar_service


def run_sync(months_back: int = 24) -> int:
    """Calendar events -> raw_message rows with source='calendar'."""
    service = calendar_service()

    time_min = (
        datetime.now(timezone.utc) - timedelta(days=months_back * 30)
    ).isoformat()

    page_token = None
    count = 0

    while True:
        response = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            )
            .execute()
        )

        for event in response.get("items", []):
            event_id = event.get("id")
            if not event_id:
                continue

            summary = event.get("summary", "")
            location = event.get("location", "")

            start = event.get("start", {})
            start_value = start.get("dateTime") or start.get("date")

            body = "\n".join(
                x
                for x in [
                    f"Summary: {summary}" if summary else "",
                    f"Location: {location}" if location else "",
                    f"Start: {start_value}" if start_value else "",
                ]
                if x
            )

            db.execute(
                """
                INSERT INTO raw_message (
                    id,
                    source,
                    sender,
                    subject,
                    body,
                    received_at,
                    matched_vendor,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(id) DO UPDATE SET
                    source = excluded.source,
                    subject = CASE
                        WHEN raw_message.extracted = 0 THEN excluded.subject
                        ELSE NULL
                    END,
                    body = CASE
                        WHEN raw_message.extracted = 0 THEN excluded.body
                        ELSE NULL
                    END,
                    received_at = excluded.received_at,
                    matched_vendor = excluded.matched_vendor,
                    fetched_at = excluded.fetched_at
                """,
                (
                    f"calendar:{event_id}",
                    "calendar",
                    None,
                    summary,
                    body,
                    start_value,
                    "calendar",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            count += 1

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return count
