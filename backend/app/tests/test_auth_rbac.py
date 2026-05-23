"""Tests for authentication, RBAC, and tenant enforcement foundations."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.domains.auth.models.roles import UserRole
from app.shared.auth.jwt import SupabaseJWTVerifier
from app.shared.auth.tenant import enforce_university_scope


def test_supabase_jwt_verifier_builds_canonical_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid Supabase-style claims should produce an authenticated user context."""

    jwt_secret = "test-secret-with-at-least-32-bytes"
    university_id = uuid4()
    user_id = uuid4()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", "https://example.supabase.co/auth/v1")
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "iss": "https://example.supabase.co/auth/v1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "app_metadata": {
                "university_id": str(university_id),
                "role": "admin",
                "permissions": ["governance:write", "relationships:write"],
                "department_scope": " Registrar ",
            },
        },
        jwt_secret,
        algorithm="HS256",
    )

    user = SupabaseJWTVerifier().verify(token)

    assert user.user_id == user_id
    assert user.university_id == university_id
    assert user.role == UserRole.ADMIN
    assert "governance:write" in user.permissions
    assert user.department_scope == "registrar"


def test_supabase_jwt_verifier_rejects_expired_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expired JWTs should fail closed."""

    jwt_secret = "test-secret-with-at-least-32-bytes"
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", None)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "aud": "authenticated",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
            "app_metadata": {
                "university_id": str(uuid4()),
                "role": "admin",
            },
        },
        jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(Exception) as exc_info:
        SupabaseJWTVerifier().verify(token)

    assert getattr(exc_info.value, "status_code", None) == 401


def test_tenant_enforcement_rejects_cross_university_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tenant enforcement should reject mismatched university scopes."""

    jwt_secret = "test-secret-with-at-least-32-bytes"
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", None)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "aud": "authenticated",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "app_metadata": {
                "university_id": str(uuid4()),
                "role": "admin",
            },
        },
        jwt_secret,
        algorithm="HS256",
    )
    user = SupabaseJWTVerifier().verify(token)

    with pytest.raises(Exception) as exc_info:
        enforce_university_scope(user, uuid4())

    assert getattr(exc_info.value, "status_code", None) == 403


def test_governance_endpoint_requires_authentication() -> None:
    """Protected governance routes should fail closed without a bearer token."""

    client = TestClient(app)
    response = client.post(
        f"/forms/{uuid4()}/publish",
        headers={"X-University-ID": str(uuid4())},
        json={"review_notes": "ready"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHORIZED"
