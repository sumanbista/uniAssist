"""Persistence access for the Calendar domain."""

from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.calendar.models import AcademicCalendarEntry


class CalendarRepository:
    """Repository for tenant-scoped academic calendar persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_entry(self, entry: AcademicCalendarEntry) -> AcademicCalendarEntry:
        """Persist a new calendar entry."""

        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def get_entry_by_id(
        self,
        university_id: UUID,
        entry_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> AcademicCalendarEntry | None:
        """Return one tenant-scoped entry matching explicit visibility filters."""

        rows = await self.session.execute(
            self._visible_query(
                university_id=university_id,
                visible_statuses=visible_statuses,
                visible_verification_statuses=visible_verification_statuses,
            ).where(AcademicCalendarEntry.id == entry_id)
        )
        return rows.scalar_one_or_none()

    async def list_entries(
        self,
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
        offset: int,
        term: str | None = None,
        academic_year: str | None = None,
        entry_type: str | None = None,
    ) -> tuple[list[AcademicCalendarEntry], int]:
        """List tenant-scoped entries with optional exact filters."""

        query = self._visible_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        )
        count_query = self._visible_count_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        )
        if term is not None:
            query = query.where(AcademicCalendarEntry.term == term)
            count_query = count_query.where(AcademicCalendarEntry.term == term)
        if academic_year is not None:
            query = query.where(AcademicCalendarEntry.academic_year == academic_year)
            count_query = count_query.where(AcademicCalendarEntry.academic_year == academic_year)
        if entry_type is not None:
            query = query.where(AcademicCalendarEntry.entry_type == entry_type)
            count_query = count_query.where(AcademicCalendarEntry.entry_type == entry_type)

        rows = await self.session.execute(
            query.order_by(
                AcademicCalendarEntry.start_date.asc().nullslast(),
                AcademicCalendarEntry.title.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def search_entries(
        self,
        university_id: UUID,
        query_text: str,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
        offset: int,
        entry_type: str | None = None,
    ) -> tuple[list[AcademicCalendarEntry], int]:
        """Search tenant-scoped entries by text and optional type."""

        pattern = f"%{query_text}%"
        query = self._visible_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        ).where(
            or_(
                AcademicCalendarEntry.title.ilike(pattern),
                AcademicCalendarEntry.description.ilike(pattern),
                AcademicCalendarEntry.term.ilike(pattern),
                AcademicCalendarEntry.academic_year.ilike(pattern),
            )
        )
        count_query = self._visible_count_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        ).where(
            or_(
                AcademicCalendarEntry.title.ilike(pattern),
                AcademicCalendarEntry.description.ilike(pattern),
                AcademicCalendarEntry.term.ilike(pattern),
                AcademicCalendarEntry.academic_year.ilike(pattern),
            )
        )
        if entry_type is not None:
            query = query.where(AcademicCalendarEntry.entry_type == entry_type)
            count_query = count_query.where(AcademicCalendarEntry.entry_type == entry_type)

        rows = await self.session.execute(
            query.order_by(
                AcademicCalendarEntry.start_date.asc().nullslast(),
                AcademicCalendarEntry.title.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def upcoming_entries(
        self,
        university_id: UUID,
        as_of: date,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
    ) -> list[AcademicCalendarEntry]:
        """Return upcoming tenant-scoped entries."""

        rows = await self.session.execute(
            self._visible_query(
                university_id=university_id,
                visible_statuses=visible_statuses,
                visible_verification_statuses=visible_verification_statuses,
            )
            .where(AcademicCalendarEntry.start_date >= as_of)
            .order_by(AcademicCalendarEntry.start_date.asc(), AcademicCalendarEntry.title.asc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    @staticmethod
    def _visible_query(
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> Select[tuple[AcademicCalendarEntry]]:
        """Build a tenant-scoped visible entry query."""

        return select(AcademicCalendarEntry).where(
            AcademicCalendarEntry.university_id == university_id,
            AcademicCalendarEntry.is_active.is_(True),
            AcademicCalendarEntry.status.in_(visible_statuses),
            AcademicCalendarEntry.verification_status.in_(visible_verification_statuses),
        )

    @staticmethod
    def _visible_count_query(
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> Select[tuple[int]]:
        """Build a tenant-scoped visible count query."""

        return select(func.count()).select_from(AcademicCalendarEntry).where(
            AcademicCalendarEntry.university_id == university_id,
            AcademicCalendarEntry.is_active.is_(True),
            AcademicCalendarEntry.status.in_(visible_statuses),
            AcademicCalendarEntry.verification_status.in_(visible_verification_statuses),
        )
