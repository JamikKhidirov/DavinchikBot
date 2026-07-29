import datetime
from typing import Optional

from sqlalchemy import select, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Profile, Like, Match, Message
from app.database import async_session

UTC = datetime.timezone.utc


async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(telegram_id=telegram_id, username=username, first_name=first_name, last_name=last_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            if username or first_name or last_name:
                user.username = username or user.username
                user.first_name = first_name or user.first_name
                user.last_name = last_name or user.last_name
            await session.commit()

    return user


async def has_profile(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return False
        result = await session.execute(
            select(Profile).where(Profile.user_id == user.id)
        )
        return result.scalar_one_or_none() is not None


async def create_profile(
    telegram_id: int,
    name: str,
    age: int,
    gender: str,
    looking_for: str,
    city: str,
    bio: str,
    photos: list,
    videos: list = None,
    interests: list = None,
    age_min: int = 18,
    age_max: int = 99,
) -> Profile:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError("User not found")

        profile = Profile(
            user_id=user.id,
            name=name,
            age=age,
            gender=gender,
            looking_for=looking_for,
            city=city,
            bio=bio,
            photos=photos,
            videos=videos or [],
            interests=interests or [],
            age_min_preference=age_min,
            age_max_preference=age_max,
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        return profile


async def get_profile_by_telegram_id(telegram_id: int) -> Optional[Profile]:
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def update_profile(telegram_id: int, **kwargs) -> Optional[Profile]:
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(User).where(User.telegram_id == telegram_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return None

        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        await session.commit()
        await session.refresh(profile)
        return profile


async def get_user_by_id(user_id: int) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def set_admin(telegram_id: int, admin: bool = True) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.is_admin = admin
        await session.commit()
        return True


async def is_admin(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        return user.is_admin


async def ban_user(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.is_banned = True
        await session.commit()
        return True


async def unban_user(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.is_banned = False
        await session.commit()
        return True


async def get_all_users() -> list[User]:
    async with async_session() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        return list(result.scalars().all())


async def is_banned(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        return user.is_banned


async def update_last_active(telegram_id: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.last_active_at = datetime.datetime.now(UTC)
            await session.commit()


async def get_profile_stats(telegram_id: int) -> dict:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return {}

        profile = await session.execute(select(Profile).where(Profile.user_id == user.id))
        profile = profile.scalar_one_or_none()
        if profile is None:
            return {}

        from sqlalchemy import func

        likes_received = (
            await session.execute(
                select(func.count(Like.id)).where(and_(Like.to_user_id == user.id, Like.is_like == True))
            )
        ).scalar() or 0

        likes_given = (
            await session.execute(select(func.count(Like.id)).where(and_(Like.from_user_id == user.id, Like.is_like == True)))
        ).scalar() or 0

        matches_count = (
            await session.execute(
                select(func.count(Match.id)).where(or_(Match.user1_id == user.id, Match.user2_id == user.id))
            )
        ).scalar() or 0

        return {
            "views": profile.views_count or 0,
            "likes_received": likes_received,
            "likes_given": likes_given,
            "matches": matches_count,
            "is_verified": profile.is_verified,
        }


async def request_verification(telegram_id: int, photo_id: str) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(User).where(User.telegram_id == telegram_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return False
        profile.verification_photo_id = photo_id
        await session.commit()
        return True


async def get_pending_verifications() -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(Profile)
            .where(and_(Profile.verification_photo_id.isnot(None), Profile.is_verified == False))
            .order_by(Profile.updated_at.desc())
        )
        profiles = result.scalars().all()
        data = []
        for p in profiles:
            u = await session.execute(select(User).where(User.id == p.user_id))
            u = u.scalar_one_or_none()
            if u:
                data.append({
                    "profile_id": p.id,
                    "user_id": u.id,
                    "telegram_id": u.telegram_id,
                    "name": p.name,
                    "photo_id": p.verification_photo_id,
                })
        return data


async def verify_profile(profile_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(Profile).where(Profile.id == profile_id))
        p = result.scalar_one_or_none()
        if p is None:
            return False
        p.is_verified = True
        p.verification_photo_id = None
        await session.commit()
        return True


async def reject_verification(profile_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(Profile).where(Profile.id == profile_id))
        p = result.scalar_one_or_none()
        if p is None:
            return False
        p.verification_photo_id = None
        await session.commit()
        return True


async def deactivate_inactive_profiles():
    from app.config import config

    cutoff = datetime.datetime.now(UTC) - datetime.timedelta(days=config.inactive_days_before_hide)
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(User).where(
                and_(
                    Profile.is_active == True,
                    or_(
                        User.last_active_at.is_(None),
                        User.last_active_at < cutoff,
                    ),
                )
            )
        )
        profiles = result.scalars().all()
        count = 0
        for p in profiles:
            p.is_active = False
            count += 1
        await session.commit()
        return count


async def increment_profile_views(owner_telegram_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(User).where(User.telegram_id == owner_telegram_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            profile.views_count = (profile.views_count or 0) + 1
            await session.commit()


async def delete_profile(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False

        result = await session.execute(select(Profile).where(Profile.user_id == user.id))
        profile = result.scalar_one_or_none()
        if profile:
            await session.delete(profile)

        match_rows = await session.execute(
            select(Match.id).where(or_(Match.user1_id == user.id, Match.user2_id == user.id))
        )
        match_ids = [row[0] for row in match_rows]

        if match_ids:
            await session.execute(delete(Message).where(Message.match_id.in_(match_ids)))
        await session.execute(
            delete(Match).where(or_(Match.user1_id == user.id, Match.user2_id == user.id))
        )
        await session.execute(
            delete(Like).where(or_(Like.from_user_id == user.id, Like.to_user_id == user.id))
        )

        await session.commit()
        return True
