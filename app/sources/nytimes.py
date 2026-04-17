from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.sources.base import BaseSource, HeadlineData


class NewYorkTimesSource(BaseSource):
    """The New York Times Article Search API source implementation."""

    name = "The New York Times"
    slug = "nytimes"
    url = "https://www.nytimes.com"
    source_type = "api"
    api_url = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

    def __init__(
        self,
        session,
        api_key: str,
        sections: tuple[str, ...] = ("business", "world"),
        timeout_seconds: int = 15,
    ) -> None:
        super().__init__(session=session, timeout_seconds=timeout_seconds)
        self.api_key = api_key.strip()

        normalized_sections = tuple(
            self._normalize_section_name(section)
            for section in sections
            if section.strip()
        )
        self.sections = normalized_sections if normalized_sections else ("Business", "World")

        self._missing_api_key_logged = False

    @property
    def headers(self) -> dict[str, str]:
        """Return HTTP headers for API calls."""
        return {
            "Accept": "application/json",
            "User-Agent": "headlines-bot/1.0",
        }

    async def fetch(self) -> list[HeadlineData]:
        """Fetch latest headlines from NYT Article Search API."""
        if not self.api_key:
            if not self._missing_api_key_logged:
                logger.warning(
                    "NYTimes API key is not configured. Source '{}' will return no headlines.",
                    self.slug,
                )
                self._missing_api_key_logged = True
            return []

        params = {
            "api-key": self.api_key,
            "sort": "newest",
            "page": "0",
            "fq": self._build_filter_query(),
        }

        try:
            async with self.session.get(
                self.api_url,
                params=params,
                headers=self.headers,
                timeout=self.build_timeout(),
            ) as response:
                if response.status == 429:
                    error_text = await response.text()
                    logger.error(
                        "NYTimes Article Search API rate limit exceeded for source '{}'. "
                        "Status: {}. Body: {}",
                        self.slug,
                        response.status,
                        error_text[:500],
                    )
                    return []

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        "NYTimes Article Search API returned status {} for source '{}'. Body: {}",
                        response.status,
                        self.slug,
                        error_text[:500],
                    )
                    return []

                payload = await response.json(content_type=None)

        except Exception:
            logger.exception("Failed to fetch NYTimes headlines.")
            return []

        status = str(payload.get("status", "")).strip()
        if status.lower() != "ok":
            logger.error(
                "NYTimes Article Search API returned non-ok status for source '{}': {}",
                self.slug,
                status,
            )
            return []

        response_block = payload.get("response")
        if not isinstance(response_block, dict):
            logger.error("NYTimes Article Search API returned invalid response block.")
            return []

        docs = response_block.get("docs")
        if not isinstance(docs, list):
            logger.error("NYTimes Article Search API returned invalid docs list.")
            return []

        headlines: list[HeadlineData] = []

        for item in docs:
            if not isinstance(item, dict):
                continue

            title = self._extract_title(item)
            raw_url = self._extract_url(item)
            published_at = self._extract_published_at(item)

            if not title or not raw_url:
                continue

            headlines.append(
                HeadlineData(
                    title=title,
                    url=self.normalize_url(raw_url),
                    published_at=published_at,
                )
            )

        return self.deduplicate(headlines)

    def _build_filter_query(self) -> str:
        """Build Article Search API filter query."""
        section_filter = self._build_section_filter()

        return (
            'source.vernacular:"The New York Times" '
            f"AND {section_filter}"
        )

    def _build_section_filter(self) -> str:
        """Build section filter for one or multiple NYT sections."""
        if len(self.sections) == 1:
            return f'section.name:"{self.sections[0]}"'

        joined_sections = ", ".join(f'"{section}"' for section in self.sections)
        return f"section.name:({joined_sections})"

    @staticmethod
    def _normalize_section_name(section: str) -> str:
        """Normalize configured section aliases to NYT section names."""
        value = section.strip().lower()

        aliases = {
            "arts": "Arts",
            "books": "Books",
            "business": "Business",
            "climate": "Climate",
            "fashion": "Fashion",
            "food": "Food",
            "health": "Health",
            "home": "Home Page",
            "home page": "Home Page",
            "movies": "Movies",
            "new york": "New York",
            "opinion": "Opinion",
            "politics": "Politics",
            "real estate": "Real Estate",
            "science": "Science",
            "sports": "Sports",
            "style": "Style",
            "technology": "Technology",
            "travel": "Travel",
            "u.s.": "U.S.",
            "us": "U.S.",
            "world": "World",
            "your money": "Your Money",
        }

        if value in aliases:
            return aliases[value]

        return " ".join(part.capitalize() for part in value.split())

    @staticmethod
    def _extract_title(item: dict[str, Any]) -> str:
        """Extract title from NYT document."""
        headline = item.get("headline")

        if isinstance(headline, dict):
            for key in ("default", "main", "seo"):
                raw_value = headline.get(key)
                if raw_value is None:
                    continue

                title = str(raw_value).strip()
                if title:
                    return title

        for key in ("title", "summary", "abstract", "snippet"):
            raw_value = item.get(key)
            if raw_value is None:
                continue

            title = str(raw_value).strip()
            if title:
                return title

        return ""

    @staticmethod
    def _extract_url(item: dict[str, Any]) -> str:
        """Extract article URL from NYT document."""
        for key in ("url", "web_url"):
            raw_value = item.get(key)
            if raw_value is None:
                continue

            url = str(raw_value).strip()
            if url:
                return url

        return ""

    @classmethod
    def _extract_published_at(cls, item: dict[str, Any]) -> datetime | None:
        """Extract published datetime from NYT document."""
        for key in ("firstPublished", "pub_date", "published_date", "created_date", "updated_date"):
            raw_value = item.get(key)
            parsed = cls._parse_datetime(raw_value)
            if parsed is not None:
                return parsed

        return None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse ISO datetime from NYT API."""
        if value is None:
            return None

        raw_value = str(value).strip()
        if not raw_value:
            return None

        normalized = raw_value.replace("Z", "+00:00")

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            logger.warning("Failed to parse NYTimes datetime '{}'.", raw_value)
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)

        return parsed