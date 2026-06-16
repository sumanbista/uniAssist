"""PDF text extraction for admin-uploaded forms."""

import re
from pathlib import Path

import anyio

from app.core.logging import get_logger
from app.domains.ingestion.pdf_forms.schemas import (
    ExtractedPdfPage,
    PdfExtractionResult,
)

logger = get_logger(__name__)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")


class PdfExtractionError(ValueError):
    """Raised when a PDF cannot be parsed safely."""


async def extract_text_from_pdf(pdf_path: Path) -> PdfExtractionResult:
    """Extract sanitized text from each page of a local PDF file."""

    return await anyio.to_thread.run_sync(_extract_text_from_pdf_sync, pdf_path)


def sanitize_extracted_text(value: str | None) -> str:
    """Remove unsafe controls and normalize whitespace in extracted text."""

    if not value:
        return ""
    without_controls = _CONTROL_CHARS.sub(" ", value)
    return _WHITESPACE.sub(" ", without_controls).strip()


def _extract_text_from_pdf_sync(pdf_path: Path) -> PdfExtractionResult:
    """Synchronous pdfplumber parser isolated for thread execution."""

    try:
        import pdfplumber
    except ImportError as exc:
        raise PdfExtractionError("PDF parser dependency is unavailable") from exc

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = [
                ExtractedPdfPage(
                    page_number=index,
                    text=sanitize_extracted_text(page.extract_text()),
                )
                for index, page in enumerate(pdf.pages, start=1)
            ]
    except Exception as exc:
        logger.warning(
            "pdf_text_extraction_failed path=%s error=%s",
            pdf_path,
            type(exc).__name__,
        )
        raise PdfExtractionError("Unable to parse uploaded PDF") from exc

    return PdfExtractionResult(pages=pages)
