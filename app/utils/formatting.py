from __future__ import annotations

from collections.abc import Sequence
from html import escape
from urllib.parse import urlparse

from app.db.models import Headline

TELEGRAM_MESSAGE_LIMIT = 2000


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    return urlparse(url).netloc or url


def format_headline_item(headline: Headline, include_source: bool = False) -> str:
    """Format a single headline for Telegram HTML mode."""
    title = escape(headline.title)
    domain = escape(extract_domain(headline.url))
    url = escape(headline.url, quote=True)

    if include_source:
        source_name = escape(headline.source.name)
        return (
            f"📰 <b>{source_name}</b>: {title}\n"
            f'<a href="{url}">{domain}</a>'
        )

    return (
        f"📰 {title}\n"
        f'<a href="{url}">{domain}</a>'
    )


def format_source_headlines_block(source_name: str, headlines: Sequence[Headline]) -> str:
    """Format headlines for a single source."""
    header = f"📋 <b>{escape(source_name)}</b> — последние {len(headlines)} новостей:"
    items = [format_headline_item(headline) for headline in headlines]
    return header + "\n\n" + "\n\n".join(items)


def format_mixed_headlines_block(title: str, headlines: Sequence[Headline]) -> str:
    """Format mixed headlines from multiple sources."""
    items = [format_headline_item(headline, include_source=True) for headline in headlines]
    return title + "\n\n" + "\n\n".join(items)


def format_notification_block(headlines: Sequence[Headline]) -> str:
    """Format notification message block."""
    header = "🔔 <b>Новые новости по вашим подпискам</b>:"
    items = [format_headline_item(headline, include_source=True) for headline in headlines]
    return header + "\n\n" + "\n\n".join(items)


def split_message_chunks(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split long Telegram message into chunks preserving paragraph boundaries."""
    if len(text) <= limit:
        return [text]

    parts = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = part if not current else f"{current}\n\n{part}"

        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(part) <= limit:
            current = part
            continue

        start = 0
        while start < len(part):
            end = start + limit
            chunks.append(part[start:end])
            start = end

        current = ""

    if current:
        chunks.append(current)

    return chunks