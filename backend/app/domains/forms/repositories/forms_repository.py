"""Persistence access for the Forms domain."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, bindparam, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domains.forms.models import Form
from app.domains.forms.schemas import FormCreate
from app.shared.database.vector import Vector


class FormsRepository:
    """Repository for tenant-scoped form persistence operations."""

    EXCLUDED_RETRIEVAL_STATUSES = ("archived", "deprecated", "rejected")
    PUBLIC_RETRIEVAL_STATUSES = ("verified", "published")

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
            .where(Form.status.in_(self.PUBLIC_RETRIEVAL_STATUSES))
            .where(Form.verification_status.in_(self.PUBLIC_RETRIEVAL_STATUSES))
            .order_by(rank.desc(), Form.title.asc(), Form.id.asc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    async def semantic_search_forms(
        self,
        embedding: list[float],
        university_id: UUID,
        limit: int,
    ) -> list[tuple[Form, float]]:
        """Search tenant-scoped forms by pgvector cosine similarity."""

        bounded_limit = min(max(limit, 1), 100)
        embedding_literal = _embedding_to_pgvector_literal(embedding)
        query_embedding = cast(
            bindparam("query_embedding"),
            Vector(settings.EMBEDDING_DIMENSIONS),
        )
        similarity_score = (1 - Form.embedding.op("<=>")(query_embedding)).label(
            "similarity_score"
        )
        rows = await self.session.execute(
            self._tenant_scoped_query(university_id)
            .add_columns(similarity_score)
            .where(Form.embedding.is_not(None))
            .where(Form.status.in_(self.PUBLIC_RETRIEVAL_STATUSES))
            .where(Form.verification_status.in_(self.PUBLIC_RETRIEVAL_STATUSES))
            .order_by(
                Form.embedding.op("<=>")(query_embedding).asc(),
                Form.title.asc(),
                Form.id.asc(),
            )
            .limit(bounded_limit),
            {"query_embedding": embedding_literal},
        )
        return [(row[0], float(row[1])) for row in rows.all()]

    async def update_form_embedding(
        self,
        university_id: UUID,
        form_id: UUID,
        embedding: list[float],
        embedding_updated_at: datetime,
    ) -> Form | None:
        """Persist a tenant-scoped form embedding."""

        embedding_literal = _embedding_to_pgvector_literal(embedding)
        result = await self.session.execute(
            text(
                """
                UPDATE forms
                SET embedding = CAST(:embedding AS vector),
                    embedding_updated_at = :embedding_updated_at
                WHERE university_id = :university_id
                  AND id = :form_id
                RETURNING id
                """
            ),
            {
                "embedding": embedding_literal,
                "embedding_updated_at": embedding_updated_at,
                "university_id": university_id,
                "form_id": form_id,
            },
        )
        if result.scalar_one_or_none() is None:
            await self.session.rollback()
            return None
        await self.session.commit()
        return await self.get_form_by_id(
            university_id=university_id,
            form_id=form_id,
            include_inactive=True,
        )

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


def _embedding_to_pgvector_literal(embedding: list[float]) -> str:
    """Validate and serialize an embedding for parameterized pgvector queries."""

    if len(embedding) != settings.EMBEDDING_DIMENSIONS:
        raise ValueError("Embedding dimension mismatch")
    return "[" + ",".join(_format_embedding_value(value) for value in embedding) + "]"


def _format_embedding_value(value: float) -> str:
    """Return a safe finite float literal for pgvector."""

    numeric_value = float(value)
    if numeric_value != numeric_value or numeric_value in (float("inf"), float("-inf")):
        raise ValueError("Embedding values must be finite")
    return f"{numeric_value:.8f}"
