"""Async database engine, session factory, and table initialisation."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.config import Config

async_engine = create_async_engine(url=Config.DATABASE_URL, echo=False)


async def init_db() -> None:
    """Create tables that don't exist yet.

    Handy in development; production schema changes go through Alembic.
    """
    # Import registers the models on SQLModel.metadata.
    from src.db import models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async_session = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
