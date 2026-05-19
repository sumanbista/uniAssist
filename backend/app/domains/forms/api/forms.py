"""FastAPI routes for the Forms domain."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.forms.governance import FormsGovernanceService
from app.domains.forms.governance.service import InvalidLifecycleTransitionError
from app.domains.forms.models import Form
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.retrieval import FormsRetrievalService
from app.domains.forms.retrieval.service import RetrievedForm
from app.domains.forms.schemas import (
    FormCreate,
    FormGovernanceRequest,
    FormListResponse,
    FormResponse,
    FormSearchResponse,
    FormSearchResult,
    FormVerificationResponse,
    FormVerifyRequest,
)
from app.domains.forms.services import FormsService
from app.shared.database.session import get_db_session

router = APIRouter(prefix="/forms", tags=["forms"])


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

    return FormsGovernanceService(FormsRepository(session))


@router.post("", response_model=FormResponse, status_code=status.HTTP_201_CREATED)
async def create_form(
    form_data: FormCreate,
    service: Annotated[FormsService, Depends(get_forms_service)],
) -> FormResponse:
    """Create a canonical form."""

    form = await service.create_form(form_data)
    return _form_to_response(form)


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
        forms=[_retrieved_form_to_response(form) for form in forms],
        query=q,
        limit=limit,
    )


@router.post("/{form_id}/verify", response_model=FormVerificationResponse)
async def verify_form(
    form_id: UUID,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    request: FormVerifyRequest,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
) -> FormVerificationResponse:
    """Verify a tenant-scoped form."""

    try:
        form = await service.verify_form(
            university_id=university_id,
            form_id=form_id,
            verified_by=request.verified_by,
            verification_score=request.verification_score,
            review_notes=request.review_notes,
            expires_at=request.expires_at,
            next_review_at=request.next_review_at,
        )
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return _form_to_governance_response(form)


@router.post("/{form_id}/publish", response_model=FormVerificationResponse)
async def publish_form(
    form_id: UUID,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    request: FormGovernanceRequest,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
) -> FormVerificationResponse:
    """Publish a verified tenant-scoped form."""

    try:
        form = await service.publish_form(
            university_id=university_id,
            form_id=form_id,
            review_notes=request.review_notes,
        )
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return _form_to_governance_response(form)


@router.post("/{form_id}/archive", response_model=FormVerificationResponse)
async def archive_form(
    form_id: UUID,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    request: FormGovernanceRequest,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
) -> FormVerificationResponse:
    """Archive a tenant-scoped form."""

    try:
        form = await service.archive_form(
            university_id=university_id,
            form_id=form_id,
            review_notes=request.review_notes,
        )
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return _form_to_governance_response(form)


@router.get("/{form_id}", response_model=FormResponse)
async def get_form(
    form_id: UUID,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    service: Annotated[FormsService, Depends(get_forms_service)],
) -> FormResponse:
    """Retrieve a tenant-scoped form by ID."""

    form = await service.retrieve_form(university_id=university_id, form_id=form_id)
    if form is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )
    return _form_to_response(form)


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
        forms=[_form_to_response(form) for form in forms],
        total=total,
        limit=limit,
        offset=offset,
    )


def _form_to_response(form: Form) -> FormResponse:
    """Convert a Form ORM model into an API response schema."""

    return FormResponse(
        id=form.id,
        university_id=form.university_id,
        title=form.title,
        description=form.description,
        category=form.category,
        source_url=form.source_url,
        storage_path=form.storage_path,
        verification_status=form.verification_status,
        verification_score=float(form.verification_score)
        if form.verification_score is not None
        else None,
        last_verified_at=form.last_verified_at,
        verified_by=form.verified_by,
        review_notes=form.review_notes,
        expires_at=form.expires_at,
        next_review_at=form.next_review_at,
        review_count=form.review_count,
        staleness_score=float(form.staleness_score)
        if form.staleness_score is not None
        else None,
        status=form.status,
        metadata=form.metadata_,
        created_at=form.created_at,
        updated_at=form.updated_at,
    )


def _retrieved_form_to_response(form: RetrievedForm) -> FormSearchResult:
    """Convert a retrieved form into a search response schema."""

    return FormSearchResult(
        id=form.id,
        university_id=form.university_id,
        title=form.title,
        description=form.description,
        category=form.category,
        source_url=form.source_url,
        verification_status=form.verification_status,
        verification_score=form.verification_score,
        last_verified_at=form.last_verified_at,
        next_review_at=form.next_review_at,
        expires_at=form.expires_at,
        staleness_score=form.staleness_score,
        status=form.status,
        metadata=form.metadata,
        ranking_score=form.ranking_score,
        ranking_signals=form.ranking_signals,
    )


def _form_to_governance_response(form: Form) -> FormVerificationResponse:
    """Convert a Form ORM model into governance response metadata."""

    return FormVerificationResponse(
        id=form.id,
        university_id=form.university_id,
        verification_status=form.verification_status,
        verification_score=float(form.verification_score)
        if form.verification_score is not None
        else None,
        last_verified_at=form.last_verified_at,
        verified_by=form.verified_by,
        review_notes=form.review_notes,
        expires_at=form.expires_at,
        next_review_at=form.next_review_at,
        review_count=form.review_count,
        staleness_score=float(form.staleness_score)
        if form.staleness_score is not None
        else None,
        status=form.status,
    )
