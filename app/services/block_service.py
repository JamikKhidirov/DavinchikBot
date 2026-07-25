from typing import Optional

from sqlalchemy import select, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Block
from app.database import async_session


async def block_user(telegram_id: int, target_user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False

        if user.id == target_user_id:
            return False

        existing = await session.execute(
            select(Block).where(
                and_(Block.user_id == user.id, Block.blocked_user_id == target_user_id)
            )
        )
        if existing.scalar_one_or_none():
            return True

        block = Block(user_id=user.id, blocked_user_id=target_user_id)
        session.add(block)

        from app.models import Like, Match
        await session.execute(
            delete(Like).where(
                or_(
                    and_(Like.from_user_id == user.id, Like.to_user_id == target_user_id),
                    and_(Like.from_user_id == target_user_id, Like.to_user_id == user.id),
                )
            )
        )
        u1, u2 = min(user.id, target_user_id), max(user.id, target_user_id)
        await session.execute(
            delete(Match).where(and_(Match.user1_id == u1, Match.user2_id == u2))
        )

        await session.commit()
        return True


async def unblock_user(telegram_id: int, target_user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False

        await session.execute(
            delete(Block).where(
                and_(Block.user_id == user.id, Block.blocked_user_id == target_user_id)
            )
        )
        await session.commit()
        return True


async def get_blocked_users(telegram_id: int) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return []

        blocked = await session.execute(
            select(Block).where(Block.user_id == user.id)
        )
        blocked_list = []
        for b in blocked.scalars().all():
            bu = await session.execute(select(User).where(User.id == b.blocked_user_id))
            bu = bu.scalar_one_or_none()
            if bu:
                blocked_list.append({"id": bu.id, "telegram_id": bu.telegram_id, "name": bu.first_name or str(bu.telegram_id)})
        return blocked_list


async def is_blocked(user_id: int, target_user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Block).where(
                or_(
                    and_(Block.user_id == user_id, Block.blocked_user_id == target_user_id),
                    and_(Block.user_id == target_user_id, Block.blocked_user_id == user_id),
                )
            )
        )
        return result.scalar_one_or_none() is not None
