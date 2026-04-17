from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonCommands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.handlers.faq import router as faq_router
from app.bot.handlers.news import router as news_router
from app.bot.handlers.settings import router as settings_router
from app.bot.handlers.start import router as start_router
from app.bot.handlers.subscriptions import router as subscriptions_router
from app.bot.middlewares.db import DatabaseSessionMiddleware
from app.config import Settings


def create_bot(settings: Settings) -> Bot:
    """Create configured aiogram Bot instance."""
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(session_factory: async_sessionmaker[AsyncSession]) -> Dispatcher:
    """Create configured aiogram Dispatcher instance."""
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(DatabaseSessionMiddleware(session_factory))

    dispatcher.include_router(start_router)
    dispatcher.include_router(faq_router)
    dispatcher.include_router(news_router)
    dispatcher.include_router(settings_router)
    dispatcher.include_router(subscriptions_router)

    return dispatcher


async def set_main_menu(bot: Bot) -> None:
    """Set Telegram bot command menu."""
    commands = [
        BotCommand(command="start", description="Запуск бота и краткое описание"),
        BotCommand(command="help", description="Список доступных команд"),
        BotCommand(command="faq", description="Как работает бот"),
        BotCommand(command="news", description="Новости из источника по умолчанию"),
        BotCommand(command="news_all", description="Новости из всех источников"),
        BotCommand(command="settings", description="Настройки источника и количества"),
        BotCommand(command="subscribe", description="Подписаться на источники"),
        BotCommand(command="unsubscribe", description="Отменить подписку"),
        BotCommand(command="mysubs", description="Мои активные подписки"),
    ]

    await bot.set_my_commands(commands)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())