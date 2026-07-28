import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow():
    return datetime.datetime.now(datetime.UTC)


GIFT_OPTIONS = {
    "rose": {"label": "🌹 Роза", "stars": 15},
    "heart": {"label": "❤️ Сердце", "stars": 25},
    "chocolate": {"label": "🍫 Шоколад", "stars": 20},
    "ring": {"label": "💍 Кольцо", "stars": 100},
    "cake": {"label": "🎂 Торт", "stars": 30},
    "bear": {"label": "🧸 Мишка", "stars": 35},
}


class Gift(Base):
    __tablename__ = "gifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    gift_type: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    stars_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
