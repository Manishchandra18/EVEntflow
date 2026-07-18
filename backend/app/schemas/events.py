from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    start_at: datetime
    end_at: datetime
    location: str = Field(default="", max_length=160)


class SessionPublic(BaseModel):
    title: str
    start_at: datetime
    end_at: datetime
    location: str


class RecurrenceCreate(BaseModel):
    pattern: Literal["daily", "weekly", "weekdays"]
    count: int = Field(ge=1, le=52)
    duration_minutes: int = Field(ge=5, le=480)
    first_start_at: datetime
    title_prefix: str = Field(default="Session", max_length=60)


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=160)
    start_at: datetime | None = None
    end_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=80)
    google_form_url: str | None = Field(default=None, max_length=500)
    feedback_questions: list[str] = Field(default_factory=list, max_length=10)
    sessions: list[SessionCreate] = Field(default_factory=list)
    recurrence: RecurrenceCreate | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        # When recurrence is provided the service derives start/end from
        # the generated sessions, so skip the envelope check here.
        if self.recurrence:
            return self

        if not self.start_at or not self.end_at:
            raise ValueError("start_at and end_at are required when no recurrence is provided")

        def comparable(value: datetime) -> datetime:
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

        start_at = comparable(self.start_at)
        end_at = comparable(self.end_at)
        now = datetime.now(UTC)
        if start_at < now:
            raise ValueError("start_at must be present or future")
        if end_at <= start_at:
            raise ValueError("end_at must be after start_at")
        return self


class EventPublic(BaseModel):
    id: str
    event_code: str
    title: str
    description: str
    location: str
    start_at: datetime
    end_at: datetime
    google_form_url: str | None = None
    feedback_questions: list[str] = []
    sessions: list[SessionPublic] = []
    feedback_open: bool
    registration_count: int = 0
    is_registered: bool = False
    has_feedback: bool = False
    created_by: str = ""


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=160)
    start_at: datetime | None = None
    end_at: datetime | None = None
    google_form_url: str | None = None
    feedback_questions: list[str] | None = None


class RegistrationPublic(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_email: str
    registered_at: datetime


class PaginatedEvents(BaseModel):
    items: list[EventPublic]
    total: int
    page: int
    page_size: int
