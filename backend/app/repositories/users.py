from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import object_id, to_id


async def find_user_by_email(db: AsyncIOMotorDatabase, email: str) -> dict | None:
    user = await db.users.find_one({"email": email.lower()})
    return to_id(user) if user else None


async def find_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> dict | None:
    user = await db.users.find_one({"_id": object_id(user_id)})
    return to_id(user) if user else None


async def insert_user(db: AsyncIOMotorDatabase, user: dict) -> dict:
    result = await db.users.insert_one(user)
    created = await db.users.find_one({"_id": result.inserted_id})
    return to_id(created)
