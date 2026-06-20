from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    title: str
    message: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    read_at: datetime | None
    is_read: bool
    created_at: datetime


class UnreadNotificationCount(BaseModel):
    count: int


class OverdueNotificationResult(BaseModel):
    created: int
