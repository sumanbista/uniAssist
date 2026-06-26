"""FastAPI routes for the Forms domain."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.domains.deadlines.services import DeadlineService
from app.domains.forms.api.dependencies import (
    AdminUser,
    get_deadline_relationship_service,
    get_forms_file_access_service,
    get_forms_retrieval_service,
    get_forms_service,
    get_relationships_service,
)
from app.domains.forms.api.governance_routes import router as governance_router
from app.domains.forms.api.serializers import (
    form_to_response,
    relationship_to_related_summary,
    retrieved_form_to_response,
)
from app.domains.forms.retrieval import FormsRetrievalService
from app.domains.forms.schemas import (
    FormCreate,
    FormListResponse,
    FormResponse,
    FormSearchResponse,
    RelatedDeadlineSummary,
    RelatedEntitySummary,
)
from app.domains.forms.services import FormsService
from app.domains.forms.services import (
    FormFileAccessDeniedError,
    FormFileNotFoundError,
    FormsFileAccessService,
)
from app.domains.relationships.services import RelationshipsService
from app.domains.auth.schemas import AuthenticatedUser
from app.shared.auth import get_current_user

router = APIRouter(prefix="/forms", tags=["forms"])
router.include_router(governance_router)


@router.post("", response_model=FormResponse, status_code=status.HTTP_201_CREATED)
async def create_form(
    form_data: FormCreate,
    current_user: AdminUser,
    service: Annotated[FormsService, Depends(get_forms_service)],
) -> FormResponse:
    """Create a canonical form."""

    form = await service.create_form(
        form_data.model_copy(update={"university_id": current_user.university_id})
    )
    return form_to_response(form)


@router.get("/search", response_model=FormSearchResponse)
async def search_forms(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[
        FormsRetrievalService,
        Depends(get_forms_retrieval_service),
    ],
    deadline_service: Annotated[
        DeadlineService | None,
        Depends(get_deadline_relationship_service),
    ],
    q: Annotated[str, Query(min_length=1, max_length=255)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    include_deadlines: Annotated[bool, Query()] = False,
) -> FormSearchResponse:
    """Search forms with PostgreSQL FTS and deterministic ranking."""

    forms = await service.retrieve_forms(
        query=q,
        university_id=current_user.university_id,
        limit=limit,
    )
    related_deadlines = await _related_deadlines_by_form(
        deadline_service=deadline_service,
        university_id=current_user.university_id,
        role=current_user.role,
        form_ids=[form.id for form in forms],
        include_deadlines=include_deadlines,
    )
    return FormSearchResponse(
        forms=[
            retrieved_form_to_response(
                form,
                related_deadlines=related_deadlines.get(form.id, []),
            )
            for form in forms
        ],
        query=q,
        limit=limit,
    )


@router.get("/search/semantic", response_model=FormSearchResponse)
async def semantic_search_forms(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[
        FormsRetrievalService,
        Depends(get_forms_retrieval_service),
    ],
    q: Annotated[str, Query(min_length=1, max_length=255)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> FormSearchResponse:
    """Search forms with local embeddings and pgvector cosine similarity."""

    forms = await service.retrieve_semantic_forms(
        query=q,
        university_id=current_user.university_id,
        limit=limit,
    )
    return FormSearchResponse(
        forms=[retrieved_form_to_response(form) for form in forms],
        query=q,
        limit=limit,
    )


@router.get("/{form_id}/file")
async def get_form_file(
    form_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[
        FormsFileAccessService,
        Depends(get_forms_file_access_service),
    ],
) -> FileResponse:
    """Open an authorized stored PDF form inline."""

    try:
        file_result = await service.get_form_file(
            form_id=form_id,
            current_user=current_user,
        )
    except FormFileAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Form file is not accessible",
        ) from exc
    except FormFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form file not found",
        ) from exc
    return FileResponse(
        path=file_result.file_path,
        media_type="application/pdf",
        filename=file_result.filename,
        content_disposition_type="inline",
    )


@router.get("/{form_id}", response_model=FormResponse)
async def get_form(
    form_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[FormsService, Depends(get_forms_service)],
    relationships_service: Annotated[
        RelationshipsService,
        Depends(get_relationships_service),
    ],
    deadline_service: Annotated[
        DeadlineService | None,
        Depends(get_deadline_relationship_service),
    ],
    include_relationships: Annotated[bool, Query()] = False,
    include_deadlines: Annotated[bool, Query()] = False,
) -> FormResponse:
    """Retrieve a tenant-scoped form by ID."""

    form = await service.retrieve_form(
        university_id=current_user.university_id,
        form_id=form_id,
    )
    if form is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )
    related_entities: list[RelatedEntitySummary] = []
    if include_relationships:
        relationships = await relationships_service.retrieve_related_entities(
            entity_type="form",
            entity_id=form.id,
        )
        related_entities = [
            relationship_to_related_summary(relationship, form.id)
            for relationship in relationships
        ]
    related_deadlines = await deadline_service.related_deadline_summaries_for_form(
        university_id=current_user.university_id,
        form_id=form.id,
        role=current_user.role,
    ) if include_deadlines and deadline_service is not None else []
    return form_to_response(
        form,
        related_entities=related_entities,
        related_deadlines=related_deadlines,
    )


@router.get("", response_model=FormListResponse)
async def list_forms(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[FormsService, Depends(get_forms_service)],
    q: Annotated[str | None, Query(max_length=255)] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FormListResponse:
    """List tenant-scoped forms."""

    forms, total = await service.list_forms(
        university_id=current_user.university_id,
        role=current_user.role,
        limit=limit,
        offset=offset,
        query=q,
        category=category,
        status=status_filter,
    )
    return FormListResponse(
        forms=[form_to_response(form) for form in forms],
        total=total,
        limit=limit,
        offset=offset,
    )


async def _related_deadlines_by_form(
    deadline_service: DeadlineService | None,
    university_id: UUID,
    role,
    form_ids: list[UUID],
    include_deadlines: bool,
) -> dict[UUID, list[RelatedDeadlineSummary]]:
    """Return visible related deadline summaries keyed by form ID."""

    if not include_deadlines or deadline_service is None:
        return {}
    related: dict[UUID, list[RelatedDeadlineSummary]] = {}
    for form_id in form_ids:
        related[form_id] = await deadline_service.related_deadline_summaries_for_form(
            university_id=university_id,
            form_id=form_id,
            role=role,
        )
    return related
