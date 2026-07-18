from datetime import UTC, datetime

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.repositories.base import object_id, to_id
from app.schemas.feedback import EventFeedbackSummary, FeedbackCreate, FeedbackPublic


async def ensure_feedback_access(db: AsyncIOMotorDatabase, event_id: str, user: dict) -> dict:
    event_oid = object_id(event_id)
    event = await db.events.find_one({"_id": event_oid})
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event["end_at"] > datetime.now(UTC) and not event.get("feedback_open"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Feedback opens after the event ends")
    registration = await db.registrations.find_one({"event_id": event_oid, "user_id": object_id(user["id"])})
    if not registration:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only registered users can submit feedback")
    return event


async def submit_feedback(
    db: AsyncIOMotorDatabase,
    event_id: str,
    user: dict,
    payload: FeedbackCreate,
) -> FeedbackPublic:
    event = await ensure_feedback_access(db, event_id, user)
    feedback = {
        "event_id": object_id(event_id),
        "user_id": object_id(user["id"]),
        "user_name": user["name"],
        "rating": payload.rating,
        "comment": payload.comment,
        "answers": payload.answers,
        "submitted_at": datetime.now(UTC),
    }
    try:
        result = await db.feedback.insert_one(feedback)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feedback already submitted") from exc
    created = to_id(await db.feedback.find_one({"_id": result.inserted_id}))
    created["event_id"] = str(created["event_id"])
    created["user_id"] = str(created["user_id"])
    return FeedbackPublic(**created)


async def get_feedback_status(db: AsyncIOMotorDatabase, event_id: str, user: dict) -> dict:
    event = await ensure_feedback_access(db, event_id, user)
    existing = await db.feedback.find_one({"event_id": object_id(event_id), "user_id": object_id(user["id"])})
    return {
        "event_id": event_id,
        "event_title": event["title"],
        "available": True,
        "submitted": existing is not None,
    }


async def summarize_event_feedback(db: AsyncIOMotorDatabase, event_id: str) -> EventFeedbackSummary:
    event = await db.events.find_one({"_id": object_id(event_id)})
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    pipeline = [
        {"$match": {"event_id": object_id(event_id)}},
        {"$group": {"_id": "$event_id", "count": {"$sum": 1}, "avg": {"$avg": "$rating"}}},
    ]
    summary = await db.feedback.aggregate(pipeline).to_list(length=1)
    cursor = db.feedback.find({"event_id": object_id(event_id)}).sort("submitted_at", -1).limit(200)
    responses: list[FeedbackPublic] = []
    async for item in cursor:
        item = to_id(item)
        item["event_id"] = str(item["event_id"])
        item["user_id"] = str(item["user_id"])
        responses.append(FeedbackPublic(**item))
    return EventFeedbackSummary(
        event_id=event_id,
        event_title=event["title"],
        response_count=summary[0]["count"] if summary else 0,
        average_rating=round(summary[0]["avg"], 2) if summary else None,
        responses=responses,
    )
