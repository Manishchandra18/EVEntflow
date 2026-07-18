import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import auth, events, feedback
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.mongo import get_database, mongo_lifespan
from app.services.events import mark_feedback_open_for_completed_events
from app.services.notifications import send_feedback_request_emails


async def feedback_sweeper(stop: asyncio.Event) -> None:
    settings = get_settings()
    while not stop.is_set():
        db = get_database()
        await mark_feedback_open_for_completed_events(db)
        await send_feedback_request_emails(db)
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.feedback_sweep_seconds)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mongo_lifespan():
        stop = asyncio.Event()
        task = asyncio.create_task(feedback_sweeper(stop))
        yield
        stop.set()
        await task


app = FastAPI(title="Event Participation API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
