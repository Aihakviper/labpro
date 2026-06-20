import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ISBN_PATTERN = re.compile(r"^(?:\d{9}[\dX]|\d{13})$")


def normalize_isbn(value: str) -> str:
    normalized = re.sub(r"[-\s]", "", value).upper()
    if not ISBN_PATTERN.fullmatch(normalized):
        raise ValueError("ISBN must be a valid 10-digit or 13-digit value")
    return normalized


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=160)
    isbn: str
    category: str = Field(min_length=1, max_length=100)
    description: str | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    total_copies: int = Field(ge=0, le=100_000)

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str) -> str:
        return normalize_isbn(value)

    @field_validator("title", "author", "category")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field cannot be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=1, max_length=160)
    isbn: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    total_copies: int | None = Field(default=None, ge=0, le=100_000)

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str | None) -> str | None:
        return normalize_isbn(value) if value is not None else None

    @field_validator("title", "author", "category")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field cannot be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def reject_empty_update(self) -> "BookUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        required_when_provided = {"title", "author", "isbn", "category", "total_copies"}
        for field in required_when_provided & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class BookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author: str
    isbn: str
    category: str
    description: str | None
    publication_year: int | None
    total_copies: int
    available_copies: int
    borrowed_copies: int
    is_available: bool
    created_at: datetime
    updated_at: datetime
