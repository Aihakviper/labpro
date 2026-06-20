from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.fine import FineStatus
from app.models.loan import LoanStatus


class ReportMeta(BaseModel):
    generated_at: datetime
    date_from: date | None = None
    date_to: date | None = None


class BorrowedBookReportItem(BaseModel):
    loan_id: UUID
    member_id: UUID
    membership_id: str
    member_name: str
    book_id: UUID
    book_title: str
    isbn: str
    borrowed_at: datetime
    due_at: datetime
    returned_at: datetime | None
    status: LoanStatus


class BorrowedBooksReport(BaseModel):
    meta: ReportMeta
    total_loans: int
    active_loans: int
    returned_loans: int
    items: list[BorrowedBookReportItem]


class OverdueItemReportItem(BaseModel):
    loan_id: UUID
    member_id: UUID
    membership_id: str
    member_name: str
    book_id: UUID
    book_title: str
    due_at: datetime
    overdue_days: int


class OverdueItemsReport(BaseModel):
    generated_at: datetime
    total_overdue: int
    items: list[OverdueItemReportItem]


class MemberActivityReportItem(BaseModel):
    member_id: UUID
    membership_id: str
    member_name: str
    is_active: bool
    total_loans: int
    active_loans: int
    returned_loans: int
    total_reservations: int
    outstanding_fines: Decimal


class MemberActivitiesReport(BaseModel):
    meta: ReportMeta
    total_members: int
    active_members: int
    members_with_active_loans: int
    items: list[MemberActivityReportItem]


class FineReportItem(BaseModel):
    fine_id: UUID
    loan_id: UUID
    member_id: UUID
    membership_id: str
    member_name: str
    amount: Decimal
    amount_paid: Decimal
    outstanding_amount: Decimal
    status: FineStatus
    overdue_days: int
    created_at: datetime
    paid_at: datetime | None


class FinesReport(BaseModel):
    meta: ReportMeta
    total_fines: int
    outstanding_fines: int
    paid_fines: int
    total_assessed: Decimal
    total_paid: Decimal
    total_outstanding: Decimal
    items: list[FineReportItem]


class InventoryReportItem(BaseModel):
    book_id: UUID
    title: str
    author: str
    isbn: str
    category: str
    total_copies: int
    available_copies: int
    borrowed_copies: int
    is_available: bool
    is_low_stock: bool


class InventoryStatusReport(BaseModel):
    generated_at: datetime
    low_stock_threshold: int
    total_titles: int
    total_copies: int
    available_copies: int
    borrowed_copies: int
    unavailable_titles: int
    low_stock_titles: int
    items: list[InventoryReportItem]
