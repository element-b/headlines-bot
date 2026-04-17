from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.factory import SettingsCountCallback, SettingsSourceCallback
from app.bot.keyboards.inline import build_settings_keyboard
from app.db.models import User
from app.db.repositories.headline import SourceRepository
from app.db.repositories.user import UserRepository

router = Router(name="settings")


async def _safe_answer_callback(callback: CallbackQuery, text: str | None = None) -> None:
    """Answer callback query safely to stop Telegram client spinner quickly."""
    try:
        await callback.answer(text=text)
    except TelegramBadRequest as error:
        logger.warning("Failed to answer settings callback query: {}", error)


async def _safe_edit_message_text(
    message: Message,
    text: str,
    reply_markup=None,
) -> None:
    """Edit message text safely and ignore 'message is not modified' errors."""
    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as error:
        if "message is not modified" in str(error).lower():
            logger.debug("Skipped settings message edit because content was not modified.")
            return
        raise


@router.message(Command("settings"))
async def settings_command(message: Message, session: AsyncSession) -> None:
    """Handle /settings command."""
    if message.from_user is None:
        return

    user_repository = UserRepository(session)
    source_repository = SourceRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    sources = await source_repository.list_active_sources()

    await message.answer(
        text=_build_settings_text(user=user, sources=sources),
        reply_markup=build_settings_keyboard(
            sources=sources,
            current_default_source_id=user.default_source_id,
            current_headlines_count=user.headlines_count,
        ),
    )


@router.callback_query(SettingsSourceCallback.filter())
async def settings_source_callback(
    callback: CallbackQuery,
    callback_data: SettingsSourceCallback,
    session: AsyncSession,
) -> None:
    """Handle default source selection in settings."""
    if callback.message is None or callback.from_user is None:
        return

    await _safe_answer_callback(callback, "Обновляю настройки...")

    user_repository = UserRepository(session)
    source_repository = SourceRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    source = await source_repository.get_by_id(callback_data.source_id)

    if source is None or not source.is_active:
        await callback.message.answer("Источник недоступен.")
        return

    updated_user = await user_repository.set_default_source(user_id=user.id, source_id=source.id)
    sources = await source_repository.list_active_sources()

    if updated_user is None:
        await callback.message.answer("Не удалось обновить настройки.")
        return

    await _safe_edit_message_text(
        callback.message,
        text=_build_settings_text(user=updated_user, sources=sources),
        reply_markup=build_settings_keyboard(
            sources=sources,
            current_default_source_id=updated_user.default_source_id,
            current_headlines_count=updated_user.headlines_count,
        ),
    )


@router.callback_query(SettingsCountCallback.filter())
async def settings_count_callback(
    callback: CallbackQuery,
    callback_data: SettingsCountCallback,
    session: AsyncSession,
) -> None:
    """Handle headlines count selection in settings."""
    if callback.message is None or callback.from_user is None:
        return

    await _safe_answer_callback(callback, "Обновляю настройки...")

    user_repository = UserRepository(session)
    source_repository = SourceRepository(session)

    if not 1 <= callback_data.count <= 20:
        await callback.message.answer("Некорректное значение.")
        return

    user = await user_repository.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    updated_user = await user_repository.set_headlines_count(
        user_id=user.id,
        count=callback_data.count,
    )
    sources = await source_repository.list_active_sources()

    if updated_user is None:
        await callback.message.answer("Не удалось обновить настройки.")
        return

    await _safe_edit_message_text(
        callback.message,
        text=_build_settings_text(user=updated_user, sources=sources),
        reply_markup=build_settings_keyboard(
            sources=sources,
            current_default_source_id=updated_user.default_source_id,
            current_headlines_count=updated_user.headlines_count,
        ),
    )


def _build_settings_text(user: User, sources: list) -> str:
    """Build settings message text."""
    default_source_name = "не выбран"
    for source in sources:
        if source.id == user.default_source_id:
            default_source_name = source.name
            break

    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"Источник по умолчанию: <b>{default_source_name}</b>\n"
        f"Количество заголовков: <b>{user.headlines_count}</b>\n\n"
        "Выберите источник по умолчанию и число заголовков:"
    )