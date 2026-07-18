from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import admin_user, current_user, get_db
from app.schemas.feedback import EventFeedbackSummary, FeedbackCreate, FeedbackPublic
from app.services.feedback import get_feedback_status, submit_feedback, summarize_event_feedback

router = APIRouter(prefix="/events/{event_id}/feedback", tags=["feedback"])


@router.get("/status")
async def status(
    event_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(current_user)],
) -> dict:
    return await get_feedback_status(db, event_id, user)


@router.post("", response_model=FeedbackPublic, status_code=201)
async def submit(
    event_id: str,
    payload: FeedbackCreate,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(current_user)],
) -> FeedbackPublic:
    return await submit_feedback(db, event_id, user, payload)


@router.get("/responses", response_model=EventFeedbackSummary)
async def responses(
    event_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _: Annotated[dict, Depends(admin_user)],
) -> EventFeedbackSummary:
    return await summarize_event_feedback(db, event_id)
