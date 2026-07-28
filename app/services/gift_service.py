from typing import Optional

from sqlalchemy import select, or_
from aiogram.types import LabeledPrice

from app.models import User, Gift, Match
from app.config import config
from app.database import async_session
from app.models.gift import GIFT_OPTIONS


async def send_gift(from_telegram_id: int, to_user_id: int, gift_type: str, message: str = None) -> Optional[Gift]:
    gift_info = GIFT_OPTIONS.get(gift_type)
    if gift_info is None:
        return None

    async with async_session() as session:
        from_user = await session.execute(select(User).where(User.telegram_id == from_telegram_id))
        from_user = from_user.scalar_one_or_none()
        if from_user is None:
            return None

        to_user = await session.execute(select(User).where(User.id == to_user_id))
        to_user = to_user.scalar_one_or_none()
        if to_user is None:
            return None

        gift = Gift(
            from_user_id=from_user.id,
            to_user_id=to_user.id,
            gift_type=gift_type,
            message=message,
            stars_cost=gift_info["stars"],
        )
        session.add(gift)
        await session.commit()
        await session.refresh(gift)
        return gift


def get_gift_invoice_params(gift_type: str, from_telegram_id: int, to_user_id: int, message: str = None):
    gift_info = GIFT_OPTIONS.get(gift_type)
    if gift_info is None:
        return None
    prices = [LabeledPrice(label=gift_info["label"], amount=gift_info["stars"])]
    return {
        "title": f"🎁 Подарок: {gift_info['label']}",
        "description": f"Отправка подарка пользователю\n\n{gift_info['label']}",
        "currency": "XTR",
        "prices": prices,
        "payload": f"gift_{gift_type}_{from_telegram_id}_{to_user_id}_{message or ''}",
    }


async def get_received_gifts(telegram_id: int) -> list[dict]:
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if user is None:
            return []

        result = await session.execute(
            select(Gift).where(Gift.to_user_id == user.id).order_by(Gift.created_at.desc())
        )
        gifts = []
        for g in result.scalars().all():
            sender = await session.execute(select(User).where(User.id == g.from_user_id))
            sender = sender.scalar_one_or_none()
            gift_info = GIFT_OPTIONS.get(g.gift_type, {})
            gifts.append({
                "id": g.id,
                "gift_type": g.gift_type,
                "label": gift_info.get("label", g.gift_type),
                "message": g.message,
                "from_name": sender.first_name or sender.username or f"user#{g.from_user_id}" if sender else "—",
                "created_at": g.created_at.isoformat() if g.created_at else "",
            })
        return gifts
