import random
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.email import send_email
from app.core.security import create_access_token, hash_password, verify_password
from app.models.domain import UserRole
from app.repositories.users import find_user_by_email, insert_user
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserPublic


def public_user(user: dict) -> UserPublic:
    return UserPublic(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        role=user["role"],
        is_superadmin=user["email"] == get_settings().super_admin_email,
    )


def _generate_otp() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


# ── Student OTP ──────────────────────────────────────────────────────────────

async def request_student_otp(db: AsyncIOMotorDatabase, email: str) -> dict[str, str]:
    normalized = email.lower()
    otp = _generate_otp()
    await db.student_otps.insert_one(
        {
            "email": normalized,
            "otp": otp,
            "used": False,
            "created_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC) + timedelta(minutes=10),
        }
    )
    await send_email(
        to=normalized,
        subject="EventFlow — verify your email",
        body=f"Your registration OTP is: {otp}\nIt expires in 10 minutes.",
    )
    return {"message": f"OTP sent to {normalized}"}


async def consume_student_otp(db: AsyncIOMotorDatabase, email: str, otp: str | None) -> None:
    if not otp:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email OTP is required for student registration")
    latest = await db.student_otps.find_one(
        {"email": email},
        sort=[("created_at", -1)],
    )
    if (
        not latest
        or latest.get("otp") != otp
        or latest.get("used")
        or latest.get("expires_at") <= datetime.now(UTC)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired email OTP")
    await db.student_otps.update_one(
        {"_id": latest["_id"]},
        {"$set": {"used": True, "used_at": datetime.now(UTC)}},
    )


# ── Admin OTP ─────────────────────────────────────────────────────────────────

async def request_admin_otp(db: AsyncIOMotorDatabase, superadmin_email: str) -> dict[str, str]:
    normalized = superadmin_email.lower()
    otp = _generate_otp()
    await db.admin_otps.insert_one(
        {
            "email": normalized,
            "otp": otp,
            "used": False,
            "created_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC) + timedelta(minutes=10),
        }
    )
    await send_email(
        to=normalized,
        subject="EventFlow — admin registration OTP",
        body=f"An admin registration was requested. OTP: {otp}\nIt expires in 10 minutes.",
    )
    return {"message": f"Admin OTP sent to {normalized}"}


async def consume_admin_otp(db: AsyncIOMotorDatabase, superadmin_email: str, otp: str | None) -> None:
    if not otp:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin OTP is required")
    latest = await db.admin_otps.find_one(
        {"email": superadmin_email},
        sort=[("created_at", -1)],
    )
    if (
        not latest
        or latest.get("otp") != otp
        or latest.get("used")
        or latest.get("expires_at") <= datetime.now(UTC)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired admin OTP")
    await db.admin_otps.update_one(
        {"_id": latest["_id"]},
        {"$set": {"used": True, "used_at": datetime.now(UTC)}},
    )


# ── Register / Login ──────────────────────────────────────────────────────────

async def register_user(db: AsyncIOMotorDatabase, payload: UserCreate) -> TokenResponse:
    email = payload.email.lower()

    if payload.admin_otp is not None:
        # Admin flow: validate OTP that was sent to the superadmin's email
        if not payload.superadmin_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="superadmin_email is required for admin registration",
            )
        await consume_admin_otp(db, payload.superadmin_email.lower(), payload.admin_otp)
        role = UserRole.ADMIN
    elif payload.student_otp is not None:
        # Student flow: validate OTP that was sent to the student's own email
        await consume_student_otp(db, email, payload.student_otp)
        role = UserRole.USER
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An OTP is required. Use the student or admin registration flow.",
        )

    user = {
        "name": payload.name,
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": role,
        "created_at": datetime.now(UTC),
    }
    try:
        created = await insert_user(db, user)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    token = create_access_token(created["id"], created["role"])
    return TokenResponse(access_token=token, user=public_user(created))


async def login_user(db: AsyncIOMotorDatabase, payload: UserLogin) -> TokenResponse:
    user = await find_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(user["id"], user["role"])
    return TokenResponse(access_token=token, user=public_user(user))
