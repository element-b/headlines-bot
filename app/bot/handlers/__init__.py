from __future__ import annotations

from app.bot.handlers.faq import router as faq_router
from app.bot.handlers.news import router as news_router
from app.bot.handlers.settings import router as settings_router
from app.bot.handlers.start import router as start_router
from app.bot.handlers.subscriptions import router as subscriptions_router

__all__ = [
    "start_router",
    "faq_router",
    "news_router",
    "settings_router",
    "subscriptions_router",
]