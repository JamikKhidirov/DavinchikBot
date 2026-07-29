from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.keyboards.profile import profile_action_keyboard, main_menu_keyboard
from app.services.matching_service import get_next_profile, like_profile, dislike_profile, check_like_limit
from app.services.ad_service import get_active_ads, increment_impression
from app.services.profile_service import get_user_by_telegram_id, has_profile, is_banned, get_user_by_id, get_profile_by_telegram_id
from app.services.notification_service import notify_like, notify_match, notify_superlike
from app.config import config


class SuperlikeMessage(StatesGroup):
    text = State()

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
        if videos:
            await callback.message.answer_video(videos[0], caption=text, reply_markup=kb)
        elif photos:
            await callback.message.answer_photo(photos[0], caption=text, reply_markup=kb)
        else:
            await callback.message.answer(text, reply_markup=kb)
    else:
        try:
            await callback.message.delete()
        except Exception:
            pass
        if videos:
            await callback.message.answer_video(videos[0], caption=profile_text, reply_markup=kb)
        elif photos:
            await callback.message.answer_photo(photos[0], caption=profile_text, reply_markup=kb)
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
    elif result == "already_exists":
        await callback.answer("✅ Уже оценено", show_alert=False)
        await show_next_profile(callback)
        return
    elif result == "blocked":
        await callback.message.answer("❌ Невозможно: пользователь заблокирован.")
    elif result == "limit_exceeded":
        await callback.message.answer(
            "❌ Лимит лайков исчерпан.\n"
            "Приведи друга или купи ⭐ Премиум!",
        )

    await show_next_profile(callback)


@router.callback_query(F.data.startswith("nlike_"))
async def process_notification_like(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])

    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    can_like, _ = await check_like_limit(callback.from_user.id)
    if not can_like:
        await callback.message.edit_text(
            "❌ У тебя закончились лайки на сегодня.\n"
            "Оформи ⭐ Премиум или приведи друга!"
        )
        return

    result = await like_profile(callback.from_user.id, target_id)

    if result == "match":
        target_user = await get_user_by_id(target_id)
        my_user = await get_user_by_telegram_id(callback.from_user.id)
        if target_user and my_user:
            match_info = {"name": callback.from_user.first_name or "?", "age": 0, "city": "?"}
            await notify_match(callback.bot, callback.from_user.id, target_user.telegram_id, match_info)
        try:
            await callback.message.edit_text("💕 Взаимная симпатия! Это совпадение!\nПосмотри свои совпадения в меню.")
        except Exception:
            await callback.message.answer("💕 Взаимная симпатия! Это совпадение!")
    elif result == "liked":
        try:
            await callback.message.edit_text("✅ Ты ответил(а) взаимностью! Если человек тоже лайкнет — будет совпадение.")
        except Exception:
            await callback.message.answer("✅ Ты ответил(а) взаимностью!")
    elif result == "already_exists":
        await callback.answer("✅ Уже взаимно", show_alert=False)
    elif result == "limit_exceeded":
        await callback.message.answer(
            "❌ Лимит лайков исчерпан.\n"
            "Приведи друга или купи ⭐ Премиум!"
        )


@router.callback_query(F.data == "hide_notification")
async def hide_notification(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_text("👋 Убрано.")
        except Exception:
            pass


@router.callback_query(F.data.startswith("dislike_"))
async def process_dislike(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])

    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    await dislike_profile(callback.from_user.id, target_id)
    await show_next_profile(callback)


@router.callback_query(F.data.startswith("superlike_"))
async def process_superlike_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    can_like, remaining = await check_like_limit(callback.from_user.id)
    if not can_like:
        await callback.message.answer(
            "❌ Недостаточно лайков для суперлайка.\n"
            "Купи ⭐ Премиум для безлимита или приведи друга!"
        )
        return

    target_id = int(callback.data.split("_")[1])
    await state.set_state(SuperlikeMessage.text)
    await state.update_data(superlike_target_id=target_id)
    await safe_edit(callback,
        "⭐ Суперлайк! Напиши короткое сообщение (оно будет отправлено анонимно):\n\n"
        "(Или отправь '-' чтобы отправить без сообщения)"
    )


@router.message(SuperlikeMessage.text)
async def process_superlike_message(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("superlike_target_id")
    if not target_id:
        await state.clear()
        return

    msg_text = message.text.strip() if message.text else ""
    if msg_text == "-":
        msg_text = ""

    if await is_banned(message.from_user.id):
        await message.answer("🚫 Вы забанены.")
        await state.clear()
        return

    result = await like_profile(message.from_user.id, target_id, is_superlike=True, superlike_message=msg_text)

    if result == "match":
        target_user = await get_user_by_id(target_id)
        my_user = await get_user_by_telegram_id(message.from_user.id)
        my_profile = await get_profile_by_telegram_id(message.from_user.id)
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
            await notify_match(message.bot, message.from_user.id, target_user.telegram_id, match_info)
        await message.answer("💕 Взаимная симпатия! Это совпадение!")
    elif result == "liked":
        target_user = await get_user_by_id(target_id)
        my_profile = await get_profile_by_telegram_id(message.from_user.id)
        my_user = await get_user_by_telegram_id(message.from_user.id)
        if target_user and my_profile:
            liker_data = {
                "name": my_profile.name,
                "age": my_profile.age,
                "city": my_profile.city,
                "bio": my_profile.bio or "",
                "photos": my_profile.photos or [],
                "superlike_message": msg_text,
            }
            await notify_superlike(message.bot, target_user.telegram_id, liker_data, liker_user_id=my_user.id)
    elif result == "already_exists":
        await message.answer("✅ Уже отправлено")
    elif result == "blocked":
        await message.answer("❌ Невозможно отправить суперлайк.")
    elif result == "limit_exceeded":
        await message.answer(
            "❌ Лимит лайков исчерпан.\n"
            "Приведи друга или купи ⭐ Премиум!",
        )

    await state.clear()

    from types import SimpleNamespace
    fake_cb = SimpleNamespace(from_user=message.from_user, bot=message.bot, message=message, answer=lambda: None)
    await show_next_profile(fake_cb)


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
