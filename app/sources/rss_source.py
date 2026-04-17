from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import struct_time

import feedparser
from loguru import logger

from app.sources.base import BaseSource, HeadlineData


class RssSource(BaseSource):
    """Generic RSS source implementation."""

    source_type = "rss"

    def __init__(
        self,
        session,
        name: str,
        slug: str,
        url: str,
        timeout_seconds: int = 15,
    ) -> None:
        super().__init__(session=session, timeout_seconds=timeout_seconds)
        self.name = name
        self.slug = slug
        self.url = url

    async def fetch(self) -> list[HeadlineData]:
        """Fetch headlines from RSS feed."""
        try:
            async with self.session.get(
                self.url,
                timeout=self.build_timeout(),
            ) as response:
                if response.status != 200:
                    logger.error(
                        "RSS source '{}' returned status {} for URL {}",
                        self.slug,
                        response.status,
                        self.url,
                    )
                    return []

                content = await response.text()

            feed = await asyncio.to_thread(feedparser.parse, content)

            headlines: list[HeadlineData] = []
            for entry in feed.entries:
                title = str(entry.get("title", "")).strip()
                link = str(entry.get("link", "")).strip()

                if not title or not link:
                    continue

                published_at = self._parse_entry_datetime(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                )

                headlines.append(
                    HeadlineData(
                        title=title,
                        url=self.make_absolute_url(link),
                        published_at=published_at,
                    )
                )

            return self.deduplicate(headlines)

        except Exception:
            logger.exception("Failed to fetch RSS source '{}'", self.slug)
            return []

    @staticmethod
    def _parse_entry_datetime(value: struct_time | None) -> datetime | None:
        """Convert RSS struct_time to UTC datetime."""
        if value is None:
            return None

        return datetime(
            year=value.tm_year,
            month=value.tm_mon,
            day=value.tm_mday,
            hour=value.tm_hour,
            minute=value.tm_min,
            second=value.tm_sec,
            tzinfo=timezone.utc,
        )