import datetime
from typing import Optional

from sqlalchemy import select, or_, and_, delete

from app.models import Message, Match, User
from app.database import async_session

UTC = datetime.timezone.utc


async def send_message(match_id: int, sender_telegram_id: int, text: str) -> Optional[Message]:
    async with async_session() as session:
        sender = await session.execute(select(User).where(User.telegram_id == sender_telegram_id))
        sender = sender.scalar_one_or_none()
        if sender is None:
            return None

        match = await session.execute(select(Match).where(Match.id == match_id))
        match = match.scalar_one_or_none()
        if match is None:
            return None

        if sender.id not in (match.user1_id, match.user2_id):
            return None

        msg = Message(match_id=match_id, sender_id=sender.id, text=text)
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


async def get_messages(match_id: int, telegram_id: int, limit: int = 50) -> list[dict]:
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if user is None:
            return []

        match = await session.execute(select(Match).where(Match.id == match_id))
        match = match.scalar_one_or_none()
        if match is None:
            return []

        if user.id not in (match.user1_id, match.user2_id):
            return []

        result = await session.execute(
            select(Message)
            .where(Message.match_id == match_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = []
        for msg in reversed(list(result.scalars().all())):
            sender_user = await session.execute(select(User).where(User.id == msg.sender_id))
            sender_user = sender_user.scalar_one_or_none()
            messages.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "sender_telegram_id": sender_user.telegram_id if sender_user else 0,
                "text": msg.text,
                "created_at": msg.created_at.isoformat() if msg.created_at else "",
            })
        return messages


async def get_match_chat_info(match_id: int, telegram_id: int) -> Optional[dict]:
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if user is None:
            return None

        match = await session.execute(select(Match).where(Match.id == match_id))
        match = match.scalar_one_or_none()
        if match is None:
            return None

        partner_id = match.user2_id if match.user1_id == user.id else match.user1_id
        partner = await session.execute(select(User).where(User.id == partner_id))
        partner = partner.scalar_one_or_none()
        if partner is None:
            return None

        from app.models import Profile
        partner_profile = await session.execute(select(Profile).where(Profile.user_id == partner_id))
        partner_profile = partner_profile.scalar_one_or_none()

        msg_count = await session.execute(
            select(Message).where(Message.match_id == match_id)
        )
        total = len(list(msg_count.scalars().all()))

        return {
            "match_id": match_id,
            "partner_id": partner.id,
            "partner_telegram_id": partner.telegram_id,
            "partner_name": partner_profile.name if partner_profile else "—",
            "partner_username": partner.username,
            "message_count": total,
        }


async def get_user_matches_with_messages(telegram_id: int) -> list[dict]:
    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user.scalar_one_or_none()
        if user is None:
            return []

        matches = await session.execute(
            select(Match).where(
                or_(Match.user1_id == user.id, Match.user2_id == user.id)
            )
        )
        result = []
        for m in matches.scalars().all():
            partner_id = m.user2_id if m.user1_id == user.id else m.user1_id
            partner = await session.execute(select(User).where(User.id == partner_id))
            partner = partner.scalar_one_or_none()

            from app.models import Profile
            partner_profile = await session.execute(select(Profile).where(Profile.user_id == partner_id))
            partner_profile = partner_profile.scalar_one_or_none()

            last_msg = await session.execute(
                select(Message)
                .where(Message.match_id == m.id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            last_msg = last_msg.scalar_one_or_none()

            result.append({
                "match_id": m.id,
                "partner_name": partner_profile.name if partner_profile else "—",
                "partner_age": partner_profile.age if partner_profile else 0,
                "partner_city": partner_profile.city if partner_profile else "",
                "partner_photo": (partner_profile.photos or [None])[0] if partner_profile else None,
                "last_message": last_msg.text if last_msg else None,
                "last_message_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
            })
        return result
