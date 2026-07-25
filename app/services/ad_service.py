from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Advertisement
from app.database import async_session


async def create_ad(photo_id: str = None, text: str = "", button_text: str = None, button_url: str = None) -> Advertisement:
    async with async_session() as session:
        ad = Advertisement(
            photo_id=photo_id,
            text=text,
            button_text=button_text,
            button_url=button_url,
        )
        session.add(ad)
        await session.commit()
        await session.refresh(ad)
        return ad


async def get_active_ads() -> list[Advertisement]:
    async with async_session() as session:
        result = await session.execute(
            select(Advertisement).where(Advertisement.is_active == True)
        )
        return list(result.scalars().all())


async def get_all_ads() -> list[Advertisement]:
    async with async_session() as session:
        result = await session.execute(select(Advertisement).order_by(Advertisement.created_at.desc()))
        return list(result.scalars().all())


async def get_ad_by_id(ad_id: int) -> Optional[Advertisement]:
    async with async_session() as session:
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        return result.scalar_one_or_none()


async def toggle_ad(ad_id: int) -> Optional[bool]:
    async with async_session() as session:
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad is None:
            return None
        ad.is_active = not ad.is_active
        await session.commit()
        return ad.is_active


async def increment_impression(ad_id: int):
    async with async_session() as session:
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.impressions_count += 1
            await session.commit()


async def increment_click(ad_id: int):
    async with async_session() as session:
        result = await session.execute(select(Advertisement).where(Advertisement.id == ad_id))
        ad = result.scalar_one_or_none()
        if ad:
            ad.clicks_count += 1
            await session.commit()


async def get_swipe_count() -> int:
    from app.models import Like
    async with async_session() as session:
        result = await session.execute(select(func.count(Like.id)))
        return result.scalar() or 0
