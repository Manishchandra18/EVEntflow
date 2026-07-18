from typing import Annotated

from fastapi import APIRouter, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import current_user, get_db
from app.core.limiter import limiter
from app.schemas.auth import AdminOtpRequest, StudentOtpRequest, TokenResponse, UserCreate, UserLogin, UserPublic
from app.services.auth import login_user, public_user, register_user, request_admin_otp, request_student_otp

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: UserCreate, db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> TokenResponse:
    return await register_user(db, payload)


@router.post("/student-otp")
@limiter.limit("3/10minutes")
async def student_otp(request: Request, payload: StudentOtpRequest, db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> dict[str, str]:
    return await request_student_otp(db, payload.email)


@router.post("/admin-otp")
@limiter.limit("3/10minutes")
async def admin_otp(request: Request, payload: AdminOtpRequest, db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> dict[str, str]:
    return await request_admin_otp(db, payload.superadmin_email)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> TokenResponse:
    return await login_user(db, payload)


@router.get("/me", response_model=UserPublic)
async def me(user: Annotated[dict, Depends(current_user)]) -> UserPublic:
    return public_user(user)
