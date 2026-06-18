"""Governance lifecycle routes for Forms."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.logging import get_logger
from app.domains.forms.api.dependencies import (
    AdminUser,
    get_forms_governance_service,
)
from app.domains.forms.api.serializers import form_to_governance_response
from app.domains.forms.governance import FormsGovernanceService
from app.domains.forms.governance.service import InvalidLifecycleTransitionError
from app.domains.forms.schemas import (
    FormGovernanceRequest,
    FormVerificationResponse,
    FormVerifyRequest,
)
from app.shared.events import EventContext

router = APIRouter()
logger = get_logger(__name__)


@router.post("/{form_id}/verify", response_model=FormVerificationResponse)
async def verify_form(
    form_id: UUID,
    request: FormVerifyRequest,
    current_user: AdminUser,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> FormVerificationResponse:
    """Verify a tenant-scoped form."""

    logger.info(
        "Governance action requested: action=form.verify user_id=%s university_id=%s form_id=%s",
        current_user.user_id,
        current_user.university_id,
        form_id,
    )
    try:
        form = await service.verify_form(
            university_id=current_user.university_id,
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
    request: FormGovernanceRequest,
    current_user: AdminUser,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> FormVerificationResponse:
    """Publish a verified tenant-scoped form."""

    logger.info(
        "Governance action requested: action=form.publish user_id=%s university_id=%s form_id=%s",
        current_user.user_id,
        current_user.university_id,
        form_id,
    )
    try:
        form = await service.publish_form(
            university_id=current_user.university_id,
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
    request: FormGovernanceRequest,
    current_user: AdminUser,
    service: Annotated[
        FormsGovernanceService,
        Depends(get_forms_governance_service),
    ],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> FormVerificationResponse:
    """Archive a tenant-scoped form."""

    logger.info(
        "Governance action requested: action=form.archive user_id=%s university_id=%s form_id=%s",
        current_user.user_id,
        current_user.university_id,
        form_id,
    )
    try:
        form = await service.archive_form(
            university_id=current_user.university_id,
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
