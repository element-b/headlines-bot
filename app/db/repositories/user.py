from __future__ import annotations

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User


class UserRepository:
    """Repository for user-related database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Return user by Telegram ID."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        """Return user by internal ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> User:
        """Get existing user or create a new one using a single upsert statement."""
        insert_stmt = insert(User).values(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            headlines_count=self.settings.default_headlines_count,
        )

        valid_headlines_count_expr = case(
            (
                User.headlines_count.between(1, 20),
                User.headlines_count,
            ),
            else_=self.settings.default_headlines_count,
        )

        upsert_stmt = (
            insert_stmt.on_conflict_do_update(
                index_elements=[User.telegram_id],
                set_={
                    "username": insert_stmt.excluded.username,
                    "first_name": insert_stmt.excluded.first_name,
                    "headlines_count": valid_headlines_count_expr,
                    "updated_at": func.now(),
                },
            )
            .returning(User)
        )

        orm_stmt = (
            select(User)
            .from_statement(upsert_stmt)
            .execution_options(populate_existing=True)
        )

        result = await self.session.execute(orm_stmt)
        user = result.scalar_one()

        await self.session.commit()
        return user

    async def set_default_source(self, user_id: int, source_id: int | None) -> User | None:
        """Update user's default source using a single update statement."""
        update_stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                default_source_id=source_id,
                updated_at=func.now(),
            )
            .returning(User)
        )

        orm_stmt = (
            select(User)
            .from_statement(update_stmt)
            .execution_options(populate_existing=True)
        )

        result = await self.session.execute(orm_stmt)
        user = result.scalar_one_or_none()

        await self.session.commit()
        return user

    async def set_headlines_count(self, user_id: int, count: int) -> User | None:
        """Update user's preferred number of headlines per response."""
        if not 1 <= count <= 20:
            raise ValueError("headlines_count must be between 1 and 20.")

        update_stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                headlines_count=count,
                updated_at=func.now(),
            )
            .returning(User)
        )

        orm_stmt = (
            select(User)
            .from_statement(update_stmt)
            .execution_options(populate_existing=True)
        )

        result = await self.session.execute(orm_stmt)
        user = result.scalar_one_or_none()

        await self.session.commit()
        return user