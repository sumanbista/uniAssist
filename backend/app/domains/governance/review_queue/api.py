"""FastAPI routes for governance review queues."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.domains.governance.review_queue.schemas import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewItemResponse,
)
from app.domains.governance.review_queue.service import (
    InvalidReviewDecisionError,
    ReviewQueueService,
)
from app.shared.auth import require_any_role
from app.shared.database.session import get_db_session
from app.shared.events import EventContext

router = APIRouter(prefix="/governance/reviews", tags=["governance"])
logger = get_logger(__name__)
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]


def get_review_queue_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewQueueService:
    """Build a review queue service for the request."""

    return ReviewQueueService(session)


@router.get("/pending", response_model=list[ReviewItemResponse])
async def list_pending_reviews(
    current_user: AdminUser,
    service: Annotated[ReviewQueueService, Depends(get_review_queue_service)],
    entity_type: Annotated[str, Query(min_length=1, max_length=50)] = "form",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReviewItemResponse]:
    """List pending tenant-scoped review items."""

    logger.info(
        "review_queue_list_requested user_id=%s university_id=%s entity_type=%s",
        current_user.user_id,
        current_user.university_id,
        entity_type,
    )
    try:
        return await service.list_pending_reviews(
            university_id=current_user.university_id,
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )
    except InvalidReviewDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{entity_type}/{entity_id}", response_model=ReviewItemResponse)
async def get_review_item(
    entity_type: str,
    entity_id: UUID,
    current_user: AdminUser,
    service: Annotated[ReviewQueueService, Depends(get_review_queue_service)],
) -> ReviewItemResponse:
    """Retrieve one tenant-scoped review item."""

    try:
        item = await service.get_review_item(
            university_id=current_user.university_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except InvalidReviewDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )
    return item


@router.post("/decision", response_model=ReviewDecisionResponse)
async def decide_review(
    request: ReviewDecisionRequest,
    current_user: AdminUser,
    service: Annotated[ReviewQueueService, Depends(get_review_queue_service)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> ReviewDecisionResponse:
    """Apply an admin review decision to a pending item."""

    logger.info(
        "review_decision_requested user_id=%s university_id=%s entity_type=%s entity_id=%s decision=%s",
        current_user.user_id,
        current_user.university_id,
        request.entity_type,
        request.entity_id,
        request.decision.value,
    )
    try:
        response = await service.decide_review(
            university_id=current_user.university_id,
            request=request,
            event_context=EventContext(
                actor_id=current_user.user_id,
                correlation_id=correlation_id,
            ),
        )
    except InvalidReviewDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )
    return response
