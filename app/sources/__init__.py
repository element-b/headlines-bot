from __future__ import annotations

from app.sources.base import BaseSource, HeadlineData
from app.sources.guardian import GuardianSource
from app.sources.nytimes import NewYorkTimesSource
from app.sources.registry import (
    DEFAULT_SOURCE_DEFINITIONS,
    LEGACY_DISABLED_SOURCE_SLUGS,
    SourceDefinition,
    build_sources_registry,
)
from app.sources.rss_source import RssSource

__all__ = [
    "BaseSource",
    "HeadlineData",
    "GuardianSource",
    "NewYorkTimesSource",
    "RssSource",
    "SourceDefinition",
    "DEFAULT_SOURCE_DEFINITIONS",
    "LEGACY_DISABLED_SOURCE_SLUGS",
    "build_sources_registry",
]