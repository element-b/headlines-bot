from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository

router = Router(name="start")


START_TEXT = (
    "👋 <b>Headlines Bot</b>\n\n"
    "Я собираю новостные заголовки из нескольких источников, сохраняю их в базу данных "
    "и помогаю получать свежие новости в двух режимах:\n\n"
    "• <b>по запросу</b> — команды /news и /news_all\n"
    "• <b>по подписке</b> — автоматические уведомления о новых заголовках\n\n"
    "Что можно сделать:\n"
    "• выбрать источник по умолчанию\n"
    "• настроить количество заголовков\n"
    "• подписаться на один или несколько источников\n"
    "• получать только новые новости после подписки\n\n"
    "Быстрый старт:\n"
    "1. Открой /settings\n"
    "2. Выбери источник по умолчанию\n"
    "3. Запроси новости через /news\n"
    "4. При желании включи подписки через /subscribe\n\n"
    "Дополнительно:\n"
    "• /help — список команд\n"
    "• /faq — как работает бот"
)


HELP_TEXT = (
    "📘 <b>Список команд</b>\n\n"
    "/start — запуск бота и краткое описание\n"
    "/help — список доступных команд\n"
    "/faq — краткое объяснение логики бота\n\n"
    "/news — последние новости из источника по умолчанию "
    "или выбор источника, если он ещё не задан\n"
    "/news_all — последние новости из всех доступных источников\n\n"
    "/settings — выбор источника по умолчанию и количества заголовков\n\n"
    "/subscribe — подписаться на один или несколько источников\n"
    "/mysubs — посмотреть активные подписки\n"
    "/unsubscribe — отключить подписку\n\n"
    "Если хочешь сначала понять логику работы бота, открой /faq."
)


@router.message(Command("start"))
async def start_command(message: Message, session: AsyncSession) -> None:
    """Handle /start command."""
    if message.from_user is not None:
        user_repository = UserRepository(session)
        await user_repository.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )

    await message.answer(START_TEXT, disable_web_page_preview=True)


@router.message(Command("help"))
async def help_command(message: Message, session: AsyncSession) -> None:
    """Handle /help command."""
    if message.from_user is not None:
        user_repository = UserRepository(session)
        await user_repository.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )

    await message.answer(HELP_TEXT, disable_web_page_preview=True)