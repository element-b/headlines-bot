from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Subscription


class SubscriptionRepository:
    """Repository for subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_and_source(self, user_id: int, source_id: int) -> Subscription | None:
        """Return subscription by user and source."""
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.source_id == source_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def subscribe(self, user_id: int, source_id: int) -> tuple[Subscription, bool]:
        """Create or reactivate subscription.

        Returns:
            Tuple of subscription and flag indicating whether it was newly activated.
        """
        subscription = await self.get_by_user_and_source(user_id=user_id, source_id=source_id)

        if subscription is None:
            subscription = Subscription(
                user_id=user_id,
                source_id=source_id,
                is_active=True,
            )
            self.session.add(subscription)
            await self.session.commit()
            await self.session.refresh(subscription)
            return subscription, True

        if subscription.is_active:
            return subscription, False

        subscription.is_active = True
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription, True

    async def unsubscribe(self, user_id: int, source_id: int) -> bool:
        """Deactivate subscription."""
        subscription = await self.get_by_user_and_source(user_id=user_id, source_id=source_id)
        if subscription is None:
            return False

        if not subscription.is_active:
            return False

        subscription.is_active = False
        await self.session.commit()
        return True

    async def list_active_by_user(self, user_id: int) -> list[Subscription]:
        """Return active subscriptions for a user."""
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.source))
            .where(
                Subscription.user_id == user_id,
                Subscription.is_active.is_(True),
            )
            .order_by(Subscription.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_source_ids_by_user(self, user_id: int) -> list[int]:
        """Return active source IDs for a user."""
        stmt = select(Subscription.source_id).where(
            Subscription.user_id == user_id,
            Subscription.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_active(self) -> list[Subscription]:
        """Return all active subscriptions with loaded user and source."""
        stmt = (
            select(Subscription)
            .options(
                joinedload(Subscription.user),
                joinedload(Subscription.source),
            )
            .where(Subscription.is_active.is_(True))
            .order_by(Subscription.user_id.asc(), Subscription.source_id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())