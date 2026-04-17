from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Headline, SentHeadline, Source
from app.sources.base import HeadlineData
from app.sources.registry import DEFAULT_SOURCE_DEFINITIONS, LEGACY_DISABLED_SOURCE_SLUGS


class SourceRepository:
    """Repository for sources table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed_defaults(self) -> int:
        """Upsert default sources and deactivate legacy unsupported sources."""
        payload = [
            {
                "name": item.name,
                "slug": item.slug,
                "url": item.url,
                "source_type": item.source_type,
                "is_active": True,
            }
            for item in DEFAULT_SOURCE_DEFINITIONS
        ]

        insert_stmt = insert(Source).values(payload)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[Source.slug],
            set_={
                "name": insert_stmt.excluded.name,
                "url": insert_stmt.excluded.url,
                "source_type": insert_stmt.excluded.source_type,
                "is_active": True,
            },
        )

        upsert_result = await self.session.execute(upsert_stmt)

        deactivated_count = 0
        if LEGACY_DISABLED_SOURCE_SLUGS:
            deactivate_stmt = (
                update(Source)
                .where(Source.slug.in_(LEGACY_DISABLED_SOURCE_SLUGS))
                .values(is_active=False)
            )
            deactivate_result = await self.session.execute(deactivate_stmt)
            deactivated_count = deactivate_result.rowcount or 0

        await self.session.commit()

        return (upsert_result.rowcount or 0) + deactivated_count

    async def list_active_sources(self) -> list[Source]:
        """Return all active sources."""
        stmt = (
            select(Source)
            .where(Source.is_active.is_(True))
            .order_by(Source.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_sources(self) -> list[Source]:
        """Return all sources."""
        stmt = select(Source).order_by(Source.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, source_id: int) -> Source | None:
        """Return source by ID."""
        stmt = select(Source).where(Source.id == source_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Source | None:
        """Return source by slug."""
        stmt = select(Source).where(Source.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class HeadlineRepository:
    """Repository for headlines."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert(self, source_id: int, headlines: Sequence[HeadlineData]) -> int:
        """Insert headlines with deduplication by URL."""
        if not headlines:
            return 0

        payload = [
            {
                "source_id": source_id,
                "title": item.title[:500],
                "url": item.url[:1000],
                "published_at": item.published_at,
            }
            for item in headlines
        ]

        stmt = (
            insert(Headline)
            .values(payload)
            .on_conflict_do_nothing(index_elements=[Headline.url])
            .returning(Headline.id)
        )

        result = await self.session.execute(stmt)
        inserted_ids = list(result.scalars().all())
        await self.session.commit()
        return len(inserted_ids)

    async def get_latest_by_source(self, source_id: int, limit: int) -> list[Headline]:
        """Return latest headlines for a source."""
        stmt = (
            select(Headline)
            .options(joinedload(Headline.source))
            .where(Headline.source_id == source_id)
            .order_by(
                desc(func.coalesce(Headline.published_at, Headline.created_at)),
                desc(Headline.id),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_all(self, limit: int) -> list[Headline]:
        """Return latest headlines across all sources."""
        stmt = (
            select(Headline)
            .options(joinedload(Headline.source))
            .order_by(
                desc(func.coalesce(Headline.published_at, Headline.created_at)),
                desc(Headline.id),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class SentHeadlineRepository:
    """Repository for sent_headlines table and notification queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_unsent_for_user(
        self,
        user_id: int,
        source_ids: Sequence[int],
        limit: int | None = None,
    ) -> list[Headline]:
        """Return headlines that were not yet sent to the user."""
        if not source_ids:
            return []

        if limit is not None and limit <= 0:
            return []

        stmt = (
            select(Headline)
            .options(joinedload(Headline.source))
            .outerjoin(
                SentHeadline,
                and_(
                    SentHeadline.headline_id == Headline.id,
                    SentHeadline.user_id == user_id,
                ),
            )
            .where(
                Headline.source_id.in_(list(source_ids)),
                SentHeadline.id.is_(None),
            )
            .order_by(
                desc(func.coalesce(Headline.published_at, Headline.created_at)),
                desc(Headline.id),
            )
        )

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_many_as_sent(self, user_id: int, headline_ids: Sequence[int]) -> int:
        """Mark multiple headlines as sent for the user."""
        if not headline_ids:
            return 0

        payload = [
            {
                "user_id": user_id,
                "headline_id": headline_id,
            }
            for headline_id in headline_ids
        ]

        stmt = (
            insert(SentHeadline)
            .values(payload)
            .on_conflict_do_nothing(
                index_elements=[SentHeadline.user_id, SentHeadline.headline_id],
            )
            .returning(SentHeadline.id)
        )
        result = await self.session.execute(stmt)
        inserted_ids = list(result.scalars().all())
        await self.session.commit()
        return len(inserted_ids)