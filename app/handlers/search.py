from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.keyboards.profile import profile_action_keyboard, main_menu_keyboard
from app.services.matching_service import get_next_profile, like_profile, dislike_profile, check_like_limit
from app.services.ad_service import get_active_ads, increment_impression
from app.services.profile_service import get_user_by_telegram_id, has_profile, is_banned, get_user_by_id, get_profile_by_telegram_id
from app.services.notification_service import notify_like, notify_match
from app.config import config

router = Router()
user_swipe_count = {}


@router.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    if not await has_profile(callback.from_user.id):
        await safe_edit(callback, "Сначала создайте анкету через /register", reply_markup=main_menu_keyboard())
        return

    user_swipe_count[callback.from_user.id] = 0
    await show_next_profile(callback)


@router.callback_query(F.data == "next_search")
async def next_search(callback: CallbackQuery):
    await callback.answer()
    await start_search(callback)


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


async def show_next_profile(callback: CallbackQuery):
    profile_data = await get_next_profile(callback.from_user.id)

    if profile_data is None:
        await safe_edit(callback, "👀 Анкеты закончились. Попробуй изменить настройки поиска!", reply_markup=main_menu_keyboard())
        return

    user_swipe_count[callback.from_user.id] = user_swipe_count.get(callback.from_user.id, 0) + 1

    verified_badge = "✅ Верифицирован(а)\n" if profile_data.get("is_verified") else ""
    profile_text = (
        f"{verified_badge}"
        f"{profile_data['name']}, {profile_data['age']}, {profile_data['city']}\n"
        f"{profile_data['bio']}"
    )

    ads = await get_active_ads()
    count = user_swipe_count.get(callback.from_user.id, 0)
    photos = profile_data.get("photos", [])
    videos = profile_data.get("videos", [])
    kb = profile_action_keyboard(profile_data["id"])

    if ads and count % config.swipe_before_ad == 0:
        ad = ads[(count // config.swipe_before_ad - 1) % len(ads)]
        await increment_impression(ad.id)
        text = f"📢 Реклама\n\n{ad.text}\n\n---\n\n{profile_text}"
        if photos:
            await callback.message.answer_photo(photos[0], caption=text, reply_markup=kb)
        elif videos:
            await callback.message.answer_video(videos[0], caption=text, reply_markup=kb)
        else:
            await callback.message.answer(text, reply_markup=kb)
    else:
        try:
            await callback.message.delete()
        except Exception:
            pass
        if photos:
            await callback.message.answer_photo(photos[0], caption=profile_text, reply_markup=kb)
        elif videos:
            await callback.message.answer_video(videos[0], caption=profile_text, reply_markup=kb)
        else:
            await safe_edit(callback, profile_text, reply_markup=kb)


@router.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])

    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    can_like, remaining = await check_like_limit(callback.from_user.id)
    if not can_like:
        await callback.message.answer(
            "❌ Дневной лимит лайков исчерпан (30/30).\n"
            "Завтра лимит обновится. Оформи ⭐ Премиум для безлимитных лайков!",
        )
        return

    result = await like_profile(callback.from_user.id, target_id)

    if result == "match":
        target_user = await get_user_by_id(target_id)
        my_user = await get_user_by_telegram_id(callback.from_user.id)
        my_profile = await get_profile_by_telegram_id(callback.from_user.id)

        if target_user and my_user and my_profile:
            target_profile = await get_profile_by_telegram_id(target_user.telegram_id)
            match_info = {
                "name": my_profile.name,
                "age": my_profile.age,
                "city": my_profile.city,
                "username": my_user.username or "",
                "name2": target_profile.name if target_profile else "",
                "age2": target_profile.age if target_profile else 0,
                "city2": target_profile.city if target_profile else "",
                "username2": target_user.username or "",
            }
            await notify_match(callback.bot, callback.from_user.id, target_user.telegram_id, match_info)

        await callback.message.answer(
            "💕 Взаимная симпатия! Это совпадение!\n"
            "Посмотри свои совпадения в меню.",
        )
    elif result == "liked":
        target_user = await get_user_by_id(target_id)
        my_profile = await get_profile_by_telegram_id(callback.from_user.id)
        my_user = await get_user_by_telegram_id(callback.from_user.id)
        if target_user and my_profile:
            liker_data = {
                "name": my_profile.name,
                "age": my_profile.age,
                "city": my_profile.city,
                "bio": my_profile.bio or "",
                "photos": my_profile.photos or [],
            }
            await notify_like(callback.bot, target_user.telegram_id, liker_data, liker_user_id=my_user.id)

        if remaining and remaining <= 5:
            await callback.message.answer(
                f"⚠️ Осталось {remaining} лайков на сегодня. ⭐ Премиум — без лимитов!",
            )

    await show_next_profile(callback)


@router.callback_query(F.data.startswith("dislike_"))
async def process_dislike(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])

    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    await dislike_profile(callback.from_user.id, target_id)
    await show_next_profile(callback)


@router.callback_query(F.data.startswith("block_"))
async def process_block(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])

    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    from app.services.block_service import block_user

    await block_user(callback.from_user.id, target_id)
    await callback.message.answer("🚫 Пользователь заблокирован. Его анкеты больше не будут показываться.")
    await show_next_profile(callback)
