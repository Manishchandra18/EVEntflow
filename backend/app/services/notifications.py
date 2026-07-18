"""
Automatic feedback-request emails.

send_feedback_request_emails() is called by the background sweeper after
mark_feedback_open_for_completed_events() runs.  It finds every event that
has feedback_open=True but hasn't had its notification sent yet
(feedback_email_sent is absent or False), sends a personalised email to each
registered student listing all feedback questions, then marks the event so it
won't be emailed again.
"""

import asyncio
import logging
from datetime import UTC, datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.email import send_email
from app.repositories.base import object_id

logger = logging.getLogger(__name__)


def _build_email_body(student_name: str, event: dict, frontend_url: str) -> str:
    title = event["title"]
    location = event.get("location", "")
    end_at = event["end_at"]
    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)
    ended_str = end_at.strftime("%d %b %Y, %H:%M UTC")

    questions = event.get("feedback_questions", [])
    google_form_url = event.get("google_form_url") or ""

    lines = [
        f"Hi {student_name},",
        "",
        f'Thank you for attending "{title}"' + (f" at {location}" if location else "") + f", which ended on {ended_str}.",
        "",
        "We'd love to hear your thoughts. Please take a moment to fill in the feedback form.",
        "",
        "── What we'd like to know ──────────────────────────",
        "",
        "★ Overall rating  (please rate from 1 to 5)",
        "   1 = Poor  |  2 = Fair  |  3 = Good  |  4 = Very good  |  5 = Excellent",
        "",
        "✎ Comments  (any additional thoughts or suggestions)",
        "",
    ]

    for i, question in enumerate(questions, start=1):
        lines.append(f"Q{i}. {question}")
        lines.append("")

    lines += [
        "────────────────────────────────────────────────────",
        "",
    ]

    if google_form_url:
        lines += [
            "Submit your feedback using the form below:",
            f"  {google_form_url}",
            "",
            f"Already logged in? Submit directly on the platform: {frontend_url}/events/{event['id']}",
        ]
    else:
        lines += [
            f"Submit your feedback here: {frontend_url}/events/{event['id']}",
        ]

    lines += [
        "",
        "Thank you!",
        "EventFlow Team",
    ]

    return "\n".join(lines)


async def send_feedback_request_emails(db: AsyncIOMotorDatabase) -> None:
    """Find newly-opened events and email every registered student."""
    settings = get_settings()
    frontend_url = settings.frontend_url.rstrip("/")

    # Atomically claim one unclaimed event at a time so multiple workers
    # can never both pick up the same event and double-send emails.
    while True:
        raw_event = await db.events.find_one_and_update(
            {"feedback_open": True, "feedback_email_sent": {"$ne": True}},
            {"$set": {"feedback_email_sent": True, "feedback_email_sent_at": datetime.now(UTC)}},
        )
        if raw_event is None:
            break

        event_oid = raw_event["_id"]
        event = {**raw_event, "id": str(event_oid)}

        # Collect all registered students (role=user) via aggregation
        pipeline = [
            {"$match": {"event_id": event_oid}},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {"$unwind": "$user"},
            {"$match": {"user.role": "user"}},
            {"$project": {"_id": 0, "name": "$user.name", "email": "$user.email"}},
        ]
        registrants = await db.registrations.aggregate(pipeline).to_list(length=None)

        if not registrants:
            continue

        subject = f"Feedback requested: {event['title']}"

        send_tasks = [
            send_email(
                to=r["email"],
                subject=subject,
                body=_build_email_body(r["name"], event, frontend_url),
            )
            for r in registrants
        ]

        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        sent = sum(1 for r in results if not isinstance(r, Exception))
        failed = [str(r) for r in results if isinstance(r, Exception)]
        logger.info(
            "Feedback emails for event %s (%s): sent=%d failed=%d",
            event["id"],
            event["title"],
            sent,
            len(failed),
        )
        for err in failed:
            logger.warning("Feedback email error for event %s: %s", event["id"], err)
