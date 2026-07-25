import datetime

from sqlalchemy import select, and_, or_, update
from aiogram.types import LabeledPrice

from app.models import User, Profile
from app.database import async_session
from app.config import config


PLANS = {
    "1m": {"stars": config.premium_1m_stars, "days": 30, "label": "1 месяц"},
    "3m": {"stars": config.premium_3m_stars, "days": 90, "label": "3 месяца"},
    "lifetime": {"stars": config.premium_lifetime_stars, "days": 36500, "label": "Навсегда"},
}


def get_invoice_params(plan_id: str, user_id: int):
    plan = PLANS.get(plan_id)
    if not plan:
        return None
    prices = [LabeledPrice(label=f"Премиум {plan['label']}", amount=plan["stars"])]
    return {
        "title": "⭐ Премиум-доступ",
        "description": f"Премиум на {plan['label']}\n\n"
                       "💎 Безлимитные лайки\n"
                       "🚀 Буст анкеты\n"
                       "👀 Смотреть кто лайкнул\n"
                       "🎨 Приоритетная поддержка",
        "currency": "XTR",
        "prices": prices,
        "payload": f"premium_{plan_id}_{user_id}",
    }


def get_boost_invoice_params(user_id: int):
    prices = [LabeledPrice(label="🚀 Буст анкеты на 7 дней", amount=config.boost_stars)]
    return {
        "title": "🚀 Буст анкеты",
        "description": "Ваша анкета будет показываться одной из первых в течение 7 дней",
        "currency": "XTR",
        "prices": prices,
        "payload": f"boost_{user_id}",
    }


async def activate_premium(telegram_id: int, plan_id: str) -> bool:
    plan = PLANS.get(plan_id)
    if not plan:
        return False

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False

        now = datetime.datetime.utcnow()
        if user.is_premium and user.premium_expires_at and user.premium_expires_at > now:
            user.premium_expires_at += datetime.timedelta(days=plan["days"])
        else:
            user.is_premium = True
            user.premium_expires_at = now + datetime.timedelta(days=plan["days"])

        await session.commit()
        return True


async def activate_boost(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(User).where(User.telegram_id == telegram_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return False

        now = datetime.datetime.utcnow()
        if profile.is_boosted and profile.boost_expires_at and profile.boost_expires_at > now:
            profile.boost_expires_at += datetime.timedelta(days=7)
        else:
            profile.is_boosted = True
            profile.boost_expires_at = now + datetime.timedelta(days=7)

        await session.commit()
        return True


async def check_premium_expired():
    now = datetime.datetime.utcnow()
    async with async_session() as session:
        result = await session.execute(
            select(User).where(and_(User.is_premium == True, User.premium_expires_at < now))
        )
        expired = result.scalars().all()
        for u in expired:
            u.is_premium = False
            u.premium_expires_at = None
        await session.commit()
        return len(expired)


async def check_boost_expired():
    now = datetime.datetime.utcnow()
    async with async_session() as session:
        result = await session.execute(
            select(Profile).where(and_(Profile.is_boosted == True, Profile.boost_expires_at < now))
        )
        expired = result.scalars().all()
        for p in expired:
            p.is_boosted = False
            p.boost_expires_at = None
        await session.commit()
        return len(expired)


async def can_boost(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(User).where(User.telegram_id == telegram_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return False
        if profile.is_boosted and profile.boost_expires_at:
            return profile.boost_expires_at < datetime.datetime.utcnow()
        return True
