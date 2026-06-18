"""FastAPI entrypoint for the UniAssist AI backend."""

import time
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.domains.analytics.services.analytics_service import AnalyticsService
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.domains.auth.services.auth_guard import AccessDeniedError, authorize_tool_access
from app.domains.calendar.api import router as calendar_router
from app.shared.observability.db import initialize_logging_db
from app.shared.observability.query_logger import QueryLogger
from app.shared.observability.models import QueryLogRecord
from app.domains.retrieval.schemas.query import QueryRequest, QueryResponse
from app.domains.auth.models.roles import UserRole
from app.domains.forms.api import router as forms_router
from app.domains.governance.review_queue import router as review_queue_router
from app.domains.ingestion.api import router as ingestion_router
from app.domains.orchestration.api import router as orchestration_router
from app.domains.relationships.api import router as relationships_router
from app.domains.retrieval.schemas.tool import ToolMetadata, ToolRequest
from app.domains.retrieval.router.fallback_handler import fallback_response
from app.domains.retrieval.router.intent_classifier import IntentClassifier
from app.domains.retrieval.router.routing_logic import RoutingLogic
from app.domains.retrieval.services.registry_factory import build_tool_registry
from app.shared.auth import get_current_user, require_any_role
from app.shared.auth.errors import forbidden_error

app = FastAPI(title=settings.APP_NAME, version=settings.API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(calendar_router)
app.include_router(forms_router)
app.include_router(review_queue_router)
app.include_router(ingestion_router)
app.include_router(relationships_router)
app.include_router(orchestration_router)
tool_registry = build_tool_registry()
intent_classifier = IntentClassifier()
routing_logic = RoutingLogic(tool_registry)
query_logger = QueryLogger()
analytics_service = AnalyticsService()
logger = get_logger(__name__)
AnyUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple service health check."""

    return {"status": "ok"}


@app.on_event("startup")
def startup() -> None:
    """Initialize persistence infrastructure."""

    initialize_logging_db()


@app.get("/tools", response_model=list[ToolMetadata])
def list_tools(_current_user: AnyUser) -> list[ToolMetadata]:
    """List all registered tools and their metadata."""

    return tool_registry.list_tools()


@app.get("/tools/{tool_name}")
def run_tool_with_query_params(
    tool_name: str,
    request: Request,
    current_user: AnyUser,
) -> dict[str, Any]:
    """Run a tool using URL query parameters for manual testing."""

    params = {
        key: _coerce_query_value(value)
        for key, value in request.query_params.items()
    }
    _authorize_direct_tool(tool_name, current_user)
    return tool_registry.run_tool(tool_name, params)


@app.post("/tools/{tool_name}")
def run_tool_with_body(
    tool_name: str,
    request: ToolRequest,
    current_user: AnyUser,
) -> dict[str, Any]:
    """Run a tool using a structured JSON request body."""

    _authorize_direct_tool(tool_name, current_user)
    return tool_registry.run_tool(tool_name, request.params)


@app.post("/query", response_model=QueryResponse)
def query_university_info(request: QueryRequest) -> QueryResponse:
    """Route a natural language query through the tool execution pipeline."""

    start_time = time.perf_counter()
    request_id = str(uuid4())
    query_text = request.query.strip()
    if not query_text:
        response = fallback_response(role=request.role)
        response.trace.request_id = request_id
        _log_query(query_text, request.role, response, start_time, request_id)
        return response

    try:
        user_role = UserRole(request.role)
    except ValueError:
        response = fallback_response(
            role=request.role,
            status="error",
            error_type="invalid_role",
            message="Unsupported role. Choose student, faculty, or admin.",
        )
        response.trace.request_id = request_id
        _log_query(query_text, request.role, response, start_time, request_id)
        return response

    try:
        decision = intent_classifier.classify(query_text)
        response = routing_logic.handle_decision(query_text, decision, user_role)
    except Exception as exc:
        logger.error("Query pipeline failed: %s", exc)
        response = fallback_response(
            role=user_role.value,
            status="error",
            error_type="query_pipeline_failed",
            message="The query pipeline failed safely.",
        )

    response.trace.request_id = request_id
    _log_query(query_text, user_role.value, response, start_time, request_id)
    return response


@app.get("/analytics/summary")
def analytics_summary(_current_user: AdminUser):
    """Return admin-only query analytics summary."""

    return analytics_service.summary()


@app.get("/analytics/tools")
def analytics_tools(_current_user: AdminUser):
    """Return admin-only tool usage counts."""

    return analytics_service.tool_counts()


@app.get("/analytics/roles")
def analytics_roles(_current_user: AdminUser):
    """Return admin-only query counts by role."""

    return analytics_service.role_counts()


@app.get("/analytics/recent")
def analytics_recent(_current_user: AdminUser, limit: int = 20):
    """Return admin-only recent query logs."""

    return analytics_service.recent_queries(limit=limit)


def _coerce_query_value(value: str) -> str | bool:
    """Convert simple query parameter strings to expected primitive values."""

    normalized_value = value.strip().lower()
    if normalized_value == "true":
        return True
    if normalized_value == "false":
        return False
    return value


def _log_query(
    query_text: str,
    role: str | None,
    response: QueryResponse,
    start_time: float,
    request_id: str,
) -> None:
    """Persist query telemetry for analytics."""

    latency_ms = max(0, round((time.perf_counter() - start_time) * 1000))
    query_logger.write(
        QueryLogRecord(
            query=query_text,
            request_id=request_id,
            tool_used=response.tool_used,
            role=role,
            confidence=response.confidence,
            latency_ms=latency_ms,
            fallback_triggered=response.status == "fallback",
            status=response.status,
        )
    )


def _authorize_direct_tool(tool_name: str, current_user: AuthenticatedUser) -> None:
    """Apply tool RBAC to direct tool execution routes."""

    tool = tool_registry.get_tool(tool_name)
    if tool is None:
        return
    try:
        authorize_tool_access(tool, current_user.role)
    except AccessDeniedError as exc:
        raise forbidden_error() from exc
