"""Persistence access for the Forms domain."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.forms.models import Form
from app.domains.forms.schemas import FormCreate


class FormsRepository:
    """Repository for tenant-scoped form persistence operations."""

    EXCLUDED_RETRIEVAL_STATUSES = ("archived", "deprecated", "rejected")

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_form(self, form_data: FormCreate) -> Form:
        """Persist a new form record."""

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
        return form

    async def get_form_by_id(
        self,
        university_id: UUID,
        form_id: UUID,
        include_inactive: bool = False,
    ) -> Form | None:
        """Return a form by tenant and ID."""

        query = select(Form).where(
            Form.university_id == university_id,
            Form.id == form_id,
        )
        if not include_inactive:
            query = query.where(Form.is_active.is_(True))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_forms(
        self,
        university_id: UUID,
        limit: int,
        offset: int,
        category: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Form], int]:
        """List tenant-scoped forms with optional retrieval filters."""

        query = self._tenant_scoped_query(university_id)
        count_query = select(func.count()).select_from(Form).where(
            Form.university_id == university_id,
            Form.is_active.is_(True),
        )
        if category is not None:
            query = query.where(Form.category == category)
            count_query = count_query.where(Form.category == category)
        if status is not None:
            query = query.where(Form.status == status)
            count_query = count_query.where(Form.status == status)

        rows = await self.session.execute(
            query.order_by(Form.title.asc()).limit(limit).offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def search_forms_by_title(
        self,
        university_id: UUID,
        title_query: str,
        limit: int,
        offset: int,
    ) -> tuple[list[Form], int]:
        """Search tenant-scoped forms by title."""

        normalized_query = f"%{title_query.strip()}%"
        query = self._tenant_scoped_query(university_id).where(
            Form.title.ilike(normalized_query)
        )
        count_query = (
            select(func.count())
            .select_from(Form)
            .where(
                Form.university_id == university_id,
                Form.is_active.is_(True),
                Form.title.ilike(normalized_query),
            )
        )
        rows = await self.session.execute(
            query.order_by(Form.title.asc()).limit(limit).offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def search_forms(
        self,
        query: str,
        university_id: UUID,
        limit: int,
    ) -> list[Form]:
        """Search tenant-scoped forms using PostgreSQL full-text search."""

        normalized_query = query.strip()
        if not normalized_query:
            return []

        search_query = func.plainto_tsquery("english", normalized_query)
        rank = func.ts_rank_cd(Form.searchable_vector, search_query)
        rows = await self.session.execute(
            self._tenant_scoped_query(university_id)
            .where(Form.searchable_vector.op("@@")(search_query))
            .where(Form.status.notin_(self.EXCLUDED_RETRIEVAL_STATUSES))
            .where(Form.verification_status.notin_(("rejected", "archived")))
            .order_by(rank.desc(), Form.title.asc(), Form.id.asc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    async def save_form(self, form: Form, commit: bool = True) -> Form:
        """Persist pending form changes."""

        self.session.add(form)
        if commit:
            await self.session.commit()
            await self.session.refresh(form)
        return form

    async def commit(self) -> None:
        """Commit pending repository changes."""

        await self.session.commit()

    async def list_stale_candidates(
        self,
        university_id: UUID,
        as_of: datetime,
        limit: int,
    ) -> list[Form]:
        """Return forms due for revalidation."""

        rows = await self.session.execute(
            self._tenant_scoped_query(university_id)
            .where(Form.status.notin_(self.EXCLUDED_RETRIEVAL_STATUSES))
            .where(
                or_(
                    (Form.expires_at.is_not(None)) & (Form.expires_at <= as_of),
                    (Form.next_review_at.is_not(None))
                    & (Form.next_review_at <= as_of),
                )
            )
            .order_by(Form.next_review_at.asc().nullslast(), Form.expires_at.asc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    @staticmethod
    def _tenant_scoped_query(university_id: UUID) -> Select[tuple[Form]]:
        """Build the base tenant-scoped form query."""

        return select(Form).where(
            Form.university_id == university_id,
            Form.is_active.is_(True),
        )
