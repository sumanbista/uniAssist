"""Typed schemas for admin-uploaded PDF form ingestion."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class PdfFormUploadInput(BaseModel):
    """Validated metadata accompanying an uploaded PDF form."""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    source_url: HttpUrl | None = None

    @field_validator("title", "description", "category", "department", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        """Normalize form text inputs before persistence."""

        if value is None or not isinstance(value, str):
            return value
        normalized = " ".join(value.replace("\x00", "").split())
        return normalized or None


class ExtractedPdfPage(BaseModel):
    """Sanitized text extracted from one PDF page."""

    page_number: int = Field(ge=1)
    text: str = ""


class PdfExtractionResult(BaseModel):
    """Sanitized PDF text extraction result."""

    pages: list[ExtractedPdfPage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def page_count(self) -> int:
        """Return the parser-reported page count."""

        return len(self.pages)

    def preview(self, max_chars: int) -> str:
        """Return a bounded text preview across pages."""

        combined = " ".join(page.text for page in self.pages if page.text)
        return combined[:max_chars]


class PdfFormUploadResponse(BaseModel):
    """Response for a governed PDF form upload."""

    form_id: UUID
    title: str
    status: str
    verification_status: str
    storage_path: str
    extracted_text_preview: str
    page_count: int
