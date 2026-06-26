"""Run production-readiness smoke checks against local UniAssist FastAPI."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import jwt

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402


@dataclass(frozen=True)
class SmokeCheck:
    """One named smoke check result."""

    name: str
    passed: bool
    detail: str


def main() -> int:
    """Run smoke checks and print a compact pass/fail report."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("UNIASSIST_SMOKE_BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument(
        "--university-id",
        type=UUID,
        default=settings.CALDWELL_UNIVERSITY_ID,
    )
    args = parser.parse_args()

    student_token = os.getenv("UNIASSIST_SMOKE_JWT") or create_demo_token(
        role="student",
        university_id=args.university_id,
    )
    admin_token = os.getenv("UNIASSIST_SMOKE_ADMIN_JWT") or create_demo_token(
        role="admin",
        university_id=args.university_id,
    )

    checks: list[SmokeCheck] = []
    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        checks.append(check_health(client))
        checks.append(check_auth_required(client))
        checks.append(check_contacts(client, student_token))
        checks.append(check_forms(client, student_token))
        checks.append(check_calendar(client, student_token))
        checks.append(check_deadlines(client, student_token))
        checks.append(check_relationship_traversal(client, student_token))
        checks.append(check_orchestrator(client, student_token))
        checks.append(check_governance_filtering(client, student_token, admin_token))

    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.detail}")

    return 0 if all(check.passed for check in checks) else 1


def create_demo_token(role: str, university_id: UUID) -> str:
    """Create a short-lived JWT using local development settings."""

    if not settings.SUPABASE_JWT_SECRET:
        raise SystemExit(
            "Set UNIASSIST_SMOKE_JWT or UNIASSIST_SUPABASE_JWT_SECRET before smoke testing"
        )
    now = datetime.now(UTC)
    claims = {
        "sub": str(uuid4()),
        "aud": settings.SUPABASE_JWT_AUDIENCE,
        "role": "authenticated",
        "app_metadata": {
            "role": role,
            "university_id": str(university_id),
            "permissions": [],
        },
        "user_metadata": {},
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    if settings.SUPABASE_JWT_ISSUER:
        claims["iss"] = settings.SUPABASE_JWT_ISSUER
    return jwt.encode(claims, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


def auth_headers(token: str) -> dict[str, str]:
    """Return authorization headers for one smoke request."""

    return {"Authorization": f"Bearer {token}"}


def check_health(client: httpx.Client) -> SmokeCheck:
    """Verify the API process is reachable."""

    response = client.get("/health")
    return SmokeCheck("Health", response.status_code == 200, f"status={response.status_code}")


def check_auth_required(client: httpx.Client) -> SmokeCheck:
    """Verify protected endpoints reject missing authentication."""

    missing = client.get("/contacts")
    invalid = client.get("/contacts", headers=auth_headers("not-a-jwt"))
    passed = missing.status_code == 401 and invalid.status_code == 401
    return SmokeCheck(
        "Authentication",
        passed,
        f"missing={missing.status_code} invalid={invalid.status_code}",
    )


def check_contacts(client: httpx.Client, token: str) -> SmokeCheck:
    """Verify seeded contacts are searchable."""

    response = client.get("/contacts/search", params={"q": "registrar"}, headers=auth_headers(token))
    data = safe_json(response)
    contacts = data.get("contacts", []) if isinstance(data, dict) else []
    passed = response.status_code == 200 and len(contacts) >= 1
    return SmokeCheck("Contacts", passed, f"status={response.status_code} count={len(contacts)}")


def check_forms(client: httpx.Client, token: str) -> SmokeCheck:
    """Verify seeded forms are searchable."""

    response = client.get("/forms/search", params={"q": "withdrawal"}, headers=auth_headers(token))
    data = safe_json(response)
    forms = data.get("forms", []) if isinstance(data, dict) else []
    passed = response.status_code == 200 and any("Withdrawal" in form.get("title", "") for form in forms)
    return SmokeCheck("Forms", passed, f"status={response.status_code} count={len(forms)}")


def check_calendar(client: httpx.Client, token: str) -> SmokeCheck:
    """Verify seeded calendar entries are visible."""

    response = client.get("/calendar/search", params={"q": "Fall"}, headers=auth_headers(token))
    data = safe_json(response)
    entries = data.get("entries", []) if isinstance(data, dict) else []
    passed = response.status_code == 200 and len(entries) >= 1
    return SmokeCheck("Calendar", passed, f"status={response.status_code} count={len(entries)}")


def check_deadlines(client: httpx.Client, token: str) -> SmokeCheck:
    """Verify seeded deadlines are visible."""

    response = client.get("/deadlines/search", params={"q": "withdrawal"}, headers=auth_headers(token))
    data = safe_json(response)
    deadlines = data.get("deadlines", []) if isinstance(data, dict) else []
    passed = response.status_code == 200 and len(deadlines) >= 1
    return SmokeCheck("Deadlines", passed, f"status={response.status_code} count={len(deadlines)}")


def check_relationship_traversal(client: httpx.Client, token: str) -> SmokeCheck:
    """Verify form-to-deadline relationship traversal through API enrichment."""

    response = client.get(
        "/forms/search",
        params={"q": "withdrawal", "include_deadlines": "true"},
        headers=auth_headers(token),
    )
    data = safe_json(response)
    forms = data.get("forms", []) if isinstance(data, dict) else []
    linked = [
        form
        for form in forms
        if isinstance(form, dict) and form.get("related_deadlines")
    ]
    passed = response.status_code == 200 and len(linked) >= 1
    return SmokeCheck(
        "Relationship traversal",
        passed,
        f"status={response.status_code} linked_forms={len(linked)}",
    )


def check_orchestrator(client: httpx.Client, token: str) -> SmokeCheck:
    """Verify authenticated orchestration returns a structured response."""

    response = client.post(
        "/orchestrator/query",
        json={"query": "withdrawal form deadline"},
        headers=auth_headers(token),
    )
    data = safe_json(response)
    results = data.get("results", {}) if isinstance(data, dict) else {}
    passed = response.status_code == 200 and isinstance(results, dict) and bool(results)
    return SmokeCheck(
        "Orchestrator",
        passed,
        f"status={response.status_code} result_keys={','.join(sorted(results.keys()))}",
    )


def check_governance_filtering(
    client: httpx.Client,
    student_token: str,
    admin_token: str,
) -> SmokeCheck:
    """Verify lifecycle responses remain governed for student and admin paths."""

    student_response = client.get("/forms", headers=auth_headers(student_token))
    admin_response = client.get("/forms", headers=auth_headers(admin_token))
    student_data = safe_json(student_response)
    admin_data = safe_json(admin_response)
    student_forms = student_data.get("forms", []) if isinstance(student_data, dict) else []
    admin_forms = admin_data.get("forms", []) if isinstance(admin_data, dict) else []
    allowed = {"verified", "published"}
    student_visible = all(
        isinstance(form, dict)
        and form.get("status") in allowed
        and form.get("verification_status") in allowed
        for form in student_forms
    )
    passed = (
        student_response.status_code == 200
        and admin_response.status_code == 200
        and student_visible
        and len(admin_forms) >= len(student_forms)
    )
    return SmokeCheck(
        "Governance filtering",
        passed,
        (
            f"student={student_response.status_code}/{len(student_forms)} "
            f"admin={admin_response.status_code}/{len(admin_forms)}"
        ),
    )


def safe_json(response: httpx.Response) -> object:
    """Return parsed JSON or an empty object for non-JSON responses."""

    try:
        return response.json()
    except ValueError:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
