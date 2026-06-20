from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.loan import LoanStatus


class LoanCreate(BaseModel):
    member_id: UUID
    book_id: UUID
    due_at: datetime | None = None


class LoanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    member_id: UUID
    book_id: UUID
    issued_by_user_id: UUID
    returned_by_user_id: UUID | None
    borrowed_at: datetime
    due_at: datetime
    returned_at: datetime | None
    status: LoanStatus
    created_at: datetime
