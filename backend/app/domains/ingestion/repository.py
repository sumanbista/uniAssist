"""Persistence operations for Caldwell ingestion."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.forms.models import Form
from app.domains.forms.schemas import FormCreate
from app.domains.ingestion.models import AcademicCalendarEntry, RawPage
from app.domains.ingestion.schemas import (
    ExtractedCalendarEntry,
    ExtractedForm,
    RawSourceArtifact,
)


class IngestionRepository:
    """Repository for retry-safe ingestion writes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def capture_raw_page(self, artifact: RawSourceArtifact) -> RawPage:
        """Persist validated raw HTML once for replay-safe ingestion."""

        existing_page = await self._find_raw_page(
            source_id=artifact.source.source_id,
            content_hash=artifact.content_hash,
        )
        if existing_page is not None:
            return existing_page

        page = RawPage(
            source_id=artifact.source.source_id,
            source_url=str(artifact.source_url),
            html_content=artifact.html_content,
            content_hash=artifact.content_hash,
            captured_at=artifact.captured_at,
            metadata_=artifact.metadata,
        )
        self.session.add(page)
        await self.session.commit()
        await self.session.refresh(page)
        return page

    async def upsert_form(
        self,
        university_id: UUID,
        source_id: str,
        extracted_form: ExtractedForm,
    ) -> tuple[Form, bool]:
        """Create a pending-review form unless the source hash already exists."""

        existing_form = await self._find_form_by_source_hash(
            university_id=university_id,
            source_hash=extracted_form.source_hash,
        )
        if existing_form is not None:
            return existing_form, False

        form_data = FormCreate(
            university_id=university_id,
            title=extracted_form.title,
            description=extracted_form.description,
            category="registrar",
            source_url=extracted_form.source_url,
            verification_status="pending_review",
            verification_score=0.5,
            status="pending_review",
            metadata={
                "source_id": source_id,
                "source_hash": extracted_form.source_hash,
                "extracted_at": extracted_form.extracted_at.isoformat(),
                "ingestion_status": "pending_review",
            },
        )
        form = Form(
            university_id=form_data.university_id,
            title=form_data.title,
            description=form_data.description,
            category=form_data.category,
            source_url=str(form_data.source_url) if form_data.source_url else None,
            storage_path=form_data.storage_path,
            verification_status=form_data.verification_status,
            verification_score=form_data.verification_score,
            last_verified_at=form_data.last_verified_at,
            review_notes=form_data.review_notes,
            expires_at=form_data.expires_at,
            next_review_at=form_data.next_review_at,
            status=form_data.status,
            metadata_=form_data.metadata,
        )
        self.session.add(form)
        await self.session.commit()
        await self.session.refresh(form)
        return form, True

    async def upsert_calendar_entry(
        self,
        university_id: UUID,
        source_id: str,
        extracted_entry: ExtractedCalendarEntry,
    ) -> tuple[AcademicCalendarEntry, bool]:
        """Create a pending-review calendar entry unless the hash already exists."""

        existing_entry = await self._find_calendar_by_source_hash(
            university_id=university_id,
            source_hash=extracted_entry.source_hash,
        )
        if existing_entry is not None:
            return existing_entry, False

        entry = AcademicCalendarEntry(
            university_id=university_id,
            title=extracted_entry.title,
            description=extracted_entry.description,
            source_url=str(extracted_entry.source_url),
            source_hash=extracted_entry.source_hash,
            status="pending_review",
            verification_status="pending_review",
            extracted_at=extracted_entry.extracted_at,
            metadata_={
                "source_id": source_id,
                "source_hash": extracted_entry.source_hash,
                "ingestion_status": "pending_review",
            },
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry, True

    async def _find_form_by_source_hash(
        self,
        university_id: UUID,
        source_hash: str,
    ) -> Form | None:
        """Find an existing form by ingestion source hash."""

        rows = await self.session.execute(
            select(Form).where(
                Form.university_id == university_id,
                Form.metadata_["source_hash"].astext == source_hash,
            )
        )
        return rows.scalar_one_or_none()

    async def _find_calendar_by_source_hash(
        self,
        university_id: UUID,
        source_hash: str,
    ) -> AcademicCalendarEntry | None:
        """Find an existing calendar entry by ingestion source hash."""

        rows = await self.session.execute(
            select(AcademicCalendarEntry).where(
                AcademicCalendarEntry.university_id == university_id,
                AcademicCalendarEntry.source_hash == source_hash,
            )
        )
        return rows.scalar_one_or_none()

    async def _find_raw_page(
        self,
        source_id: str,
        content_hash: str,
    ) -> RawPage | None:
        """Find an already captured raw page by source and hash."""

        rows = await self.session.execute(
            select(RawPage).where(
                RawPage.source_id == source_id,
                RawPage.content_hash == content_hash,
            )
        )
        return rows.scalar_one_or_none()
