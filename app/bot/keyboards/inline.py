from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks.factory import (
    NewsSourceCallback,
    SettingsCountCallback,
    SettingsSourceCallback,
    SubscribeCallback,
    UnsubscribeCallback,
)
from app.db.models import Source, Subscription


def build_news_sources_keyboard(sources: list[Source]) -> InlineKeyboardMarkup:
    """Build source selection keyboard for /news command."""
    builder = InlineKeyboardBuilder()

    for source in sources:
        builder.button(
            text=source.name,
            callback_data=NewsSourceCallback(source_id=source.id),
        )

    builder.adjust(1)
    return builder.as_markup()


def build_settings_keyboard(
    sources: list[Source],
    current_default_source_id: int | None,
    current_headlines_count: int,
) -> InlineKeyboardMarkup:
    """Build settings keyboard with source and count options."""
    builder = InlineKeyboardBuilder()

    for source in sources:
        prefix = "✅ " if source.id == current_default_source_id else ""
        builder.button(
            text=f"{prefix}{source.name}",
            callback_data=SettingsSourceCallback(source_id=source.id),
        )

    builder.adjust(1)

    counts = [3, 5, 10, 15]
    for count in counts:
        prefix = "✅ " if count == current_headlines_count else ""
        builder.button(
            text=f"{prefix}{count}",
            callback_data=SettingsCountCallback(count=count),
        )

    builder.adjust(1, 1, 1, 1, 4)
    return builder.as_markup()


def build_subscribe_keyboard(
    sources: list[Source],
    active_source_ids: set[int],
) -> InlineKeyboardMarkup:
    """Build subscription keyboard."""
    builder = InlineKeyboardBuilder()

    for source in sources:
        prefix = "✅ " if source.id in active_source_ids else ""
        builder.button(
            text=f"{prefix}{source.name}",
            callback_data=SubscribeCallback(source_id=source.id),
        )

    builder.adjust(1)
    return builder.as_markup()


def build_unsubscribe_keyboard(subscriptions: list[Subscription]) -> InlineKeyboardMarkup:
    """Build unsubscribe keyboard for active subscriptions."""
    builder = InlineKeyboardBuilder()

    for subscription in subscriptions:
        builder.button(
            text=f"❌ {subscription.source.name}",
            callback_data=UnsubscribeCallback(source_id=subscription.source_id),
        )

    builder.adjust(1)
    return builder.as_markup()