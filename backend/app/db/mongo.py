from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.core.config import get_settings


client: AsyncIOMotorClient | None = None


def get_database() -> AsyncIOMotorDatabase:
    if client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return client[get_settings().database_name]


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index([("email", ASCENDING)], unique=True)
    await db.users.create_index([("role", ASCENDING)])
    await db.admin_otps.create_index([("email", ASCENDING), ("used", ASCENDING)])
    await db.admin_otps.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db.student_otps.create_index([("email", ASCENDING), ("used", ASCENDING)])
    await db.student_otps.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    await db.events.create_index([("start_at", ASCENDING)])
    await db.events.create_index([("end_at", ASCENDING), ("feedback_open", ASCENDING)])
    await db.events.create_index([("created_by", ASCENDING), ("created_at", DESCENDING)])
    await db.events.create_index([("event_code", ASCENDING)], unique=True, sparse=True)
    await db.events.create_index([("idempotency_key", ASCENDING)], unique=True, sparse=True)

    await db.registrations.create_index([("event_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    await db.registrations.create_index([("user_id", ASCENDING), ("registered_at", DESCENDING)])

    await db.feedback.create_index([("event_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    await db.feedback.create_index([("event_id", ASCENDING), ("submitted_at", DESCENDING)])


@asynccontextmanager
async def mongo_lifespan() -> AsyncIterator[AsyncIOMotorDatabase]:
    global client
    settings = get_settings()
    client = AsyncIOMotorClient(
        settings.mongo_uri,
        uuidRepresentation="standard",
        tz_aware=True,
        serverSelectionTimeoutMS=5000,
    )
    db = client[settings.database_name]
    await create_indexes(db)
    try:
        yield db
    finally:
        client.close()
        client = None
