from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Book(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("total_copies >= 0", name="total_copies_non_negative"),
        CheckConstraint("available_copies >= 0", name="available_copies_non_negative"),
        CheckConstraint(
            "available_copies <= total_copies",
            name="available_copies_not_above_total",
        ),
    )

    title: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    author: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    isbn: Mapped[str] = mapped_column(String(17), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False)
    available_copies: Mapped[int] = mapped_column(Integer, nullable=False)

    @property
    def borrowed_copies(self) -> int:
        return self.total_copies - self.available_copies

    @property
    def is_available(self) -> bool:
        return self.available_copies > 0
