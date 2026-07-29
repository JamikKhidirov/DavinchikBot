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

    if profile_data.get("telegram_id") == callback.from_user.id:
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
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        ad_kb = None
        if ad.button_url:
            ad_builder = InlineKeyboardBuilder()
            ad_builder.button(text=ad.button_text or "🔗 Перейти", url=ad.button_url)
            ad_kb = ad_builder.as_markup()
        if ad.photo_id:
            await callback.message.answer_photo(ad.photo_id, caption=ad.text, reply_markup=ad_kb)
        else:
            await callback.message.answer(ad.text, reply_markup=ad_kb)

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


async def _handle_match(callback_or_message, target_id: int, my_telegram_id: int, is_superlike: bool = False, superlike_msg: str = None):
    target_user = await get_user_by_id(target_id)
    my_user = await get_user_by_telegram_id(my_telegram_id)
    my_profile = await get_profile_by_telegram_id(my_telegram_id)

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
            "superlike_message": superlike_msg or "",
        }
        bot = callback_or_message.bot if hasattr(callback_or_message, 'bot') else callback_or_message.bot
        await notify_match(bot, my_telegram_id, target_user.telegram_id, match_info)

    if hasattr(callback_or_message, 'message'):
        await callback_or_message.message.answer(
            "💕 Взаимная симпатия! Это совпадение!\nПосмотри свои совпадения в меню.",
        )
    else:
        await callback_or_message.answer(
            "💕 Взаимная симпатия! Это совпадение!\nПосмотри свои совпадения в меню.",
        )


@router.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])

    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    me = await get_user_by_telegram_id(callback.from_user.id)
    if me and me.id == target_id:
        await callback.answer("❌ Нельзя лайкнуть себя", show_alert=True)
        await show_next_profile(callback)
        return

    can_like, remaining = await check_like_limit(callback.from_user.id)
    if not can_like:
        await callback.message.answer(
            "❌ Дневной лимит лайков исчерпан.\n"
            "Завтра лимит обновится. Оформи ⭐ Премиум для безлимитных лайков!",
        )
        return

    result = await like_profile(callback.from_user.id, target_id)

    if result == "match":
        await _handle_match(callback, target_id, callback.from_user.id)
    elif result == "liked":
        target_user = await get_user_by_id(target_id)
        liker_profile = await get_profile_by_telegram_id(callback.from_user.id)
        if target_user and liker_profile:
            await notify_like(
                callback.bot,
                target_user.telegram_id,
                {
                    "name": liker_profile.name,
                    "age": liker_profile.age,
                    "city": liker_profile.city,
                    "bio": liker_profile.bio,
                    "photos": liker_profile.photos or [],
                    "videos": liker_profile.videos or [],
                },
                liker_user_id=callback.from_user.id,
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
    liker_telegram_id = int(callback.data.split("_")[1])

    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    liker_user = await get_user_by_telegram_id(liker_telegram_id)
    if liker_user is None:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    target_id = liker_user.id

    me = await get_user_by_telegram_id(callback.from_user.id)
    if me and me.id == target_id:
        await callback.answer("❌ Нельзя", show_alert=True)
        return

    can_like, _ = await check_like_limit(callback.from_user.id)
    if not can_like:
        try:
            await callback.message.edit_text(
                "❌ У тебя закончились лайки на сегодня.\n"
                "Оформи ⭐ Премиум или приведи друга!"
            )
        except Exception:
            await callback.message.answer("❌ Лимит лайков исчерпан.")
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
        try:
            await callback.message.edit_text("💕 Взаимная симпатия! Это совпадение!\nПосмотри свои совпадения в меню.")
        except Exception:
            await callback.message.answer("💕 Взаимная симпатия! Это совпадение!")
    elif result == "liked":
        try:
            await callback.message.edit_text("✅ Твой лайк отправлен! Если человек тоже лайкнет — будет совпадение.")
        except Exception:
            await callback.message.answer("✅ Лайк отправлен!")
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

    me = await get_user_by_telegram_id(callback.from_user.id)
    if me and me.id == target_id:
        await show_next_profile(callback)
        return

    await dislike_profile(callback.from_user.id, target_id)
    await show_next_profile(callback)


@router.callback_query(F.data.startswith("superlike_"))
async def process_superlike_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    target_id = int(callback.data.split("_")[1])

    me = await get_user_by_telegram_id(callback.from_user.id)
    if me and me.id == target_id:
        await callback.answer("❌ Нельзя суперлайкнуть себя", show_alert=True)
        return

    can_like, remaining = await check_like_limit(callback.from_user.id)
    if not can_like:
        await callback.message.answer(
            "❌ Недостаточно лайков для суперлайка.\n"
            "Купи ⭐ Премиум для безлимита или приведи друга!"
        )
        return

    await state.set_state(SuperlikeMessage.text)
    await state.update_data(superlike_target_id=target_id)
    await safe_edit(callback,
        "⭐ Суперлайк! Напиши короткое сообщение (до 200 символов):\n\n"
        "(Или отправь '-' чтобы отправить без сообщения)"
    )


@router.message(SuperlikeMessage.text, F.text)
async def process_superlike_message(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("superlike_target_id")
    if not target_id:
        await state.clear()
        return

    msg_text = message.text.strip() if message.text else ""
    if msg_text == "-":
        msg_text = ""
    if len(msg_text) > 200:
        msg_text = msg_text[:200]

    if await is_banned(message.from_user.id):
        await message.answer("🚫 Вы забанены.")
        await state.clear()
        return

    result = await like_profile(message.from_user.id, target_id, is_superlike=True, superlike_message=msg_text)

    if result == "match":
        await _handle_match(message, target_id, message.from_user.id, is_superlike=True, superlike_msg=msg_text)
    elif result == "liked":
        target_user = await get_user_by_id(target_id)
        liker_profile = await get_profile_by_telegram_id(message.from_user.id)
        if target_user and liker_profile:
            await notify_superlike(
                message.bot,
                target_user.telegram_id,
                {
                    "superlike_message": msg_text,
                },
                liker_user_id=None,
            )
        await message.answer("✅ Суперлайк отправлен! Если человек тоже лайкнет — будет совпадение.")
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


@router.message(SuperlikeMessage.text)
async def process_superlike_non_text(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, отправь текстовое сообщение (или '-' чтобы пропустить).")
    # State stays unchanged so they can try again


@router.callback_query(F.data.startswith("block_"))
async def process_block(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])

    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    me = await get_user_by_telegram_id(callback.from_user.id)
    if me and me.id == target_id:
        await show_next_profile(callback)
        return

    from app.services.block_service import block_user

    await block_user(callback.from_user.id, target_id)
    await callback.message.answer("🚫 Пользователь заблокирован. Его анкеты больше не будут показываться.")
    await show_next_profile(callback)
