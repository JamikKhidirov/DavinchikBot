import math
from typing import Optional

from sqlalchemy import select

from app.models import Profile
from app.database import async_session


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def update_location(telegram_id: int, latitude: float, longitude: float) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(Profile.user).where(Profile.user.has(telegram_id=telegram_id))
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return False
        profile.latitude = latitude
        profile.longitude = longitude
        await session.commit()
        return True


async def update_search_radius(telegram_id: int, radius_km: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Profile).join(Profile.user).where(Profile.user.has(telegram_id=telegram_id))
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return False
        profile.search_radius = max(1, min(1000, radius_km))
        await session.commit()
        return True


def filter_by_distance(candidates: list[Profile], my_lat: float, my_lon: float, radius_km: int) -> list[tuple[Profile, float]]:
    result = []
    for p in candidates:
        if p.latitude is not None and p.longitude is not None:
            dist = haversine_km(my_lat, my_lon, p.latitude, p.longitude)
            if dist <= radius_km:
                result.append((p, dist))
        else:
            result.append((p, None))
    result.sort(key=lambda x: x[1] if x[1] is not None else float("inf"))
    return result
