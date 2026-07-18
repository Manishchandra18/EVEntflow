from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.mongo import get_database
from app.models.domain import UserRole
from app.repositories.users import find_user_by_id


def get_db() -> AsyncIOMotorDatabase:
    return get_database()


async def current_user(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = await find_user_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


async def admin_user(user: Annotated[dict, Depends(current_user)]) -> dict:
    if user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def superadmin_user(user: Annotated[dict, Depends(current_user)]) -> dict:
    if user["role"] != UserRole.ADMIN or user["email"] != get_settings().super_admin_email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super-admin access required")
    return user
