from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)
    answers: dict[str, str] = Field(default_factory=dict)


class FeedbackPublic(BaseModel):
    id: str
    event_id: str
    user_id: str
    user_name: str
    rating: int
    comment: str
    answers: dict[str, str] = {}
    submitted_at: datetime


class EventFeedbackSummary(BaseModel):
    event_id: str
    event_title: str
    response_count: int
    average_rating: float | None
    responses: list[FeedbackPublic]
