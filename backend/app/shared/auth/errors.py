"""Secure authentication and authorization errors."""

from fastapi import HTTPException, status


def unauthorized_error() -> HTTPException:
    """Build a generic authentication failure without sensitive details."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "UNAUTHORIZED",
            "message": "Authentication required.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden_error() -> HTTPException:
    """Build a generic authorization failure."""

    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "FORBIDDEN",
            "message": "Insufficient permissions.",
        },
    )
