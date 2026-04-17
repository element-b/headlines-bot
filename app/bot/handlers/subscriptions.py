from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks.factory import SubscribeCallback, UnsubscribeCallback
from app.bot.keyboards.inline import build_subscribe_keyboard, build_unsubscribe_keyboard
from app.db.models import Headline, SentHeadline, Subscription
from app.db.repositories.headline import SourceRepository
from app.db.repositories.subscription import SubscriptionRepository
from app.db.repositories.user import UserRepository

router = Router(name="subscriptions")


async def _safe_answer_callback(callback: CallbackQuery, text: str | None = None) -> None:
    """Answer callback query safely to stop Telegram client spinner quickly."""
    try:
        await callback.answer(text=text)
    except TelegramBadRequest as error:
        logger.warning("Failed to answer subscriptions callback query: {}", error)


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
            logger.debug("Skipped subscriptions message edit because content was not modified.")
            return
        raise


async def _mark_existing_headlines_as_sent(
    session: AsyncSession,
    user_id: int,
    source_id: int,
) -> None:
    """Mark all current headlines of the source as already sent for the user."""
    stmt = (
        insert(SentHeadline)
        .from_select(
            ["user_id", "headline_id"],
            select(
                literal(user_id),
                Headline.id,
            ).where(Headline.source_id == source_id),
        )
        .on_conflict_do_nothing(index_elements=["user_id", "headline_id"])
    )
    await session.execute(stmt)


@router.message(Command("subscribe"))
async def subscribe_command(message: Message, session: AsyncSession) -> None:
    """Handle /subscribe command."""
    if message.from_user is None:
        return

    user_repository = UserRepository(session)
    source_repository = SourceRepository(session)
    subscription_repository = SubscriptionRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    sources = await source_repository.list_active_sources()
    active_source_ids = set(await subscription_repository.get_active_source_ids_by_user(user.id))

    await message.answer(
        "Выберите источники для подписки:",
        reply_markup=build_subscribe_keyboard(
            sources=sources,
            active_source_ids=active_source_ids,
        ),
    )


@router.callback_query(SubscribeCallback.filter())
async def subscribe_callback(
    callback: CallbackQuery,
    callback_data: SubscribeCallback,
    session: AsyncSession,
) -> None:
    """Handle subscribe callback."""
    if callback.message is None or callback.from_user is None:
        return

    await _safe_answer_callback(callback, "Обрабатываю подписку...")

    user_repository = UserRepository(session)
    source_repository = SourceRepository(session)
    subscription_repository = SubscriptionRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    source = await source_repository.get_by_id(callback_data.source_id)

    if source is None or not source.is_active:
        await callback.message.answer("Источник недоступен.")
        return

    existing_active_subscription_id = await session.scalar(
        select(Subscription.id).where(
            Subscription.user_id == user.id,
            Subscription.source_id == source.id,
            Subscription.is_active.is_(True),
        )
    )

    activated = existing_active_subscription_id is None

    if activated:
        upsert_subscription_stmt = (
            insert(Subscription)
            .values(
                user_id=user.id,
                source_id=source.id,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "source_id"],
                set_={"is_active": True},
            )
        )
        await session.execute(upsert_subscription_stmt)

        await _mark_existing_headlines_as_sent(
            session=session,
            user_id=user.id,
            source_id=source.id,
        )

        await session.commit()

    sources = await source_repository.list_active_sources()
    active_source_ids = set(await subscription_repository.get_active_source_ids_by_user(user.id))

    await _safe_edit_message_text(
        callback.message,
        "Выберите источники для подписки:",
        reply_markup=build_subscribe_keyboard(
            sources=sources,
            active_source_ids=active_source_ids,
        ),
    )


@router.message(Command("unsubscribe"))
async def unsubscribe_command(message: Message, session: AsyncSession) -> None:
    """Handle /unsubscribe command."""
    if message.from_user is None:
        return

    user_repository = UserRepository(session)
    subscription_repository = SubscriptionRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    subscriptions = await subscription_repository.list_active_by_user(user.id)

    if not subscriptions:
        await message.answer("У вас нет активных подписок.")
        return

    await message.answer(
        "Выберите подписку для отмены:",
        reply_markup=build_unsubscribe_keyboard(subscriptions),
    )


@router.callback_query(UnsubscribeCallback.filter())
async def unsubscribe_callback(
    callback: CallbackQuery,
    callback_data: UnsubscribeCallback,
    session: AsyncSession,
) -> None:
    """Handle unsubscribe callback."""
    if callback.message is None or callback.from_user is None:
        return

    await _safe_answer_callback(callback, "Отменяю подписку...")

    user_repository = UserRepository(session)
    source_repository = SourceRepository(session)
    subscription_repository = SubscriptionRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    source = await source_repository.get_by_id(callback_data.source_id)

    if source is None:
        await callback.message.answer("Источник не найден.")
        return

    removed = await subscription_repository.unsubscribe(user_id=user.id, source_id=source.id)
    subscriptions = await subscription_repository.list_active_by_user(user.id)

    if subscriptions:
        await _safe_edit_message_text(
            callback.message,
            "Выберите подписку для отмены:",
            reply_markup=build_unsubscribe_keyboard(subscriptions),
        )
    else:
        await _safe_edit_message_text(
            callback.message,
            "У вас больше нет активных подписок.",
        )

    if not removed:
        logger.info(
            "User {} tried to unsubscribe from source '{}' but subscription was already inactive.",
            user.id,
            source.slug,
        )


@router.message(Command("mysubs"))
async def mysubs_command(message: Message, session: AsyncSession) -> None:
    """Handle /mysubs command."""
    if message.from_user is None:
        return

    user_repository = UserRepository(session)
    subscription_repository = SubscriptionRepository(session)

    user = await user_repository.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    subscriptions = await subscription_repository.list_active_by_user(user.id)

    if not subscriptions:
        await message.answer("У вас нет активных подписок.")
        return

    lines = ["🔔 <b>Ваши активные подписки</b>:\n"]
    for subscription in subscriptions:
        lines.append(f"• {subscription.source.name}")

    await message.answer("\n".join(lines))