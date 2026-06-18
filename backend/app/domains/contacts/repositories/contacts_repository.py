"""Persistence access for the Contacts domain."""

from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.contacts.models import Contact


class ContactsRepository:
    """Repository for tenant-scoped contact persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_contact(self, contact: Contact) -> Contact:
        """Persist a new contact."""

        self.session.add(contact)
        await self.session.commit()
        await self.session.refresh(contact)
        return contact

    async def get_contact_by_id(
        self,
        university_id: UUID,
        contact_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> Contact | None:
        """Return one tenant-scoped contact matching explicit visibility filters."""

        rows = await self.session.execute(
            self._visible_query(
                university_id=university_id,
                visible_statuses=visible_statuses,
                visible_verification_statuses=visible_verification_statuses,
            ).where(Contact.id == contact_id)
        )
        return rows.scalar_one_or_none()

    async def list_contacts(
        self,
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
        offset: int,
        department: str | None = None,
        contact_type: str | None = None,
    ) -> tuple[list[Contact], int]:
        """List tenant-scoped contacts with optional exact filters."""

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
        if department is not None:
            query = query.where(Contact.department.ilike(department))
            count_query = count_query.where(Contact.department.ilike(department))
        if contact_type is not None:
            query = query.where(Contact.contact_type == contact_type)
            count_query = count_query.where(Contact.contact_type == contact_type)

        rows = await self.session.execute(
            query.order_by(Contact.name.asc(), Contact.id.asc()).limit(limit).offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def search_contacts(
        self,
        university_id: UUID,
        query_text: str,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Contact], int]:
        """Search tenant-scoped contacts by name, title, department, or email."""

        pattern = f"%{query_text}%"
        query = self._visible_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        ).where(
            or_(
                Contact.name.ilike(pattern),
                Contact.title.ilike(pattern),
                Contact.department.ilike(pattern),
                Contact.email.ilike(pattern),
            )
        )
        count_query = self._visible_count_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        ).where(
            or_(
                Contact.name.ilike(pattern),
                Contact.title.ilike(pattern),
                Contact.department.ilike(pattern),
                Contact.email.ilike(pattern),
            )
        )
        rows = await self.session.execute(
            query.order_by(Contact.name.asc(), Contact.id.asc()).limit(limit).offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def search_by_department(
        self,
        university_id: UUID,
        department: str,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Contact], int]:
        """Search tenant-scoped contacts by department."""

        pattern = f"%{department}%"
        query = self._visible_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        ).where(Contact.department.ilike(pattern))
        count_query = self._visible_count_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        ).where(Contact.department.ilike(pattern))
        rows = await self.session.execute(
            query.order_by(Contact.name.asc(), Contact.id.asc()).limit(limit).offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    async def search_by_contact_type(
        self,
        university_id: UUID,
        contact_type: str,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Contact], int]:
        """Search tenant-scoped contacts by contact type."""

        query = self._visible_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        ).where(Contact.contact_type == contact_type)
        count_query = self._visible_count_query(
            university_id=university_id,
            visible_statuses=visible_statuses,
            visible_verification_statuses=visible_verification_statuses,
        ).where(Contact.contact_type == contact_type)
        rows = await self.session.execute(
            query.order_by(Contact.name.asc(), Contact.id.asc()).limit(limit).offset(offset)
        )
        total = await self.session.scalar(count_query)
        return list(rows.scalars().all()), int(total or 0)

    @staticmethod
    def _visible_query(
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> Select[tuple[Contact]]:
        """Build a tenant-scoped visible contact query."""

        return select(Contact).where(
            Contact.university_id == university_id,
            Contact.is_active.is_(True),
            Contact.status.in_(visible_statuses),
            Contact.verification_status.in_(visible_verification_statuses),
        )

    @staticmethod
    def _visible_count_query(
        university_id: UUID,
        visible_statuses: tuple[str, ...],
        visible_verification_statuses: tuple[str, ...],
    ) -> Select[tuple[int]]:
        """Build a tenant-scoped visible contact count query."""

        return select(func.count()).select_from(Contact).where(
            Contact.university_id == university_id,
            Contact.is_active.is_(True),
            Contact.status.in_(visible_statuses),
            Contact.verification_status.in_(visible_verification_statuses),
        )

