from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class NewsSourceCallback(CallbackData, prefix="news_source"):
    """Callback for selecting source in /news command."""

    source_id: int


class SettingsSourceCallback(CallbackData, prefix="settings_source"):
    """Callback for selecting default source in settings."""

    source_id: int


class SettingsCountCallback(CallbackData, prefix="settings_count"):
    """Callback for selecting headlines count in settings."""

    count: int


class SubscribeCallback(CallbackData, prefix="subscribe"):
    """Callback for subscribing to a source."""

    source_id: int


class UnsubscribeCallback(CallbackData, prefix="unsubscribe"):
    """Callback for unsubscribing from a source."""

    source_id: int