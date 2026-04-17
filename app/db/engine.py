from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create asynchronous SQLAlchemy engine."""
    connect_args: dict[str, object] = {
        "statement_cache_size": 0,
    }

    return create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
        pool_pre_ping=False,
        pool_recycle=900,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_use_lifo=True,
        connect_args=connect_args,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create asynchronous SQLAlchemy session factory."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


_settings = get_settings()
engine: AsyncEngine = create_engine(_settings)
session_factory: async_sessionmaker[AsyncSession] = create_session_factory(engine)