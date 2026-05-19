"""Service layer for the Forms domain."""

from uuid import UUID

from app.domains.forms.models import Form
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.schemas import FormCreate


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
        limit: int,
        offset: int,
        query: str | None = None,
        category: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Form], int]:
        """List or search tenant-scoped forms."""

        if query and query.strip():
            return await self.repository.search_forms_by_title(
                university_id=university_id,
                title_query=query,
                limit=limit,
                offset=offset,
            )
        return await self.repository.list_forms(
            university_id=university_id,
            limit=limit,
            offset=offset,
            category=category,
            status=status,
        )

    async def _run_validation_hooks(self, form_data: FormCreate) -> None:
        """Placeholder for future Forms domain validation hooks."""

        return None

    async def _run_governance_hooks(self, form_data: FormCreate) -> None:
        """Placeholder for future governance integration hooks."""

        return None
