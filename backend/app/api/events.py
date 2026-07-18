from typing import Annotated

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import admin_user, current_user, get_db, superadmin_user
from app.schemas.events import EventCreate, EventPublic, EventUpdate, PaginatedEvents, RegistrationPublic
from app.services.events import (
    create_event,
    delete_event,
    get_event,
    list_event_registrations,
    list_events,
    register_for_event,
    update_event,
)

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=PaginatedEvents)
async def events(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=50),
) -> PaginatedEvents:
    return await list_events(db, user, page, page_size)


@router.post("", response_model=EventPublic, status_code=201)
async def create(
    payload: EventCreate,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(admin_user)],
) -> EventPublic:
    return await create_event(db, payload, user)


@router.get("/{event_id}", response_model=EventPublic)
async def detail(
    event_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(current_user)],
) -> EventPublic:
    return await get_event(db, event_id, user)


@router.patch("/{event_id}", response_model=EventPublic)
async def edit(
    event_id: str,
    payload: EventUpdate,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(admin_user)],
) -> EventPublic:
    return await update_event(db, event_id, payload, user)


@router.delete("/{event_id}", status_code=204)
async def remove(
    event_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _: Annotated[dict, Depends(superadmin_user)],
) -> None:
    await delete_event(db, event_id)


@router.post("/{event_id}/register", response_model=EventPublic)
async def register(
    event_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    user: Annotated[dict, Depends(current_user)],
) -> EventPublic:
    return await register_for_event(db, event_id, user)


@router.get("/{event_id}/registrations", response_model=list[RegistrationPublic])
async def registrations(
    event_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _: Annotated[dict, Depends(admin_user)],
) -> list[RegistrationPublic]:
    return await list_event_registrations(db, event_id)
