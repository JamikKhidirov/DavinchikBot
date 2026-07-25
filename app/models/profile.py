import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    looking_for: Mapped[str] = mapped_column(String(16), default="all")
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    photos: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_photo_id: Mapped[str] = mapped_column(String(512), nullable=True)
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    age_min_preference: Mapped[int] = mapped_column(Integer, default=18)
    age_max_preference: Mapped[int] = mapped_column(Integer, default=99)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    user = relationship("User", back_populates="profile")
