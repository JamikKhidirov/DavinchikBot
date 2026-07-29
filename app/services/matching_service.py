import datetime
from typing import Optional

from sqlalchemy import select, and_, or_, delete

from app.models import User, Profile, Like, Match, Block
from app.database import async_session
from app.config import config

UTC = datetime.timezone.utc


async def check_like_limit(telegram_id: int) -> tuple[bool, int]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False, 0

        if user.is_premium:
            return True, 999

        total_available = (user.extra_likes or 0)
        today = datetime.datetime.now(UTC).date()
        if user.last_like_date and user.last_like_date.date() == today:
            remaining = config.max_likes_per_day - user.daily_likes_count + total_available
            if remaining <= 0 and total_available <= 0:
                return False, 0
            return True, remaining
        else:
            user.daily_likes_count = 0
            user.last_like_date = datetime.datetime.now(UTC)
            await session.commit()
            return True, config.max_likes_per_day + total_available


async def like_profile(from_telegram_id: int, to_user_id: int, is_superlike: bool = False, superlike_message: str = None) -> Optional[str]:
    async with async_session() as session:
        from_result = await session.execute(select(User).where(User.telegram_id == from_telegram_id))
        from_user = from_result.scalar_one_or_none()
        if from_user is None:
            return None

        if from_user.id == to_user_id:
            return None

        to_user = await session.execute(select(User).where(User.id == to_user_id))
        to_user = to_user.scalar_one_or_none()
        if to_user is None:
            return None

        from app.services.block_service import is_blocked
        if await is_blocked(from_user.id, to_user.id):
            return "blocked"

        result = await session.execute(
            select(Like).where(
                and_(Like.from_user_id == from_user.id, Like.to_user_id == to_user_id)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return "already_exists"

        if not from_user.is_premium:
            from_user.daily_likes_count += 1
            from_user.last_like_date = datetime.datetime.now(UTC)
            if from_user.daily_likes_count > config.max_likes_per_day:
                if (from_user.extra_likes or 0) > 0:
                    from_user.extra_likes -= 1
                else:
                    await session.rollback()
                    return "limit_exceeded"

        like = Like(
            from_user_id=from_user.id,
            to_user_id=to_user.id,
            is_like=True,
            is_superlike=is_superlike,
            superlike_message=superlike_message if is_superlike else None,
        )
        session.add(like)
        await session.commit()

        mutual = await session.execute(
            select(Like).where(
                and_(Like.from_user_id == to_user.id, Like.to_user_id == from_user.id, Like.is_like == True)
            )
        )
        if mutual.scalar_one_or_none():
            match = Match(user1_id=min(from_user.id, to_user.id), user2_id=max(from_user.id, to_user.id))
            session.add(match)
            await session.commit()
            return "match"

        return "liked"


async def dislike_profile(from_telegram_id: int, to_user_id: int) -> bool:
    async with async_session() as session:
        from_result = await session.execute(select(User).where(User.telegram_id == from_telegram_id))
        from_user = from_result.scalar_one_or_none()
        if from_user is None:
            return False

        result = await session.execute(
            select(Like).where(
                and_(Like.from_user_id == from_user.id, Like.to_user_id == to_user_id)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            if not existing.is_like:
                return True
            existing.is_like = False
        else:
            dislike = Like(from_user_id=from_user.id, to_user_id=to_user_id, is_like=False)
            session.add(dislike)

        u1, u2 = min(from_user.id, to_user_id), max(from_user.id, to_user_id)
        await session.execute(
            delete(Match).where(and_(Match.user1_id == u1, Match.user2_id == u2))
        )

        await session.commit()
        return True


async def get_next_profile(telegram_id: int) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        profile_result = await session.execute(select(Profile).where(Profile.user_id == user.id))
        my_profile = profile_result.scalar_one_or_none()
        if my_profile is None:
            return None

        matches_subq1 = select(Match.user2_id).where(Match.user1_id == user.id)
        matches_subq2 = select(Match.user1_id).where(Match.user2_id == user.id)
        blocked_by_me = select(Block.blocked_user_id).where(Block.user_id == user.id)
        blocked_me = select(Block.user_id).where(Block.blocked_user_id == user.id)

        base_filters = [
            Profile.user_id != user.id,
            Profile.is_active == True,
            Profile.user_id.not_in(matches_subq1),
            Profile.user_id.not_in(matches_subq2),
            Profile.user_id.not_in(blocked_by_me),
            Profile.user_id.not_in(blocked_me),
            Profile.age >= my_profile.age_min_preference,
            Profile.age <= my_profile.age_max_preference,
            or_(
                Profile.looking_for == "all",
                Profile.looking_for == my_profile.gender,
            ),
        ]

        def sort_exprs():
            return [Profile.is_boosted.desc(), Profile.is_verified.desc()]

        liked_subq = select(Like.to_user_id).where(and_(Like.from_user_id == user.id, Like.is_like == True))
        disliked_subq = select(Like.to_user_id).where(and_(Like.from_user_id == user.id, Like.is_like == False))
        seen_subq = select(Like.to_user_id).where(Like.from_user_id == user.id)

        city_filters = [*base_filters, Profile.user_id.not_in(seen_subq), Profile.city == my_profile.city]
        candidates = await session.execute(
            select(Profile)
            .where(and_(*city_filters))
            .order_by(*sort_exprs(), Profile.created_at.desc())
            .limit(5)
        )
        candidates_list = list(candidates.scalars().all())

        if not candidates_list:
            all_filters = [*base_filters, Profile.user_id.not_in(seen_subq)]
            candidates = await session.execute(
                select(Profile)
                .where(and_(*all_filters))
                .order_by(*sort_exprs(), Profile.created_at.desc())
                .limit(5)
            )
            candidates_list = list(candidates.scalars().all())

        if not candidates_list:
            wider_filters = [Profile.is_active == True, Profile.user_id.not_in(blocked_by_me), Profile.user_id.not_in(blocked_me)]
            candidates = await session.execute(
                select(Profile)
                .where(and_(*wider_filters))
                .order_by(Profile.created_at.desc())
                .limit(5)
            )
            candidates_list = list(candidates.scalars().all())

        if not candidates_list:
            last_filters = [Profile.is_active == True, Profile.user_id != user.id]
            candidates = await session.execute(
                select(Profile)
                .where(and_(*last_filters))
                .order_by(Profile.created_at.desc())
                .limit(1)
            )
            candidates_list = list(candidates.scalars().all())

        if not candidates_list:
            return None

        candidate_profile = _pick_best_match(candidates_list, my_profile)

        candidate_user = await session.execute(select(User).where(User.id == candidate_profile.user_id))
        candidate_user = candidate_user.scalar_one_or_none()

        candidate_profile.views_count = (candidate_profile.views_count or 0) + 1
        await session.commit()

        return {
            "id": candidate_user.id,
            "telegram_id": candidate_user.telegram_id,
            "name": candidate_profile.name,
            "age": candidate_profile.age,
            "gender": candidate_profile.gender,
            "city": candidate_profile.city,
            "bio": candidate_profile.bio or "",
            "photos": candidate_profile.photos or [],
            "videos": candidate_profile.videos or [],
            "is_verified": candidate_profile.is_verified,
            "is_boosted": candidate_profile.is_boosted,
        }


def _pick_best_match(candidates: list[Profile], my_profile: Profile) -> Profile:
    scored = []
    for p in candidates:
        score = 0.0
        age_diff = abs(p.age - my_profile.age)
        if age_diff <= 3:
            score += 30
        elif age_diff <= 7:
            score += 20
        elif age_diff <= 15:
            score += 10
        else:
            score += 2

        if p.looking_for == my_profile.gender or p.looking_for == "all":
            score += 15

        if p.is_boosted:
            score += 50
        if p.is_verified:
            score += 10

        if p.city == my_profile.city:
            score += 20

        my_interests = set(my_profile.interests or [])
        p_interests = set(p.interests or [])
        common = len(my_interests & p_interests)
        if common > 0:
            score += common * 10

        if my_profile.latitude and my_profile.longitude and p.latitude and p.longitude:
            from app.services.geo_service import haversine_km
            dist = haversine_km(my_profile.latitude, my_profile.longitude, p.latitude, p.longitude)
            if dist <= 10:
                score += 25
            elif dist <= 50:
                score += 15
            elif dist <= my_profile.search_radius:
                score += 5
            else:
                score -= 10

        scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


async def get_matches(telegram_id: int) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return []

        matches = await session.execute(
            select(Match).where(
                or_(Match.user1_id == user.id, Match.user2_id == user.id)
            )
        )
        match_list = []
        for match in matches.scalars().all():
            matched_user_id = match.user2_id if match.user1_id == user.id else match.user1_id
            matched_user = await session.execute(select(User).where(User.id == matched_user_id))
            matched_user = matched_user.scalar_one_or_none()
            matched_profile = await session.execute(
                select(Profile).where(Profile.user_id == matched_user_id)
            )
            matched_profile = matched_profile.scalar_one_or_none()

            if matched_user and matched_profile:
                match_list.append({
                    "id": matched_user.id,
                    "telegram_id": matched_user.telegram_id,
                    "username": matched_user.username,
                    "name": matched_profile.name,
                    "age": matched_profile.age,
                    "city": matched_profile.city,
                    "photo": matched_profile.photos[0] if matched_profile.photos else None,
                    "video": matched_profile.videos[0] if matched_profile.videos else None,
                    "matched_at": match.created_at,
                })
        return match_list


async def unmatch(telegram_id: int, target_user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False

        u1, u2 = min(user.id, target_user_id), max(user.id, target_user_id)
        await session.execute(
            delete(Match).where(and_(Match.user1_id == u1, Match.user2_id == u2))
        )
        await session.commit()
        return True


async def complaint(from_telegram_id: int, target_user_id: int, reason: str) -> bool:
    from app.models.complaint import Complaint

    async with async_session() as session:
        from_result = await session.execute(select(User).where(User.telegram_id == from_telegram_id))
        from_user = from_result.scalar_one_or_none()
        if from_user is None:
            return False

        complaint = Complaint(from_user_id=from_user.id, complained_user_id=target_user_id, reason=reason)
        session.add(complaint)
        await session.commit()
        return True
