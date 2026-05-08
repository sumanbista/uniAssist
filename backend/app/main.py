"""FastAPI entrypoint for the UniAssist AI backend."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.models.query import QueryRequest, QueryResponse
from app.models.roles import UserRole
from app.models.tool import ToolMetadata, ToolRequest
from app.router.fallback_handler import fallback_response
from app.router.intent_classifier import IntentClassifier
from app.router.routing_logic import RoutingLogic
from app.services.registry_factory import build_tool_registry

app = FastAPI(title=settings.APP_NAME, version=settings.API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
tool_registry = build_tool_registry()
intent_classifier = IntentClassifier()
routing_logic = RoutingLogic(tool_registry)
logger = get_logger(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple service health check."""

    return {"status": "ok"}


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

    query_text = request.query.strip()
    if not query_text:
        return fallback_response(role=request.role)

    try:
        user_role = UserRole(request.role)
    except ValueError:
        return fallback_response(
            role=request.role,
            status="error",
            error_type="invalid_role",
            message="Unsupported role. Choose student, faculty, or admin.",
        )

    try:
        decision = intent_classifier.classify(query_text)
        return routing_logic.handle_decision(query_text, decision, user_role)
    except Exception as exc:
        logger.error("Query pipeline failed: %s", exc)
        return fallback_response()


def _coerce_query_value(value: str) -> str | bool:
    """Convert simple query parameter strings to expected primitive values."""

    normalized_value = value.strip().lower()
    if normalized_value == "true":
        return True
    if normalized_value == "false":
        return False
    return value
