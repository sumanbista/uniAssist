"""FastAPI routes for the Forms domain."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.forms.api.serializers import (
    form_to_governance_response,
    form_to_response,
    relationship_to_related_summary,
    retrieved_form_to_response,
)
from app.domains.forms.governance import FormsGovernanceService
from app.domains.forms.governance.service import InvalidLifecycleTransitionError
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.retrieval import FormsRetrievalService
from app.domains.forms.schemas import (
    FormCreate,
    FormGovernanceRequest,
    FormListResponse,
    FormResponse,
    FormSearchResponse,
    FormVerificationResponse,
    FormVerifyRequest,
    RelatedEntitySummary,
)
from app.domains.forms.services import FormsService
from app.domains.forms.services import (
    FormFileAccessDeniedError,
    FormFileNotFoundError,
    FormsFileAccessService,
)
from app.domains.relationships.repositories import RelationshipsRepository
from app.domains.relationships.services import RelationshipsService
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.shared.auth import get_current_user, require_any_role, scoped_university_id
from app.core.logging import get_logger
from app.shared.database.session import get_db_session
from app.shared.events import EventBus, EventContext, EventStore

router = APIRouter(prefix="/forms", tags=["forms"])
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]
logger = get_logger(__name__)


def get_forms_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormsService:
    """Build a Forms service for a request."""

    return FormsService(FormsRepository(session))


def get_forms_retrieval_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormsRetrievalService:
    """Build a Forms retrieval service for a request."""

    return FormsRetrievalService(FormsRepository(session))


def get_forms_governance_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormsGovernanceService:
    """Build a Forms governance service for a request."""

    return FormsGovernanceService(
        FormsRepository(session),
        event_bus=EventBus(EventStore(session)),
    )


def get_relationships_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RelationshipsService:
    """Build a Relationships service for optional Forms summaries."""

    return RelationshipsService(RelationshipsRepository(session))


def get_forms_file_access_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormsFileAccessService:
    """Build a Forms file access service for a request."""

    return FormsFileAccessService(FormsRepository(session))


@router.post("", response_model=FormResponse, status_code=status.HTTP_201_CREATED)
async def create_form(
    form_data: FormCreate,
    service: Annotated[FormsService, Depends(get_forms_service)],
) -> FormResponse:
    """Create a canonical form."""

    form = await service.create_form(form_data)
    return form_to_response(form)


@router.get("/search", response_model=FormSearchResponse)
async def search_forms(
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    service: Annotated[
        FormsRetrievalService,
        Depends(get_forms_retrieval_service),
    ],
    q: Annotated[str, Query(min_length=1, max_length=255)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> FormSearchResponse:
    """Search forms with PostgreSQL FTS and deterministic ranking."""

    forms = await service.retrieve_forms(
        query=q,
        university_id=university_id,
        limit=limit,
    )
    return FormSearchResponse(
        forms=[retrieved_form_to_response(form) for form in forms],
        query=q,
        limit=limit,
    )


@router.get("/search/semantic", response_model=FormSearchResponse)
async def semantic_search_forms(
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
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
        university_id=university_id,
        limit=limit,
    )
    return FormSearchResponse(
        forms=[retrieved_form_to_response(form) for form in forms],
        query=q,
        limit=limit,
    )


@router.post("/{form_id}/verify", response_model=FormVerificationResponse)
async def verify_form(
    form_id: UUID,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    request: FormVerifyRequest,
    current_user: AdminUser,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> FormVerificationResponse:
    """Verify a tenant-scoped form."""

    scoped_university = scoped_university_id(current_user, university_id)
    logger.info(
        "Governance action requested: action=form.verify user_id=%s university_id=%s form_id=%s",
        current_user.user_id,
        scoped_university,
        form_id,
    )
    try:
        form = await service.verify_form(
            university_id=scoped_university,
            form_id=form_id,
            verified_by=current_user.user_id,
            verification_score=request.verification_score,
            review_notes=request.review_notes,
            expires_at=request.expires_at,
            next_review_at=request.next_review_at,
            event_context=EventContext(
                actor_id=current_user.user_id,
                correlation_id=correlation_id,
            ),
        )
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return form_to_governance_response(form)


@router.post("/{form_id}/publish", response_model=FormVerificationResponse)
async def publish_form(
    form_id: UUID,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    request: FormGovernanceRequest,
    current_user: AdminUser,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> FormVerificationResponse:
    """Publish a verified tenant-scoped form."""

    scoped_university = scoped_university_id(current_user, university_id)
    logger.info(
        "Governance action requested: action=form.publish user_id=%s university_id=%s form_id=%s",
        current_user.user_id,
        scoped_university,
        form_id,
    )
    try:
        form = await service.publish_form(
            university_id=scoped_university,
            form_id=form_id,
            review_notes=request.review_notes,
            event_context=EventContext(
                actor_id=current_user.user_id,
                correlation_id=correlation_id,
            ),
        )
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return form_to_governance_response(form)


@router.post("/{form_id}/archive", response_model=FormVerificationResponse)
async def archive_form(
    form_id: UUID,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    request: FormGovernanceRequest,
    current_user: AdminUser,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> FormVerificationResponse:
    """Archive a tenant-scoped form."""

    scoped_university = scoped_university_id(current_user, university_id)
    logger.info(
        "Governance action requested: action=form.archive user_id=%s university_id=%s form_id=%s",
        current_user.user_id,
        scoped_university,
        form_id,
    )
    try:
        form = await service.archive_form(
            university_id=scoped_university,
            form_id=form_id,
            review_notes=request.review_notes,
            event_context=EventContext(
                actor_id=current_user.user_id,
                correlation_id=correlation_id,
            ),
        )
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return form_to_governance_response(form)


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
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    service: Annotated[FormsService, Depends(get_forms_service)],
    relationships_service: Annotated[
        RelationshipsService,
        Depends(get_relationships_service),
    ],
    include_relationships: Annotated[bool, Query()] = False,
) -> FormResponse:
    """Retrieve a tenant-scoped form by ID."""

    form = await service.retrieve_form(university_id=university_id, form_id=form_id)
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
    return form_to_response(form, related_entities=related_entities)


@router.get("", response_model=FormListResponse)
async def list_forms(
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    service: Annotated[FormsService, Depends(get_forms_service)],
    q: Annotated[str | None, Query(max_length=255)] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FormListResponse:
    """List tenant-scoped forms."""

    forms, total = await service.list_forms(
        university_id=university_id,
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
