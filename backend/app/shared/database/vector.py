"""SQLAlchemy support for pgvector columns."""

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """PostgreSQL pgvector column type."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        """Return pgvector column specification."""

        return f"vector({self.dimensions})"
