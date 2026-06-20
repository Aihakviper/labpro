from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.fine import FineStatus


class FineConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    daily_rate: Decimal
    updated_at: datetime


class FineConfigUpdate(BaseModel):
    daily_rate: Decimal = Field(ge=0, decimal_places=2, max_digits=12)


class FinePaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)


class FinePaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    recorded_by_user_id: UUID
    paid_at: datetime


class FineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loan_id: UUID
    overdue_days: int
    daily_rate: Decimal
    amount: Decimal
    amount_paid: Decimal
    outstanding_amount: Decimal
    status: FineStatus
    paid_at: datetime | None
    created_at: datetime
    payments: list[FinePaymentRead]
