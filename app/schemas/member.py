from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.schemas.user import UserRead


class MemberCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    phone_number: str = Field(min_length=7, max_length=32)
    address: str | None = Field(default=None, max_length=255)


class MemberUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone_number: str | None = Field(default=None, min_length=7, max_length=32)
    address: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def reject_empty_update(self) -> "MemberUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    membership_id: str
    phone_number: str
    address: str | None
    membership_start_date: date
    is_active: bool
    deactivated_at: datetime | None
    created_at: datetime
    user: UserRead


class BorrowingHistoryItem(BaseModel):
    loan_id: UUID
    book_id: UUID
    book_title: str
    borrowed_at: datetime
    due_at: datetime
    returned_at: datetime | None
    status: str


class BorrowingHistoryRead(BaseModel):
    member_id: UUID
    membership_id: str
    total: int
    items: list[BorrowingHistoryItem]
