from __future__ import annotations

import asyncio
from collections import defaultdict

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Headline, Subscription
from app.db.repositories.headline import SentHeadlineRepository
from app.db.repositories.subscription import SubscriptionRepository
from app.utils.formatting import format_notification_block, split_message_chunks


class NotifierService:
    """Background service for sending fresh headlines to subscribers."""

    def __init__(
        self,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
        interval_seconds: int,
    ) -> None:
        self._bot = bot
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()
        self._max_headlines_per_iteration = 20

    def stop(self) -> None:
        """Request graceful stop."""
        self._stop_event.set()

    async def run(self) -> None:
        """Run notification loop until stop is requested."""
        logger.info("Notifier service started.")

        try:
            while not self._stop_event.is_set():
                await self.run_once()
                await self._sleep_until_next_iteration()
        except asyncio.CancelledError:
            logger.info("Notifier service cancelled.")
            raise
        finally:
            logger.info("Notifier service stopped.")

    async def run_once(self) -> None:
        """Execute one notification iteration."""
        async with self._session_factory() as session:
            subscription_repository = SubscriptionRepository(session)
            subscriptions = await subscription_repository.list_all_active()

        grouped_subscriptions = self._group_by_user(subscriptions)

        for user_id, user_subscriptions in grouped_subscriptions.items():
            user = user_subscriptions[0].user
            source_ids = [subscription.source_id for subscription in user_subscriptions]
            fetch_limit = self._max_headlines_per_iteration + 1

            async with self._session_factory() as session:
                sent_repository = SentHeadlineRepository(session)
                unsent_headlines = await sent_repository.get_unsent_for_user(
                    user_id=user_id,
                    source_ids=source_ids,
                    limit=fetch_limit,
                )

            if not unsent_headlines:
                continue

            has_more = len(unsent_headlines) > self._max_headlines_per_iteration
            headlines_to_send = unsent_headlines[: self._max_headlines_per_iteration]

            if has_more:
                logger.warning(
                    "User {} has more than {} unsent headlines. "
                    "Sending only {} in this iteration.",
                    user_id,
                    self._max_headlines_per_iteration,
                    self._max_headlines_per_iteration,
                )

            sent_successfully = await self._send_headlines(
                telegram_id=user.telegram_id,
                headlines=headlines_to_send,
            )

            if sent_successfully:
                async with self._session_factory() as session:
                    sent_repository = SentHeadlineRepository(session)
                    await sent_repository.mark_many_as_sent(
                        user_id=user_id,
                        headline_ids=[headline.id for headline in headlines_to_send],
                    )

            await asyncio.sleep(0.05)

    async def _send_headlines(self, telegram_id: int, headlines: list[Headline]) -> bool:
        """Send a batch of headlines to Telegram user."""
        message_text = format_notification_block(headlines)
        chunks = split_message_chunks(message_text)

        try:
            for chunk in chunks:
                await self._bot.send_message(
                    chat_id=telegram_id,
                    text=chunk,
                    disable_web_page_preview=True,
                )
            return True

        except TelegramRetryAfter as error:
            logger.warning(
                "Telegram rate limit reached for user {}. Retry after {} seconds.",
                telegram_id,
                error.retry_after,
            )
            await asyncio.sleep(error.retry_after)

            try:
                for chunk in chunks:
                    await self._bot.send_message(
                        chat_id=telegram_id,
                        text=chunk,
                        disable_web_page_preview=True,
                    )
                return True
            except Exception:
                logger.exception("Retry after TelegramRetryAfter failed for user {}.", telegram_id)
                return False

        except TelegramForbiddenError:
            logger.warning("Bot is blocked or chat unavailable for user {}.", telegram_id)
            return False

        except TelegramBadRequest:
            logger.exception("Telegram rejected message for user {}.", telegram_id)
            return False

        except Exception:
            logger.exception("Unexpected error while sending notifications to user {}.", telegram_id)
            return False

    @staticmethod
    def _group_by_user(subscriptions: list[Subscription]) -> dict[int, list[Subscription]]:
        """Group subscriptions by user ID."""
        grouped: dict[int, list[Subscription]] = defaultdict(list)
        for subscription in subscriptions:
            grouped[subscription.user_id].append(subscription)
        return dict(grouped)

    async def _sleep_until_next_iteration(self) -> None:
        """Sleep until next loop iteration or until stop is requested."""
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
        except asyncio.TimeoutError:
            return