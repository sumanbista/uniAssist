"""Generate development-only Supabase-compatible JWTs for local UniAssist runs."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import jwt

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402

DEMO_ROLES = ("student", "faculty", "admin", "university_admin", "super_admin")


def main() -> int:
    """Generate and print a development JWT."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=DEMO_ROLES)
    parser.add_argument(
        "--university-id",
        type=UUID,
        default=settings.CALDWELL_UNIVERSITY_ID,
    )
    parser.add_argument("--user-id", type=UUID, default=uuid4())
    parser.add_argument("--expires-minutes", type=int, default=120)
    args = parser.parse_args()

    if os.getenv("UNIASSIST_ENV", "").casefold() == "production":
        raise SystemExit("Refusing to generate demo JWTs when UNIASSIST_ENV=production")
    if not settings.SUPABASE_JWT_SECRET:
        raise SystemExit("UNIASSIST_SUPABASE_JWT_SECRET is required")
    if args.expires_minutes < 1:
        raise SystemExit("--expires-minutes must be at least 1")

    now = datetime.now(UTC)
    claims = {
        "sub": str(args.user_id),
        "aud": settings.SUPABASE_JWT_AUDIENCE,
        "role": "authenticated",
        "app_metadata": {
            "role": args.role,
            "university_id": str(args.university_id),
            "permissions": [],
        },
        "user_metadata": {},
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=args.expires_minutes)).timestamp()),
    }
    if settings.SUPABASE_JWT_ISSUER:
        claims["iss"] = settings.SUPABASE_JWT_ISSUER

    print(jwt.encode(claims, settings.SUPABASE_JWT_SECRET, algorithm="HS256"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
