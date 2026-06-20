from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.reservation import ReservationStatus


class ReservationCreate(BaseModel):
    book_id: UUID


class ReservationUpdate(BaseModel):
    status: ReservationStatus


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    member_id: UUID
    book_id: UUID
    status: ReservationStatus
    queue_position: int | None = None
    queued_at: datetime
    ready_at: datetime | None
    fulfilled_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
