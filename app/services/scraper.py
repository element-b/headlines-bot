from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Source
from app.db.repositories.headline import HeadlineRepository, SourceRepository
from app.sources.base import BaseSource


class ScraperService:
    """Background service for fetching and storing headlines."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sources_registry: dict[str, BaseSource],
        interval_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._sources_registry = sources_registry
        self._interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        """Request graceful stop."""
        self._stop_event.set()

    async def run(self) -> None:
        """Run scraper loop until stop is requested."""
        logger.info("Scraper service started.")

        try:
            while not self._stop_event.is_set():
                await self.run_once()
                await self._sleep_until_next_iteration()
        except asyncio.CancelledError:
            logger.info("Scraper service cancelled.")
            raise
        finally:
            logger.info("Scraper service stopped.")

    async def run_once(self) -> None:
        """Execute one scraping iteration."""
        async with self._session_factory() as session:
            source_repository = SourceRepository(session)
            active_sources = await source_repository.list_active_sources()

        tasks = [
            self._process_source(source)
            for source in active_sources
            if source.slug in self._sources_registry
        ]

        if not tasks:
            logger.warning("No active sources available for scraping.")
            return

        await asyncio.gather(*tasks, return_exceptions=False)

    async def _process_source(self, source_record: Source) -> None:
        """Fetch and store headlines for a single source."""
        source_client = self._sources_registry.get(source_record.slug)
        if source_client is None:
            logger.warning("Source '{}' is active in DB but absent in registry.", source_record.slug)
            return

        try:
            headlines = await source_client.fetch()
            if not headlines:
                logger.info("Source '{}' returned no headlines.", source_record.slug)
                return

            async with self._session_factory() as session:
                headline_repository = HeadlineRepository(session)
                inserted = await headline_repository.bulk_insert(
                    source_id=source_record.id,
                    headlines=headlines,
                )

            logger.info(
                "Source '{}' processed successfully. Fetched: {}, inserted: {}.",
                source_record.slug,
                len(headlines),
                inserted,
            )

        except Exception:
            logger.exception("Unhandled error while processing source '{}'.", source_record.slug)

    async def _sleep_until_next_iteration(self) -> None:
        """Sleep until the next loop iteration or until stop is requested."""
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
        except asyncio.TimeoutError:
            return