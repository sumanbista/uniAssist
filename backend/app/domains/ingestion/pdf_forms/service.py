"""Service layer for secure admin PDF form ingestion."""

import hashlib
import re
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.domains.forms.models import Form
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.schemas import FormCreate
from app.domains.forms.services import FormsService
from app.domains.ingestion.models import RawPage
from app.domains.ingestion.pdf_forms.pdf_parser import (
    PdfExtractionError,
    extract_text_from_pdf,
)
from app.domains.ingestion.pdf_forms.schemas import (
    PdfExtractionResult,
    PdfFormUploadInput,
    PdfFormUploadResponse,
)
from app.shared.events import EventBus, EventContext, EventStore
from app.shared.storage import LocalStorageProvider, StorageProvider

logger = get_logger(__name__)

ALLOWED_PDF_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/x-pdf",
    }
)
PDF_MAGIC = b"%PDF-"
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class PdfFormIngestionError(ValueError):
    """Raised when a PDF form upload fails validation or parsing."""


class PdfTextExtractor(Protocol):
    """Protocol for injectable PDF text extractors."""

    async def __call__(self, pdf_path) -> PdfExtractionResult:
        """Extract text from a local PDF path."""


class PdfFormIngestionService:
    """Coordinate secure file storage, extraction, Forms creation, and events."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage_provider: StorageProvider | None = None,
        event_bus: EventBus | None = None,
        text_extractor: PdfTextExtractor = extract_text_from_pdf,
    ) -> None:
        self.session = session
        self.forms_service = FormsService(FormsRepository(session))
        self.storage_provider = storage_provider or LocalStorageProvider()
        self.event_bus = event_bus or EventBus(EventStore(session))
        self.text_extractor = text_extractor

    async def ingest_pdf_form(
        self,
        *,
        university_id: UUID,
        upload: UploadFile,
        metadata: PdfFormUploadInput,
        event_context: EventContext,
    ) -> PdfFormUploadResponse:
        """Validate, store, extract, and create a pending-review form."""

        original_filename = sanitize_original_filename(upload.filename)
        content = await _read_and_validate_pdf(upload)
        content_hash = hashlib.sha256(content).hexdigest()
        upload_id = uuid4()
        storage_path = await self.storage_provider.save_file(
            university_id=university_id,
            relative_path=f"pdf_forms/{upload_id}.pdf",
            content=content,
        )
        file_path = self.storage_provider.get_file_path(storage_path)
        try:
            extraction = await self.text_extractor(file_path)
        except PdfExtractionError as exc:
            raise PdfFormIngestionError(str(exc)) from exc

        extracted_text_preview = extraction.preview(settings.PDF_FORM_TEXT_PREVIEW_CHARS)
        form = await self._create_form(
            university_id=university_id,
            metadata=metadata,
            storage_path=storage_path,
            original_filename=original_filename,
            file_size=len(content),
            content_hash=content_hash,
            extraction=extraction,
            extracted_text_preview=extracted_text_preview,
        )
        await self._capture_raw_pdf_extraction(
            form=form,
            source_url=str(metadata.source_url) if metadata.source_url else storage_path,
            content_hash=content_hash,
            extraction=extraction,
        )
        await self._emit_upload_events(
            form=form,
            storage_path=storage_path,
            event_context=event_context,
        )
        logger.info(
            "pdf_form_ingested form_id=%s university_id=%s actor_id=%s storage_path=%s page_count=%s",
            form.id,
            university_id,
            event_context.actor_id,
            storage_path,
            extraction.page_count,
        )
        return PdfFormUploadResponse(
            form_id=form.id,
            title=form.title,
            status=form.status,
            verification_status=form.verification_status,
            storage_path=storage_path,
            extracted_text_preview=extracted_text_preview,
            page_count=extraction.page_count,
        )

    async def _create_form(
        self,
        *,
        university_id: UUID,
        metadata: PdfFormUploadInput,
        storage_path: str,
        original_filename: str,
        file_size: int,
        content_hash: str,
        extraction: PdfExtractionResult,
        extracted_text_preview: str,
    ) -> Form:
        """Create the canonical governed form record."""

        return await self.forms_service.create_form(
            FormCreate(
                university_id=university_id,
                title=metadata.title,
                description=metadata.description,
                category=metadata.category,
                source_url=metadata.source_url,
                storage_path=storage_path,
                verification_status="pending_review",
                verification_score=0.5,
                status="pending_review",
                metadata={
                    "department": metadata.department,
                    "original_filename": original_filename,
                    "file_size": file_size,
                    "content_hash": content_hash,
                    "page_count": extraction.page_count,
                    "extracted_text_preview": extracted_text_preview,
                    "upload_method": "admin_pdf",
                    "embedding_status": "pending",
                    "ingestion_status": "pending_review",
                    "uploaded_at": datetime.now(UTC).isoformat(),
                },
            )
        )

    async def _capture_raw_pdf_extraction(
        self,
        *,
        form: Form,
        source_url: str,
        content_hash: str,
        extraction: PdfExtractionResult,
    ) -> None:
        """Store raw extraction metadata in the existing raw_pages table."""

        text_by_page = "\n\n".join(
            f"Page {page.page_number}\n{page.text}"
            for page in extraction.pages
            if page.text
        )
        raw_page = RawPage(
            source_id="admin_pdf_forms",
            source_url=source_url,
            html_content=text_by_page or "",
            content_hash=content_hash,
            captured_at=datetime.now(UTC),
            metadata_={
                "form_id": str(form.id),
                "storage_path": form.storage_path,
                "page_count": extraction.page_count,
                "content_type": "application/pdf",
                "capture_type": "pdf_text_extraction",
                "todo": "Replace raw_pages with a document/raw_pages schema when the document pipeline is implemented.",
            },
        )
        self.session.add(raw_page)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()

    async def _emit_upload_events(
        self,
        *,
        form: Form,
        storage_path: str,
        event_context: EventContext,
    ) -> None:
        """Emit audit-ready upload and entity creation events."""

        payload = {
            "actor_id": str(event_context.actor_id) if event_context.actor_id else None,
            "university_id": str(form.university_id),
            "correlation_id": (
                str(event_context.correlation_id)
                if event_context.correlation_id
                else None
            ),
            "storage_path": storage_path,
            "form_id": str(form.id),
            "status": form.status,
            "verification_status": form.verification_status,
        }
        for event_type in ("forms.pdf_uploaded", "entity.created"):
            await self.event_bus.emit_event(
                event_type=event_type,
                aggregate_type="form",
                aggregate_id=form.id,
                university_id=form.university_id,
                actor_id=event_context.actor_id,
                correlation_id=event_context.correlation_id,
                payload={**payload, "entity_type": "form"},
                metadata={"source": "pdf_form_ingestion_service"},
            )


async def _read_and_validate_pdf(upload: UploadFile) -> bytes:
    """Read an upload with bounded memory and validate it as a PDF."""

    content_type = (upload.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if content_type not in ALLOWED_PDF_CONTENT_TYPES:
        raise PdfFormIngestionError("Only PDF uploads are supported")
    if not _has_pdf_extension(upload.filename):
        raise PdfFormIngestionError("Uploaded file must use a .pdf extension")

    max_size = settings.PDF_FORM_MAX_FILE_SIZE_BYTES
    content = await upload.read(max_size + 1)
    if not content:
        raise PdfFormIngestionError("Uploaded PDF cannot be empty")
    if len(content) > max_size:
        raise PdfFormIngestionError("Uploaded PDF exceeds the maximum allowed size")
    if not content.startswith(PDF_MAGIC):
        raise PdfFormIngestionError("Uploaded file is not a valid PDF")
    return content


def sanitize_original_filename(filename: str | None) -> str:
    """Return safe metadata-only original filename without trusting paths."""

    basename = PurePath((filename or "uploaded.pdf").replace("\\", "/")).name
    sanitized = _UNSAFE_FILENAME_CHARS.sub("_", basename).strip("._")
    if not sanitized:
        sanitized = "uploaded.pdf"
    if not sanitized.lower().endswith(".pdf"):
        sanitized = f"{sanitized}.pdf"
    return sanitized[:255]


def _has_pdf_extension(filename: str | None) -> bool:
    """Return whether the client-provided basename has a PDF extension."""

    if not filename:
        return False
    basename = PurePath(filename.replace("\\", "/")).name
    return basename.lower().endswith(".pdf")
