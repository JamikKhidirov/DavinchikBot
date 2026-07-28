import secrets

from sqlalchemy import select

from app.models import User, Referral
from app.database import async_session


async def get_or_create_referral_code(telegram_id: int) -> str:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return ""
        if not user.referral_code:
            user.referral_code = secrets.token_hex(4).upper()
            await session.commit()
        return user.referral_code


async def apply_referral(referred_telegram_id: int, code: str) -> str:
    async with async_session() as session:
        referrer = await session.execute(select(User).where(User.referral_code == code))
        referrer = referrer.scalar_one_or_none()
        if referrer is None:
            return "invalid"

        referred = await session.execute(select(User).where(User.telegram_id == referred_telegram_id))
        referred = referred.scalar_one_or_none()
        if referred is None:
            return "invalid"

        if referred.referred_by_id is not None:
            return "already"

        existing = await session.execute(
            select(Referral).where(Referral.referred_id == referred.id)
        )
        if existing.scalar_one_or_none():
            return "already"

        referral = Referral(referrer_id=referrer.id, referred_id=referred.id, bonus_given=True)
        session.add(referral)

        referrer.extra_likes = (referrer.extra_likes or 0) + 5
        referred.referred_by_id = referrer.id

        await session.commit()
        return "ok"


async def get_referral_stats(telegram_id: int) -> dict:
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if user is None:
            return {"count": 0, "bonus_likes": 0}

        referrals = await session.execute(
            select(Referral).where(Referral.referrer_id == user.id)
        )
        ref_list = list(referrals.scalars().all())

        return {
            "count": len(ref_list),
            "bonus_likes": user.extra_likes or 0,
            "code": user.referral_code or "",
        }
