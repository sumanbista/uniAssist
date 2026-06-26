"""Service layer for the Forms domain."""

from uuid import UUID

from app.domains.auth.models.roles import UserRole
from app.domains.forms.models import Form
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.schemas import FormCreate

PUBLIC_VISIBLE_STATUSES = ("verified", "published")
ADMIN_VISIBLE_STATUSES = ("pending_review", "stale", "verified", "published")
ADMIN_ROLES = {UserRole.ADMIN, UserRole.UNIVERSITY_ADMIN, UserRole.SUPER_ADMIN}


class FormsService:
    """Coordinate Forms domain repository operations."""

    def __init__(self, repository: FormsRepository) -> None:
        self.repository = repository

    async def create_form(self, form_data: FormCreate) -> Form:
        """Create a form after placeholder validation and governance hooks."""

        await self._run_validation_hooks(form_data)
        await self._run_governance_hooks(form_data)
        return await self.repository.create_form(form_data)

    async def retrieve_form(self, university_id: UUID, form_id: UUID) -> Form | None:
        """Retrieve a tenant-scoped form."""

        return await self.repository.get_form_by_id(university_id, form_id)

    async def list_forms(
        self,
        university_id: UUID,
        role: UserRole | None,
        limit: int,
        offset: int,
        query: str | None = None,
        category: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Form], int]:
        """List or search tenant-scoped forms."""

        statuses = self._visible_statuses(role)
        if query and query.strip():
            return await self.repository.search_forms_by_title(
                university_id=university_id,
                title_query=query,
                limit=limit,
                offset=offset,
                visible_statuses=statuses,
                visible_verification_statuses=statuses,
            )
        return await self.repository.list_forms(
            university_id=university_id,
            limit=limit,
            offset=offset,
            category=category,
            status=status,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
        )

    async def _run_validation_hooks(self, form_data: FormCreate) -> None:
        """Placeholder for future Forms domain validation hooks."""

        return None

    async def _run_governance_hooks(self, form_data: FormCreate) -> None:
        """Placeholder for future governance integration hooks."""

        return None

    @staticmethod
    def _visible_statuses(role: UserRole | None) -> tuple[str, ...]:
        """Return lifecycle states visible to this role."""

        if role in ADMIN_ROLES:
            return ADMIN_VISIBLE_STATUSES
        return PUBLIC_VISIBLE_STATUSES
