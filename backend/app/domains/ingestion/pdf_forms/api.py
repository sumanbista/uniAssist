"""FastAPI routes for admin-uploaded PDF form ingestion."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.domains.ingestion.pdf_forms.schemas import (
    PdfFormUploadInput,
    PdfFormUploadResponse,
)
from app.domains.ingestion.pdf_forms.service import (
    PdfFormIngestionError,
    PdfFormIngestionService,
)
from app.shared.auth import require_any_role
from app.shared.database.session import get_db_session
from app.shared.events import EventContext

router = APIRouter(tags=["ingestion"])
logger = get_logger(__name__)
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]


def get_pdf_form_ingestion_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PdfFormIngestionService:
    """Build the PDF form ingestion service for the request."""

    return PdfFormIngestionService(session)


@router.post("/forms/pdf", response_model=PdfFormUploadResponse)
async def upload_pdf_form(
    current_user: AdminUser,
    service: Annotated[
        PdfFormIngestionService,
        Depends(get_pdf_form_ingestion_service),
    ],
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form(max_length=4000)] = None,
    category: Annotated[str | None, Form(max_length=100)] = None,
    department: Annotated[str | None, Form(max_length=100)] = None,
    source_url: Annotated[str | None, Form()] = None,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> PdfFormUploadResponse:
    """Upload one admin-managed PDF form as a pending-review resource."""

    try:
        metadata = PdfFormUploadInput(
            title=title,
            description=description,
            category=category,
            department=department,
            source_url=source_url,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    logger.info(
        "pdf_form_upload_requested user_id=%s university_id=%s content_type=%s",
        current_user.user_id,
        current_user.university_id,
        file.content_type,
    )
    try:
        return await service.ingest_pdf_form(
            university_id=current_user.university_id,
            upload=file,
            metadata=metadata,
            event_context=EventContext(
                actor_id=current_user.user_id,
                correlation_id=correlation_id,
            ),
        )
    except PdfFormIngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
