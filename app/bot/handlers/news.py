from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.factory import NewsSourceCallback
from app.bot.keyboards.inline import build_news_sources_keyboard
from app.db.repositories.headline import HeadlineRepository, SourceRepository
from app.db.repositories.user import UserRepository
from app.utils.formatting import (
    format_mixed_headlines_block,
    format_source_headlines_block,
    split_message_chunks,
)

router = Router(name="news")


async def _safe_answer_callback(callback: CallbackQuery, text: str | None = None) -> None:
    """Answer callback query safely to stop Telegram client spinner quickly."""
    try:
        await callback.answer(text=text)
    except TelegramBadRequest as error:
        logger.warning("Failed to answer news callback query: {}", error)


async def _safe_edit_message_text(
    message: Message,
    text: str,
    reply_markup=None,
    disable_web_page_preview: bool | None = None,
) -> None:
    """Edit message text safely and ignore 'message is not modified' errors."""
    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
    except TelegramBadRequest as error:
        if "message is not modified" in str(error).lower():
            logger.debug("Skipped news message edit because content was not modified.")
            return
        raise


@router.message(Command("news"))
async def news_command(message: Message, session: AsyncSession) -> None:
    """Handle /news command."""
    if message.from_user is None:
        return

    user_repository = UserRepository(session)
    source_repository = SourceRepository(session)
    headline_repository = HeadlineRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    if user.default_source_id is None:
        sources = await source_repository.list_active_sources()
        if not sources:
            await message.answer("Сейчас нет доступных источников.")
            return

        await message.answer(
            "Выберите источник новостей:",
            reply_markup=build_news_sources_keyboard(sources),
        )
        return

    source = await source_repository.get_by_id(user.default_source_id)
    if source is None or not source.is_active:
        sources = await source_repository.list_active_sources()
        await message.answer(
            "Источник по умолчанию недоступен. Выберите другой источник:",
            reply_markup=build_news_sources_keyboard(sources),
        )
        return

    headlines = await headline_repository.get_latest_by_source(
        source_id=source.id,
        limit=user.headlines_count,
    )

    if not headlines:
        await message.answer(f"Для источника <b>{source.name}</b> пока нет новостей.")
        return

    text = format_source_headlines_block(
        source_name=source.name,
        headlines=headlines,
    )

    for chunk in split_message_chunks(text):
        await message.answer(chunk, disable_web_page_preview=True)


@router.callback_query(NewsSourceCallback.filter())
async def news_source_callback(
    callback: CallbackQuery,
    callback_data: NewsSourceCallback,
    session: AsyncSession,
) -> None:
    """Handle source selection callback for /news command."""
    if callback.message is None or callback.from_user is None:
        return

    await _safe_answer_callback(callback, "Загружаю новости...")

    user_repository = UserRepository(session)
    source_repository = SourceRepository(session)
    headline_repository = HeadlineRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )

    source = await source_repository.get_by_id(callback_data.source_id)
    if source is None or not source.is_active:
        await callback.message.answer("Источник недоступен.")
        return

    headlines = await headline_repository.get_latest_by_source(
        source_id=source.id,
        limit=user.headlines_count,
    )

    if not headlines:
        await _safe_edit_message_text(
            callback.message,
            f"Для источника <b>{source.name}</b> пока нет новостей.",
        )
        return

    text = format_source_headlines_block(
        source_name=source.name,
        headlines=headlines,
    )

    chunks = split_message_chunks(text)
    await _safe_edit_message_text(
        callback.message,
        chunks[0],
        disable_web_page_preview=True,
    )

    for extra_chunk in chunks[1:]:
        await callback.message.answer(extra_chunk, disable_web_page_preview=True)


@router.message(Command("news_all"))
async def news_all_command(message: Message, session: AsyncSession) -> None:
    """Handle /news_all command."""
    if message.from_user is None:
        return

    user_repository = UserRepository(session)
    headline_repository = HeadlineRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    total_limit = max(1, user.headlines_count * 4)
    headlines = await headline_repository.get_latest_all(limit=total_limit)

    if not headlines:
        await message.answer("Пока нет новостей ни в одном источнике.")
        return

    text = format_mixed_headlines_block(
        title="📋 <b>Все источники</b> — последние новости:",
        headlines=headlines,
    )

    for chunk in split_message_chunks(text):
        await message.answer(chunk, disable_web_page_preview=True)