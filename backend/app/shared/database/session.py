"""Async SQLAlchemy engine and session management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.shared.database.config import DatabaseSettings, get_database_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: DatabaseSettings | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine from database settings."""

    database_settings = settings or get_database_settings()
    return create_async_engine(
        database_settings.sqlalchemy_database_url,
        echo=database_settings.DB_ECHO_SQL,
        pool_size=database_settings.DB_POOL_SIZE,
        max_overflow=database_settings.DB_MAX_OVERFLOW,
        pool_timeout=database_settings.DB_POOL_TIMEOUT_SECONDS,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "server_settings": {
                "search_path": "public,extensions",
            },
        },
    )


def get_engine() -> AsyncEngine:
    """Return the process-wide async database engine."""

    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory."""

    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session for FastAPI dependencies."""

    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the process-wide async engine and reset cached factories."""

    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
