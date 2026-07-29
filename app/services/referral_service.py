import secrets
import datetime

from sqlalchemy import select

from app.models import User, Referral, Profile
from app.database import async_session

REFERRER_BONUS_LIKES = 15
REFERRED_BONUS_LIKES = 10
REFERRAL_PREMIUM_TRIAL_DAYS = 7


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

        if referrer.id == referred.id:
            return "self"

        now = datetime.datetime.now(datetime.UTC)

        referral = Referral(
            referrer_id=referrer.id,
            referred_id=referred.id,
            bonus_given=True,
        )
        session.add(referral)

        referrer.extra_likes = (referrer.extra_likes or 0) + REFERRER_BONUS_LIKES
        referred.extra_likes = (referred.extra_likes or 0) + REFERRED_BONUS_LIKES
        referred.referred_by_id = referrer.id

        if not referrer.is_premium:
            existing_trial = referrer.premium_trial_expires_at
            if existing_trial and existing_trial > now:
                referrer.premium_trial_expires_at += datetime.timedelta(days=3)
            else:
                referrer.is_premium = True
                referrer.premium_trial_expires_at = now + datetime.timedelta(days=REFERRAL_PREMIUM_TRIAL_DAYS)

        referred.is_premium = True
        referred.premium_trial_expires_at = now + datetime.timedelta(days=REFERRAL_PREMIUM_TRIAL_DAYS)

        referred_profile = await session.execute(select(Profile).where(Profile.user_id == referred.id))
        referred_profile = referred_profile.scalar_one_or_none()
        if referred_profile:
            referred_profile.is_referral_badge = True
        else:
            referred.referral_bonus_claimed = True

        referrer_profile = await session.execute(select(Profile).where(Profile.user_id == referrer.id))
        referrer_profile = referrer_profile.scalar_one_or_none()
        if referrer_profile:
            referrer_profile.is_referral_badge = True

        await session.commit()
        return "ok"


async def get_referral_stats(telegram_id: int) -> dict:
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if user is None:
            return {"count": 0, "bonus_likes": 0, "code": "", "premium_trial": False}

        referrals = await session.execute(
            select(Referral).where(Referral.referrer_id == user.id)
        )
        ref_list = list(referrals.scalars().all())

        now = datetime.datetime.now(datetime.UTC)
        has_active_trial = (
            user.premium_trial_expires_at is not None
            and user.premium_trial_expires_at > now
        )

        return {
            "count": len(ref_list),
            "bonus_likes": user.extra_likes or 0,
            "code": user.referral_code or "",
            "premium_trial": has_active_trial,
            "premium_trial_days": (user.premium_trial_expires_at - now).days
            if has_active_trial and user.premium_trial_expires_at
            else 0,
        }


async def check_and_revoke_expired_trials() -> int:
    now = datetime.datetime.now(datetime.UTC)
    count = 0
    async with async_session() as session:
        expired = await session.execute(
            select(User).where(
                User.premium_trial_expires_at.isnot(None),
                User.premium_trial_expires_at < now,
                User.is_premium == True,
            )
        )
        for u in expired.scalars().all():
            if u.premium_expires_at is None or u.premium_expires_at < now:
                u.is_premium = False
            u.premium_trial_expires_at = None
            count += 1
        await session.commit()
        return count
