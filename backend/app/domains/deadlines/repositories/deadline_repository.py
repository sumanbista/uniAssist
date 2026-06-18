"""Persistence access for the Deadline domain."""

from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.deadlines.models import Deadline


class DeadlineRepository:
    """Repository for tenant-scoped deadline persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_deadline(self, deadline: Deadline) -> Deadline:
        """Persist a new deadline record."""

        self.session.add(deadline)
        await self.session.commit()
        await self.session.refresh(deadline)
        return deadline

    async def get_deadline_by_id(
        self,
        university_id: UUID,
        deadline_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> Deadline | None:
        """Return one tenant-scoped deadline matching explicit visibility filters."""

        rows = await self.session.execute(
            self._visible_query(
                university_id=university_id,
                visible_statuses=visible_statuses,
                visible_verification_statuses=visible_verification_statuses,
            ).where(Deadline.id == deadline_id)
        )
        return rows.scalar_one_or_none()

    async def list_deadlines(
        self,
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
        offset: int,
        term: str | None = None,
        academic_year: str | None = None,
        deadline_type: str | None = None,
    ) -> tuple[list[Deadline], int]:
        """List tenant-scoped deadlines with optional exact filters."""

        query = self._visible_query(
            university_id,
            visible_statuses,
            visible_verification_statuses,
        )
        count_query = self._visible_count_query(
            university_id,
            visible_statuses,
            visible_verification_statuses,
        )
        if term is not None:
            query = query.where(Deadline.term == term)
            count_query = count_query.where(Deadline.term == term)
        if academic_year is not None:
            query = query.where(Deadline.academic_year == academic_year)
            count_query = count_query.where(Deadline.academic_year == academic_year)
        if deadline_type is not None:
            query = query.where(Deadline.deadline_type == deadline_type)
            count_query = count_query.where(Deadline.deadline_type == deadline_type)

        rows = await self.session.execute(
            query.order_by(Deadline.due_date.asc(), Deadline.title.asc())
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def search_deadlines(
        self,
        university_id: UUID,
        query_text: str,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
        offset: int,
        deadline_type: str | None = None,
    ) -> tuple[list[Deadline], int]:
        """Search tenant-scoped deadlines by text and optional type."""

        pattern = f"%{query_text}%"
        query = self._visible_query(
            university_id,
            visible_statuses,
            visible_verification_statuses,
        ).where(
            or_(
                Deadline.title.ilike(pattern),
                Deadline.description.ilike(pattern),
                Deadline.term.ilike(pattern),
                Deadline.academic_year.ilike(pattern),
            )
        )
        count_query = self._visible_count_query(
            university_id,
            visible_statuses,
            visible_verification_statuses,
        ).where(
            or_(
                Deadline.title.ilike(pattern),
                Deadline.description.ilike(pattern),
                Deadline.term.ilike(pattern),
                Deadline.academic_year.ilike(pattern),
            )
        )
        if deadline_type is not None:
            query = query.where(Deadline.deadline_type == deadline_type)
            count_query = count_query.where(Deadline.deadline_type == deadline_type)

        rows = await self.session.execute(
            query.order_by(Deadline.due_date.asc(), Deadline.title.asc())
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def upcoming_deadlines(
        self,
        university_id: UUID,
        as_of: date,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
    ) -> list[Deadline]:
        """Return upcoming tenant-scoped deadlines."""

        rows = await self.session.execute(
            self._visible_query(
                university_id,
                visible_statuses,
                visible_verification_statuses,
            )
            .where(Deadline.due_date >= as_of)
            .order_by(Deadline.due_date.asc(), Deadline.title.asc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    @staticmethod
    def _visible_query(
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> Select[tuple[Deadline]]:
        """Build a tenant-scoped visible deadline query."""

        return select(Deadline).where(
            Deadline.university_id == university_id,
            Deadline.is_active.is_(True),
            Deadline.status.in_(visible_statuses),
            Deadline.verification_status.in_(visible_verification_statuses),
        )

    @staticmethod
    def _visible_count_query(
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> Select[tuple[int]]:
        """Build a tenant-scoped visible deadline count query."""

        return select(func.count()).select_from(Deadline).where(
            Deadline.university_id == university_id,
            Deadline.is_active.is_(True),
            Deadline.status.in_(visible_statuses),
            Deadline.verification_status.in_(visible_verification_statuses),
        )
