"""Alembic environment wired to shared database metadata."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.domains.calendar.models import AcademicCalendarEntry
from app.domains.contacts.models import Contact
from app.domains.deadlines.models import Deadline
from app.domains.forms.models import Form, FormRelationship
from app.domains.ingestion.models import RawPage
from app.domains.relationships.models import EntityRelationship
from app.shared.database.base import Base
from app.shared.database.config import get_database_settings
from app.shared.events.models import EventStoreRecord

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_registered_models = (
    Form,
    FormRelationship,
    EntityRelationship,
    EventStoreRecord,
    AcademicCalendarEntry,
    Contact,
    Deadline,
    RawPage,
)


def get_database_url() -> str:
    """Return the configured async database URL for migrations."""

    return get_database_settings().sqlalchemy_database_url


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with an active connection."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async migration engine and run migrations."""

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        pool_pre_ping=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
