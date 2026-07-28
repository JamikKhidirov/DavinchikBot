from sqlalchemy import select, func
from app.database import async_session
from app.models import Payment, WithdrawalRequest

STAR_CONVERSIONS = {
    "premium_1m": {"label": "⭐ Премиум на 1 месяц", "stars": 50},
    "premium_3m": {"label": "⭐ Премиум на 3 месяца", "stars": 120},
    "premium_lifetime": {"label": "⭐ Премиум навсегда", "stars": 300},
    "boost": {"label": "🚀 Буст на 7 дней", "stars": 30},
    "likes_50": {"label": "❤️ 50 бонусных лайков", "stars": 10},
    "gift_rose": {"label": "🌹 Подарок Роза", "stars": 15},
    "gift_heart": {"label": "❤️ Подарок Сердце", "stars": 25},
    "gift_chocolate": {"label": "🍫 Подарок Шоколад", "stars": 20},
    "gift_ring": {"label": "💍 Подарок Кольцо", "stars": 100},
    "gift_cake": {"label": "🎂 Подарок Торт", "stars": 30},
    "gift_bear": {"label": "🧸 Подарок Мишка", "stars": 35},
    "ad_banner": {"label": "📢 Рекламный баннер 30 дней", "stars": 200},
}


async def get_star_balance() -> dict:
    async with async_session() as session:
        total_earned = (
            await session.execute(
                select(func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.currency == "XTR", Payment.status == "completed")
            )
        ).scalar() or 0

        total_used = (
            await session.execute(
                select(func.coalesce(func.sum(WithdrawalRequest.amount_stars), 0))
                .where(WithdrawalRequest.status.in_(["pending", "approved", "converted"]))
            )
        ).scalar() or 0

        return {
            "total_earned": int(total_earned),
            "total_used": int(total_used),
            "available": int(total_earned - total_used),
        }


async def create_withdrawal(admin_user_id: int, amount_stars: int, conversion_type: str = None, conversion_detail: str = None) -> bool:
    balance = await get_star_balance()
    if amount_stars > balance["available"]:
        return False

    async with async_session() as session:
        req = WithdrawalRequest(
            admin_user_id=admin_user_id,
            amount_stars=amount_stars,
            status="converted" if conversion_type else "pending",
            conversion_type=conversion_type,
            conversion_detail=conversion_detail,
        )
        session.add(req)
        await session.commit()
        return True


async def get_conversion_history(admin_user_id: int) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(WithdrawalRequest)
            .where(WithdrawalRequest.admin_user_id == admin_user_id)
            .order_by(WithdrawalRequest.created_at.desc())
            .limit(20)
        )
        history = []
        for r in result.scalars().all():
            history.append({
                "id": r.id,
                "amount": r.amount_stars,
                "status": r.status,
                "conversion_type": r.conversion_type or "withdrawal",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            })
        return history
