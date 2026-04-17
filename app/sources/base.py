from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import aiohttp


@dataclass(frozen=True, slots=True)
class HeadlineData:
    """DTO for scraped or parsed headline data."""

    title: str
    url: str
    published_at: datetime | None


class BaseSource(ABC):
    """Abstract base class for all news sources."""

    name: str
    slug: str
    url: str
    source_type: str

    def __init__(self, session: aiohttp.ClientSession, timeout_seconds: int = 15) -> None:
        self.session = session
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def fetch(self) -> list[HeadlineData]:
        """Fetch list of headlines from the source."""
        raise NotImplementedError

    def build_timeout(self) -> aiohttp.ClientTimeout:
        """Build aiohttp timeout."""
        return aiohttp.ClientTimeout(total=self.timeout_seconds)

    def make_absolute_url(self, raw_url: str) -> str:
        """Convert relative URL to absolute and normalize it."""
        absolute_url = urljoin(self.url, raw_url.strip())
        return self.normalize_url(absolute_url)

    def normalize_url(self, raw_url: str) -> str:
        """Normalize URL by removing query string and fragment."""
        parts = urlsplit(raw_url.strip())
        normalized = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        return normalized

    def deduplicate(self, headlines: list[HeadlineData]) -> list[HeadlineData]:
        """Remove duplicates and empty items."""
        seen_urls: set[str] = set()
        result: list[HeadlineData] = []

        for item in headlines:
            title = " ".join(item.title.split()).strip()
            url = self.normalize_url(item.url)

            if not title:
                continue

            if not url.startswith("http://") and not url.startswith("https://"):
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)
            result.append(
                HeadlineData(
                    title=title,
                    url=url,
                    published_at=item.published_at,
                )
            )

        return result