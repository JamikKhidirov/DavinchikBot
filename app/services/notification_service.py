from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def notify_match(bot: Bot, user1_telegram_id: int, user2_telegram_id: int, match_info: dict):
    superlike_msg = match_info.get("superlike_message", "")
    superlike_text1 = ""
    superlike_text2 = ""
    if superlike_msg:
        superlike_text1 = f"\n\n⭐ Тебе отправили суперлайк с сообщением: {superlike_msg}"
        superlike_text2 = f"\n\n⭐ Ты отправил(а) суперлайк с сообщением: {superlike_msg}"

    text1 = (
        f"💕 Взаимная симпатия!\n\n"
        f"Вы понравились {match_info['name2']}, {match_info['age2']} лет, {match_info['city2']}!\n"
        f"Напишите ей/ему: @{match_info['username2'] or 'пользователь не указал username'}"
        f"{superlike_text1}"
    )
    text2 = (
        f"💕 Взаимная симпатия!\n\n"
        f"Вы понравились {match_info['name']}, {match_info['age']} лет, {match_info['city']}!\n"
        f"Напишите ей/ему: @{match_info['username'] or 'пользователь не указал username'}"
        f"{superlike_text2}"
    )

    try:
        await bot.send_message(user1_telegram_id, text1)
    except Exception:
        pass
    try:
        await bot.send_message(user2_telegram_id, text2)
    except Exception:
        pass


async def notify_like(bot: Bot, user_telegram_id: int, liker_profile: dict, liker_user_id: int = None):
    text = (
        f"💕 Твоя анкета понравилась!\n\n"
        f"{liker_profile.get('name', '?')}, {liker_profile.get('age', '?')} лет\n"
        f"🏙 {liker_profile.get('city', '?')}\n"
        f"{liker_profile.get('bio', '')}"
    )
    photos = liker_profile.get("photos", [])
    videos = liker_profile.get("videos", [])
    kb = None
    if liker_user_id:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="❤️ Ответить", callback_data=f"nlike_{liker_user_id}")
        builder.button(text="👎 Скрыть", callback_data="hide_notification")
        builder.adjust(2)
        kb = builder.as_markup()
    try:
        if videos:
            await bot.send_video(user_telegram_id, videos[0], caption=text, reply_markup=kb)
        elif photos:
            await bot.send_photo(user_telegram_id, photos[0], caption=text, reply_markup=kb)
        else:
            await bot.send_message(user_telegram_id, text, reply_markup=kb)
    except Exception:
        pass


async def notify_superlike(bot: Bot, user_telegram_id: int, liker_profile: dict, liker_user_id: int = None):
    msg = liker_profile.get("superlike_message", "")
    text = (
        f"⭐ Кто-то отправил тебе суперлайк!\n\n"
        f"Ты очень понравился(ась) незнакомцу"
    )
    if msg:
        text += f"\n\n💬 Сообщение: {msg}"

    kb = None
    if liker_user_id:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="❤️ Ответить взаимностью", callback_data=f"nlike_{liker_user_id}")
        builder.button(text="👎 Скрыть", callback_data="hide_notification")
        builder.adjust(2)
        kb = builder.as_markup()
    try:
        await bot.send_message(user_telegram_id, text, reply_markup=kb)
    except Exception:
        pass


async def send_broadcast(bot: Bot, user_ids: list[int], text: str, photo_id: str = None):
    success = 0
    failed = 0
    for uid in user_ids:
        try:
            if photo_id:
                await bot.send_photo(uid, photo_id, caption=text)
            else:
                await bot.send_message(uid, text)
            success += 1
        except Exception:
            failed += 1
    return success, failed
