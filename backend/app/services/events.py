from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.models.domain import UserRole
from app.repositories.base import object_id, to_id
from app.schemas.events import EventCreate, EventPublic, EventUpdate, PaginatedEvents, RecurrenceCreate, RegistrationPublic, SessionPublic


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _event_public(event: dict, is_registered: bool = False, has_feedback: bool = False) -> EventPublic:
    sessions = [
        SessionPublic(
            title=s["title"],
            start_at=s["start_at"],
            end_at=s["end_at"],
            location=s.get("location", ""),
        )
        for s in event.get("sessions", [])
    ]
    return EventPublic(
        id=event["id"],
        event_code=event.get("event_code", event["id"][-8:].upper()),
        title=event["title"],
        description=event.get("description", ""),
        location=event.get("location", ""),
        start_at=event["start_at"],
        end_at=event["end_at"],
        google_form_url=event.get("google_form_url"),
        feedback_questions=event.get("feedback_questions", []),
        sessions=sessions,
        feedback_open=bool(event.get("feedback_open")) or event["end_at"] <= datetime.now(UTC),
        registration_count=event.get("registration_count", 0),
        is_registered=is_registered,
        has_feedback=has_feedback,
        created_by=str(event.get("created_by", "")),
    )


def _generate_sessions(recurrence: RecurrenceCreate) -> list[dict]:
    sessions = []
    current = _utc(recurrence.first_start_at)
    duration = timedelta(minutes=recurrence.duration_minutes)
    for i in range(recurrence.count):
        if recurrence.pattern == "weekdays":
            while current.weekday() >= 5:  # 5=Saturday, 6=Sunday
                current += timedelta(days=1)
        sessions.append({
            "title": f"{recurrence.title_prefix} {i + 1}",
            "start_at": current,
            "end_at": current + duration,
            "location": "",
        })
        if recurrence.pattern == "weekly":
            current += timedelta(weeks=1)
        else:
            current += timedelta(days=1)
    return sessions


async def create_event(db: AsyncIOMotorDatabase, payload: EventCreate, user: dict) -> EventPublic:
    now = datetime.now(UTC)

    if payload.recurrence:
        sessions = _generate_sessions(payload.recurrence)
        start_at = sessions[0]["start_at"]
        end_at = sessions[-1]["end_at"]
        if start_at < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="First session must be in the future")
    else:
        sessions = [
            {"title": s.title, "start_at": _utc(s.start_at), "end_at": _utc(s.end_at), "location": s.location}
            for s in payload.sessions
        ]
        start_at = _utc(payload.start_at)
        end_at = _utc(payload.end_at)
        if start_at < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be present or future")
        if end_at <= start_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time")

    if payload.idempotency_key:
        existing = await db.events.find_one({"idempotency_key": payload.idempotency_key})
        if existing:
            return _event_public(to_id(existing))

    next_value = await db.counters.find_one_and_update(
        {"_id": "event_code"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    event = {
        "event_code": f"EVT-{next_value['seq']:05d}",
        "title": payload.title,
        "description": payload.description,
        "location": payload.location,
        "start_at": start_at,
        "end_at": end_at,
        "google_form_url": str(payload.google_form_url) if payload.google_form_url else None,
        "feedback_questions": [question.strip() for question in payload.feedback_questions if question.strip()][:10],
        "sessions": sessions,
        "feedback_open": end_at <= now,
        "registration_count": 0,
        "idempotency_key": payload.idempotency_key,
        "created_by": object_id(user["id"]),
        "created_at": now,
    }
    try:
        result = await db.events.insert_one(event)
    except DuplicateKeyError:
        if payload.idempotency_key:
            existing = await db.events.find_one({"idempotency_key": payload.idempotency_key})
            if existing:
                return _event_public(to_id(existing))
        raise
    created = await db.events.find_one({"_id": result.inserted_id})
    return _event_public(to_id(created))


async def list_events(
    db: AsyncIOMotorDatabase,
    user: dict | None,
    page: int,
    page_size: int,
) -> PaginatedEvents:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    skip = (page - 1) * page_size
    now = datetime.now(UTC)

    is_admin = user and user.get("role") == UserRole.ADMIN

    if is_admin:
        query: dict = {}
    elif user:
        user_oid = object_id(user["id"])
        registered_oids = {
            doc["event_id"]
            async for doc in db.registrations.find({"user_id": user_oid}, {"event_id": 1})
        }
        feedback_oids = {
            doc["event_id"]
            async for doc in db.feedback.find({"user_id": user_oid}, {"event_id": 1})
        }
        # Past events where user is registered but hasn't submitted feedback yet
        pending_oids = list(registered_oids - feedback_oids)
        if pending_oids:
            query = {"$or": [{"end_at": {"$gt": now}}, {"_id": {"$in": pending_oids}}]}
        else:
            query = {"end_at": {"$gt": now}}
    else:
        query = {"end_at": {"$gt": now}}

    cursor = db.events.find(query).sort("start_at", -1).skip(skip).limit(page_size)
    events = [to_id(event) async for event in cursor]
    total = await db.events.count_documents(query)

    registrations: set[str] = set()
    feedback: set[str] = set()
    if user and events:
        event_ids = [object_id(event["id"]) for event in events]
        registrations = {
            str(doc["event_id"])
            async for doc in db.registrations.find({"user_id": object_id(user["id"]), "event_id": {"$in": event_ids}})
        }
        feedback = {
            str(doc["event_id"])
            async for doc in db.feedback.find({"user_id": object_id(user["id"]), "event_id": {"$in": event_ids}})
        }

    return PaginatedEvents(
        items=[_event_public(event, event["id"] in registrations, event["id"] in feedback) for event in events],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_event(db: AsyncIOMotorDatabase, event_id: str, user: dict | None) -> EventPublic:
    event = await db.events.find_one({"_id": object_id(event_id)})
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event = to_id(event)
    is_registered = False
    has_feedback = False
    if user:
        user_id = object_id(user["id"])
        event_oid = object_id(event_id)
        is_registered = await db.registrations.find_one({"event_id": event_oid, "user_id": user_id}) is not None
        has_feedback = await db.feedback.find_one({"event_id": event_oid, "user_id": user_id}) is not None
    return _event_public(event, is_registered, has_feedback)


async def register_for_event(db: AsyncIOMotorDatabase, event_id: str, user: dict) -> EventPublic:
    if user["role"] == UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot register for events")
    event_oid = object_id(event_id)
    event = await db.events.find_one({"_id": event_oid})
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event["end_at"] <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration is closed")

    try:
        await db.registrations.insert_one(
            {"event_id": event_oid, "user_id": object_id(user["id"]), "registered_at": datetime.now(UTC)}
        )
        await db.events.update_one({"_id": event_oid}, {"$inc": {"registration_count": 1}})
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already registered") from exc
    return await get_event(db, event_id, user)


async def list_event_registrations(db: AsyncIOMotorDatabase, event_id: str) -> list[RegistrationPublic]:
    event_oid = object_id(event_id)
    if not await db.events.find_one({"_id": event_oid}):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    cursor = db.registrations.aggregate(
        [
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
            {"$sort": {"registered_at": -1}},
            {"$limit": 1000},
        ]
    )
    registrations: list[RegistrationPublic] = []
    async for item in cursor:
        registrations.append(
            RegistrationPublic(
                id=str(item["_id"]),
                user_id=str(item["user_id"]),
                user_name=item["user"]["name"],
                user_email=item["user"]["email"],
                registered_at=item["registered_at"],
            )
        )
    return registrations


async def mark_feedback_open_for_completed_events(db: AsyncIOMotorDatabase) -> int:
    result = await db.events.update_many(
        {"end_at": {"$lte": datetime.now(UTC)}, "feedback_open": {"$ne": True}},
        {"$set": {"feedback_open": True, "feedback_opened_at": datetime.now(UTC)}},
    )
    return result.modified_count


async def delete_event(db: AsyncIOMotorDatabase, event_id: str) -> None:
    result = await db.events.delete_one({"_id": object_id(event_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")


async def update_event(db: AsyncIOMotorDatabase, event_id: str, payload: EventUpdate, user: dict) -> EventPublic:
    event_oid = object_id(event_id)
    event = await db.events.find_one({"_id": event_oid})
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if str(event.get("created_by", "")) != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit events you created")

    updates: dict = {}
    if payload.title is not None:
        updates["title"] = payload.title
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.location is not None:
        updates["location"] = payload.location
    if payload.start_at is not None:
        updates["start_at"] = _utc(payload.start_at)
    if payload.end_at is not None:
        updates["end_at"] = _utc(payload.end_at)
    if payload.google_form_url is not None:
        updates["google_form_url"] = str(payload.google_form_url)
    if payload.feedback_questions is not None:
        updates["feedback_questions"] = [q.strip() for q in payload.feedback_questions if q.strip()][:10]

    # Validate date consistency if either bound is being changed
    new_start = updates.get("start_at", event["start_at"])
    new_end = updates.get("end_at", event["end_at"])
    if _utc(new_end) <= _utc(new_start):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_at must be after start_at")

    if updates:
        await db.events.update_one({"_id": event_oid}, {"$set": updates})
    return await get_event(db, event_id, user)
