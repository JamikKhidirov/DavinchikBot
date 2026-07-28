import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow():
    return datetime.datetime.now(datetime.UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    daily_likes_count: Mapped[int] = mapped_column(Integer, default=0)
    last_like_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    last_active_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    likes_given = relationship("Like", foreign_keys="Like.from_user_id", back_populates="from_user", cascade="all, delete-orphan")
    likes_received = relationship("Like", foreign_keys="Like.to_user_id", back_populates="to_user", cascade="all, delete-orphan")
    matches_as_user1 = relationship("Match", foreign_keys="Match.user1_id", back_populates="user1", cascade="all, delete-orphan")
    matches_as_user2 = relationship("Match", foreign_keys="Match.user2_id", back_populates="user2", cascade="all, delete-orphan")
