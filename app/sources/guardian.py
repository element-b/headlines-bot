from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.sources.base import BaseSource, HeadlineData


class GuardianSource(BaseSource):
    """The Guardian Open Platform API source implementation."""

    name = "The Guardian"
    slug = "guardian"
    url = "https://www.theguardian.com"
    source_type = "api"
    api_url = "https://content.guardianapis.com/search"

    def __init__(
        self,
        session,
        api_key: str,
        sections: tuple[str, ...] = ("business", "world"),
        page_size: int = 20,
        timeout_seconds: int = 15,
    ) -> None:
        super().__init__(session=session, timeout_seconds=timeout_seconds)
        self.api_key = api_key.strip()
        self.sections = sections
        self.page_size = page_size
        self._missing_api_key_logged = False

    @property
    def headers(self) -> dict[str, str]:
        """Return HTTP headers for API calls."""
        return {
            "Accept": "application/json",
            "User-Agent": "headlines-bot/1.0",
        }

    async def fetch(self) -> list[HeadlineData]:
        """Fetch headlines from configured Guardian sections."""
        if not self.api_key:
            if not self._missing_api_key_logged:
                logger.warning(
                    "Guardian API key is not configured. Source '{}' will return no headlines.",
                    self.slug,
                )
                self._missing_api_key_logged = True
            return []

        tasks = [self._fetch_section(section) for section in self.sections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        headlines: list[HeadlineData] = []

        for section, result in zip(self.sections, results, strict=False):
            if isinstance(result, Exception):
                logger.error(
                    "Unhandled error while fetching Guardian section '{}': {}",
                    section,
                    result,
                )
                continue

            headlines.extend(result)

        return self.deduplicate(headlines)

    async def _fetch_section(self, section: str) -> list[HeadlineData]:
        """Fetch headlines for a single Guardian section."""
        params = {
            "api-key": self.api_key,
            "section": section,
            "page-size": str(self.page_size),
            "order-by": "newest",
            "use-date": "published",
        }

        try:
            async with self.session.get(
                self.api_url,
                params=params,
                headers=self.headers,
                timeout=self.build_timeout(),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        "Guardian API returned status {} for section '{}'. Body: {}",
                        response.status,
                        section,
                        error_text[:500],
                    )
                    return []

                payload = await response.json(content_type=None)

        except Exception:
            logger.exception("Failed to fetch Guardian section '{}'.", section)
            return []

        response_block = payload.get("response")
        if not isinstance(response_block, dict):
            logger.error("Guardian API returned invalid payload for section '{}'.", section)
            return []

        if response_block.get("status") != "ok":
            logger.error(
                "Guardian API returned non-ok status for section '{}': {}",
                section,
                response_block.get("status"),
            )
            return []

        results = response_block.get("results")
        if not isinstance(results, list):
            logger.error("Guardian API returned invalid results list for section '{}'.", section)
            return []

        headlines: list[HeadlineData] = []

        for item in results:
            if not isinstance(item, dict):
                continue

            if item.get("type") != "article":
                continue

            title = str(item.get("webTitle", "")).strip()
            raw_url = str(item.get("webUrl", "")).strip()
            published_at = self._parse_datetime(item.get("webPublicationDate"))

            if not title or not raw_url:
                continue

            headlines.append(
                HeadlineData(
                    title=title,
                    url=self.normalize_url(raw_url),
                    published_at=published_at,
                )
            )

        return headlines

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse ISO datetime from Guardian API."""
        if value is None:
            return None

        raw_value = str(value).strip()
        if not raw_value:
            return None

        normalized = raw_value.replace("Z", "+00:00")

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            logger.warning("Failed to parse Guardian datetime '{}'.", raw_value)
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)

        return parsed