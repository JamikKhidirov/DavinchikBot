from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def notify_match(bot: Bot, user1_telegram_id: int, user2_telegram_id: int, match_info: dict):
    text1 = (
        f"💕 Взаимная симпатия!\n\n"
        f"Вы понравились {match_info['name']}, {match_info['age']} лет, {match_info['city']}!\n"
        f"Напишите ей/ему: @{match_info['username'] or 'пользователь не указал username'}"
    )
    text2 = (
        f"💕 Взаимная симпатия!\n\n"
        f"Вы понравились {match_info['name2']}, {match_info['age2']} лет, {match_info['city2']}!\n"
        f"Напишите ей/ему: @{match_info['username2'] or 'пользователь не указал username'}"
    )

    try:
        await bot.send_message(user1_telegram_id, text1)
    except Exception:
        pass
    try:
        await bot.send_message(user2_telegram_id, text2)
    except Exception:
        pass


async def notify_like(bot: Bot, user_telegram_id: int, liker_name: str):
    text = f"💕 Кому-то понравилась ваша анкета! Откройте бота, чтобы узнать кто."
    try:
        await bot.send_message(user_telegram_id, text)
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
