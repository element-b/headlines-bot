from __future__ import annotations

from dataclasses import dataclass

import aiohttp

from app.config import Settings
from app.sources.base import BaseSource
from app.sources.guardian import GuardianSource
from app.sources.nytimes import NewYorkTimesSource
from app.sources.rss_source import RssSource


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    """Static source definition used for seeding and registry creation."""

    name: str
    slug: str
    url: str
    source_type: str


DEFAULT_SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        name="The Guardian",
        slug="guardian",
        url="https://www.theguardian.com",
        source_type="api",
    ),
    SourceDefinition(
        name="The New York Times",
        slug="nytimes",
        url="https://www.nytimes.com",
        source_type="api",
    ),
    SourceDefinition(
        name="Коммерсантъ",
        slug="kommersant",
        url="https://www.kommersant.ru/RSS/news.xml",
        source_type="rss",
    ),
    SourceDefinition(
        name="РБК",
        slug="rbc",
        url="https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
        source_type="rss",
    ),
)

LEGACY_DISABLED_SOURCE_SLUGS: tuple[str, ...] = (
    "bloomberg",
    "wsj",
)


def build_sources_registry(
    session: aiohttp.ClientSession,
    settings: Settings,
    timeout_seconds: int = 15,
) -> dict[str, BaseSource]:
    """Build runtime registry of source instances by slug."""
    return {
        "guardian": GuardianSource(
            session=session,
            api_key=settings.guardian_api_key,
            sections=settings.guardian_sections,
            timeout_seconds=timeout_seconds,
        ),
        "nytimes": NewYorkTimesSource(
            session=session,
            api_key=settings.nytimes_api_key,
            sections=settings.nytimes_sections,
            timeout_seconds=timeout_seconds,
        ),
        "kommersant": RssSource(
            session=session,
            name="Коммерсантъ",
            slug="kommersant",
            url="https://www.kommersant.ru/RSS/news.xml",
            timeout_seconds=timeout_seconds,
        ),
        "rbc": RssSource(
            session=session,
            name="РБК",
            slug="rbc",
            url="https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
            timeout_seconds=timeout_seconds,
        ),
    }