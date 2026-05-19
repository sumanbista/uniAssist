"""FastAPI entrypoint for the UniAssist AI backend."""

import time
from uuid import uuid4
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.domains.analytics.services.analytics_service import AnalyticsService
from app.shared.observability.db import initialize_logging_db
from app.shared.observability.query_logger import QueryLogger
from app.shared.observability.models import QueryLogRecord
from app.domains.retrieval.schemas.query import QueryRequest, QueryResponse
from app.domains.auth.models.roles import UserRole
from app.domains.forms.api import router as forms_router
from app.domains.retrieval.schemas.tool import ToolMetadata, ToolRequest
from app.domains.retrieval.router.fallback_handler import fallback_response
from app.domains.retrieval.router.intent_classifier import IntentClassifier
from app.domains.retrieval.router.routing_logic import RoutingLogic
from app.domains.retrieval.services.registry_factory import build_tool_registry

app = FastAPI(title=settings.APP_NAME, version=settings.API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(forms_router)
tool_registry = build_tool_registry()
intent_classifier = IntentClassifier()
routing_logic = RoutingLogic(tool_registry)
query_logger = QueryLogger()
analytics_service = AnalyticsService()
logger = get_logger(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple service health check."""

    return {"status": "ok"}


@app.on_event("startup")
def startup() -> None:
    """Initialize persistence infrastructure."""

    initialize_logging_db()


@app.get("/tools", response_model=list[ToolMetadata])
def list_tools() -> list[ToolMetadata]:
    """List all registered tools and their metadata."""

    return tool_registry.list_tools()


@app.get("/tools/{tool_name}")
def run_tool_with_query_params(tool_name: str, request: Request) -> dict[str, Any]:
    """Run a tool using URL query parameters for manual testing."""

    params = {
        key: _coerce_query_value(value)
        for key, value in request.query_params.items()
    }
    return tool_registry.run_tool(tool_name, params)


@app.post("/tools/{tool_name}")
def run_tool_with_body(tool_name: str, request: ToolRequest) -> dict[str, Any]:
    """Run a tool using a structured JSON request body."""

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
def analytics_summary(role: str = "student"):
    """Return admin-only query analytics summary."""

    denied_response = _admin_only(role)
    if denied_response is not None:
        return denied_response
    return analytics_service.summary()


@app.get("/analytics/tools")
def analytics_tools(role: str = "student"):
    """Return admin-only tool usage counts."""

    denied_response = _admin_only(role)
    if denied_response is not None:
        return denied_response
    return analytics_service.tool_counts()


@app.get("/analytics/roles")
def analytics_roles(role: str = "student"):
    """Return admin-only query counts by role."""

    denied_response = _admin_only(role)
    if denied_response is not None:
        return denied_response
    return analytics_service.role_counts()


@app.get("/analytics/recent")
def analytics_recent(role: str = "student", limit: int = 20):
    """Return admin-only recent query logs."""

    denied_response = _admin_only(role)
    if denied_response is not None:
        return denied_response
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


def _admin_only(role: str) -> JSONResponse | None:
    """Return an access denial response unless the role is admin."""

    if role != UserRole.ADMIN.value:
        return JSONResponse(status_code=403, content={"error": "Access denied"})
    return None
