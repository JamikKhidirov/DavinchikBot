from typing import Optional

from sqlalchemy import select, and_

from app.models import User, Advertisement
from app.database import async_session
from app.config import config
from aiogram.types import LabeledPrice

AD_BANNER_STARS = 200
AD_BANNER_DAYS = 30


async def buy_ad_banner(telegram_id: int, text: str, photo_id: str = None) -> Optional[Advertisement]:
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if user is None:
            return None

        ad = Advertisement(
            photo_id=photo_id,
            text=text,
            is_active=True,
        )
        session.add(ad)
        await session.commit()
        await session.refresh(ad)
        return ad


def get_ad_banner_invoice_params(telegram_id: int):
    prices = [LabeledPrice(label="📢 Рекламный баннер на 30 дней", amount=AD_BANNER_STARS)]
    return {
        "title": "📢 Рекламный баннер",
        "description": f"Ваша реклама будет показываться пользователям в течение {AD_BANNER_DAYS} дней",
        "currency": "XTR",
        "prices": prices,
        "payload": f"ad_banner_{telegram_id}",
    }


async def get_user_ads(telegram_id: int) -> list[Advertisement]:
    async with async_session() as session:
        result = await session.execute(
            select(Advertisement).order_by(Advertisement.created_at.desc())
        )
        return list(result.scalars().all())
