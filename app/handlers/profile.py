from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.keyboards.profile import (
    edit_profile_keyboard, main_menu_keyboard, my_gender_keyboard,
    gender_keyboard, settings_keyboard, search_settings_keyboard,
    interests_keyboard, referral_keyboard,
)
from app.services.profile_service import (
    get_profile_by_telegram_id, update_profile, has_profile, is_banned,
    get_profile_stats, request_verification, get_user_by_telegram_id,
)
from app.services.geo_service import update_location, update_search_radius
from app.services.referral_service import get_or_create_referral_code, get_referral_stats, REFERRER_BONUS_LIKES, REFERRED_BONUS_LIKES
from app.states.edit_profile import EditProfile, Verification

router = Router()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "my_profile")
async def show_my_profile(callback: CallbackQuery):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        await safe_edit(callback, "У вас нет анкеты. Создайте через /register", reply_markup=main_menu_keyboard())
        return

    user = await get_user_by_telegram_id(callback.from_user.id)
    stats = await get_profile_stats(callback.from_user.id)

    gender_map = {"male": "👨 Мужской", "female": "👩 Женский"}
    looking_map = {"male": "Мужчин", "female": "Женщин", "all": "Всех"}

    verified_badge = "✅ Верифицирован(а)" if profile.is_verified else "❌ Не верифицирован(а)"
    premium_badge = "⭐ Премиум" if user and user.is_premium else "👤 Бесплатный"
    referral_badge = " 🏆 Реферал" if profile.is_referral_badge else ""
    interests_text = ", ".join(profile.interests or []) if profile.interests else "—"

    text = (
        "📝 Твоя анкета:\n\n"
        f"📝 Имя: {profile.name}\n"
        f"🎂 Возраст: {profile.age}\n"
        f"⚧ Пол: {gender_map.get(profile.gender, profile.gender)}\n"
        f"🔍 Ищу: {looking_map.get(profile.looking_for, profile.looking_for)}\n"
        f"🏙 Город: {profile.city}\n"
        f"📄 О себе: {profile.bio or '—'}\n"
        f"🎯 Интересы: {interests_text}\n"
        f"📸 Фото: {len(profile.photos or [])} | 🎬 Видео: {len(profile.videos or [])}\n"
        f"{verified_badge} | {premium_badge}{referral_badge}\n\n"
        f"📊 Статистика:\n"
        f"👁 Просмотров: {stats.get('views', 0)}\n"
        f"❤️ Получено лайков: {stats.get('likes_received', 0)}\n"
        f"💕 Совпадений: {stats.get('matches', 0)}"
    )

    kb = edit_profile_keyboard()
    photos = profile.photos or []
    videos = profile.videos or []
    try:
        await callback.message.delete()
    except Exception:
        pass
    if photos:
        await callback.message.answer_photo(photos[0], caption=text, reply_markup=kb)
    elif videos:
        await callback.message.answer_video(videos[0], caption=text, reply_markup=kb)
    else:
        await callback.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("edit_"))
async def edit_profile_field(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    field = callback.data.replace("edit_", "")

    field_states = {
        "name": EditProfile.name,
        "age": EditProfile.age,
        "gender": EditProfile.gender,
        "looking_for": EditProfile.looking_for,
        "city": EditProfile.city,
        "bio": EditProfile.bio,
        "photos": EditProfile.photos,
    }

    prompts = {
        "name": "📝 Введите новое имя:",
        "age": "🎂 Введите новый возраст (16-99):",
        "gender": "⚧ Выберите ваш пол:",
        "looking_for": "🔍 Кого вы ищете?",
        "city": "🏙 Введите ваш город:",
        "bio": "📄 Введите новый текст о себе (или '-' чтобы удалить):",
        "photos": "📸 Отправьте новые фото (до 3). /done когда закончите:",
    }

    target_state = field_states.get(field)
    if target_state:
        await state.update_data(edit_field=field)
        await state.set_state(target_state)

        msg = prompts.get(field, "Введите значение:")
        kb = None
        if field == "gender":
            kb = my_gender_keyboard()
        elif field == "looking_for":
            kb = gender_keyboard()

        if kb:
            try:
                await callback.message.edit_text(msg, reply_markup=kb)
            except Exception:
                await callback.message.answer(msg, reply_markup=kb)
        else:
            try:
                await callback.message.edit_text(msg)
            except Exception:
                await callback.message.answer(msg)


@router.message(EditProfile.name)
async def update_name(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field", "name")
    if len(message.text) > 64:
        await message.answer("Слишком длинное (макс 64). Попробуйте ещё:")
        return
    await update_profile(message.from_user.id, **{field: message.text})
    await state.clear()
    await message.answer("✅ Обновлено!", reply_markup=main_menu_keyboard())


@router.message(EditProfile.age)
async def update_age(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field", "age")
    try:
        val = int(message.text)
        if field == "search_radius":
            if val < 1 or val > 1000:
                await message.answer("Введите число от 1 до 1000:")
                return
            await update_search_radius(message.from_user.id, val)
        else:
            if val < 16 or val > 99:
                raise ValueError
            await update_profile(message.from_user.id, **{field: val})
    except ValueError:
        await message.answer("Введите число от 16 до 99:")
        return
    await state.clear()
    await message.answer("✅ Обновлено!", reply_markup=main_menu_keyboard())


@router.callback_query(EditProfile.gender, F.data.in_({"mygender_male", "mygender_female"}))
async def update_gender(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    gender = "male" if callback.data == "mygender_male" else "female"
    await update_profile(callback.from_user.id, gender=gender)
    await state.clear()
    try:
        await callback.message.edit_text("✅ Пол обновлён!", reply_markup=main_menu_keyboard())
    except Exception:
        await callback.message.answer("✅ Пол обновлён!", reply_markup=main_menu_keyboard())


@router.callback_query(EditProfile.looking_for, F.data.in_({"gender_male", "gender_female", "gender_all"}))
async def update_looking_for(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    mapping = {"gender_male": "male", "gender_female": "female", "gender_all": "all"}
    await update_profile(callback.from_user.id, looking_for=mapping[callback.data])
    await state.clear()
    try:
        await callback.message.edit_text("✅ Настройки поиска обновлены!", reply_markup=main_menu_keyboard())
    except Exception:
        await callback.message.answer("✅ Настройки поиска обновлены!", reply_markup=main_menu_keyboard())


@router.message(EditProfile.city)
async def update_city(message: Message, state: FSMContext):
    if len(message.text) > 128:
        await message.answer("Слишком длинное название. Попробуйте ещё:")
        return
    await update_profile(message.from_user.id, city=message.text.strip())
    await state.clear()
    await message.answer("✅ Город обновлён!", reply_markup=main_menu_keyboard())


@router.message(EditProfile.bio)
async def update_bio(message: Message, state: FSMContext):
    bio = message.text.strip()
    if bio == "-":
        bio = ""
    await update_profile(message.from_user.id, bio=bio)
    await state.clear()
    await message.answer("✅ Информация обновлена!", reply_markup=main_menu_keyboard())


@router.message(EditProfile.photos, F.photo)
async def update_photos(message: Message, state: FSMContext):
    from app.handlers.registration import media_storage

    user_id = message.from_user.id
    if user_id not in media_storage:
        media_storage[user_id] = {"photos": [], "videos": []}

    media_storage[user_id]["photos"].append(message.photo[-1].file_id)
    total = len(media_storage[user_id]["photos"]) + len(media_storage[user_id]["videos"])

    if total >= 3:
        await update_profile(message.from_user.id, photos=media_storage[user_id]["photos"], videos=media_storage[user_id]["videos"])
        media_storage.pop(user_id, None)
        await state.clear()
        await message.answer("✅ Медиа обновлены!", reply_markup=main_menu_keyboard())
    else:
        await message.answer(f"✅ Фото #{len(media_storage[user_id]['photos'])} добавлено. Ещё или /done.")


@router.message(EditProfile.photos, F.video)
async def update_video(message: Message, state: FSMContext):
    from app.handlers.registration import media_storage

    user_id = message.from_user.id
    if user_id not in media_storage:
        media_storage[user_id] = {"photos": [], "videos": []}

    media_storage[user_id]["videos"].append(message.video.file_id)
    total = len(media_storage[user_id]["photos"]) + len(media_storage[user_id]["videos"])

    if total >= 3:
        await update_profile(message.from_user.id, photos=media_storage[user_id]["photos"], videos=media_storage[user_id]["videos"])
        media_storage.pop(user_id, None)
        await state.clear()
        await message.answer("✅ Медиа обновлены!", reply_markup=main_menu_keyboard())
    else:
        await message.answer(f"✅ Видео #{len(media_storage[user_id]['videos'])} добавлено. Ещё или /done.")


@router.message(EditProfile.photos, Command("done"))
async def done_update_photos(message: Message, state: FSMContext):
    from app.handlers.registration import media_storage

    user_id = message.from_user.id
    data = media_storage.pop(user_id, {"photos": [], "videos": []})
    await update_profile(message.from_user.id, photos=data["photos"], videos=data["videos"])
    await state.clear()
    await message.answer("✅ Медиа обновлены!", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "request_verify")
async def request_verify(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        await callback.message.answer("Сначала создайте анкету.")
        return

    if profile.is_verified:
        await safe_edit(callback, "✅ Ваша анкета уже верифицирована!", reply_markup=main_menu_keyboard())
        return

    await state.set_state(Verification.photo)
    await state.update_data(edit_field="verification_photo")
    text = ("📸 Отправьте фото, на котором вы держите листок с написанным"
            "вашим Telegram @username.\n\n"
            "Это нужно для подтверждения, что вы реальный человек.")
    try:
        await callback.message.edit_text(text)
    except Exception:
        await callback.message.answer(text)


@router.message(Verification.photo, F.photo)
async def handle_verify_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await request_verification(message.from_user.id, photo_id)
    await state.clear()
    await message.answer(
        "✅ Фото отправлено на верификацию администратору. Ожидайте.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery):
    await callback.answer()
    user = await get_user_by_telegram_id(callback.from_user.id)
    is_premium = user and user.is_premium
    await safe_edit(callback, "⚙️ Настройки:", reply_markup=settings_keyboard(is_premium=is_premium))


@router.callback_query(F.data == "search_settings")
async def show_search_settings(callback: CallbackQuery):
    await callback.answer()
    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        await callback.message.answer("Сначала создайте анкету.")
        return

    looking_map = {"male": "Мужчин", "female": "Женщин", "all": "Всех"}
    text = (
        "🎯 Настройки поиска:\n\n"
        f"👫 Ищу: {looking_map.get(profile.looking_for, profile.looking_for)}\n"
        f"📏 Возраст: от {profile.age_min_preference} до {profile.age_max_preference}\n"
        f"🏙 Город: {profile.city}\n"
        f"🗺 Радиус поиска: {profile.search_radius} км"
    )
    await safe_edit(callback, text, reply_markup=search_settings_keyboard())


@router.callback_query(F.data == "set_looking_for")
async def set_looking_for(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="looking_for")
    await state.set_state(EditProfile.looking_for)
    await safe_edit(callback, "🔍 Кого ищем?", reply_markup=gender_keyboard())


@router.callback_query(F.data == "set_age_min")
async def set_age_min(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="age_min_preference")
    await state.set_state(EditProfile.age)
    try:
        await callback.message.edit_text("📏 Минимальный возраст (от 16):")
    except Exception:
        await callback.message.answer("📏 Минимальный возраст (от 16):")


@router.callback_query(F.data == "set_age_max")
async def set_age_max(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="age_max_preference")
    await state.set_state(EditProfile.age)
    try:
        await callback.message.edit_text("📏 Максимальный возраст (до 99):")
    except Exception:
        await callback.message.answer("📏 Максимальный возраст (до 99):")


@router.callback_query(F.data == "set_city")
async def set_city(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="city")
    await state.set_state(EditProfile.city)
    try:
        await callback.message.edit_text("🏙 Введите город:")
    except Exception:
        await callback.message.answer("🏙 Введите город:")


@router.callback_query(F.data == "set_radius")
async def set_radius(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="search_radius")
    await state.set_state(EditProfile.age)
    try:
        await callback.message.edit_text("🗺 Радиус поиска в км (от 1 до 1000):")
    except Exception:
        await callback.message.answer("🗺 Радиус поиска в км (от 1 до 1000):")


@router.callback_query(F.data == "set_location")
async def set_location(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_text(
            "📍 Отправьте свою геопозицию кнопкой 📎 -> 📍 Геопозиция\n\n"
            "Или напишите название города вручную через настройки города."
        )
    except Exception:
        await callback.message.answer(
            "📍 Отправьте свою геопозицию кнопкой 📎 -> 📍 Геопозиция\n\n"
            "Или напишите название города вручную через настройки города."
        )


@router.message(F.location)
async def handle_location(message: Message):
    if message.location:
        ok = await update_location(message.from_user.id, message.location.latitude, message.location.longitude)
        if ok:
            await message.answer("✅ Геопозиция обновлена!", reply_markup=main_menu_keyboard())
        else:
            await message.answer("❌ Сначала создайте анкету через /register")


@router.callback_query(F.data == "edit_interests")
async def edit_interests_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        await callback.message.answer("Сначала создайте анкету.")
        return
    selected = list(profile.interests or [])
    await state.set_state(EditProfile.interests)
    await state.update_data(edit_field="interests", interests=selected)
    try:
        await callback.message.edit_text(
            "🎯 Выбери свои интересы:",
            reply_markup=interests_keyboard(selected),
        )
    except Exception:
        await callback.message.answer(
            "🎯 Выбери свои интересы:",
            reply_markup=interests_keyboard(selected),
        )


@router.callback_query(EditProfile.interests, F.data.startswith("interest_"))
async def edit_interest_toggle(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    selected = list(data.get("interests", []))
    interest = callback.data.replace("interest_", "")
    if interest in selected:
        selected.remove(interest)
    else:
        selected.append(interest)
    await state.update_data(interests=selected)
    try:
        await callback.message.edit_reply_markup(reply_markup=interests_keyboard(selected))
    except Exception:
        pass


@router.callback_query(EditProfile.interests, F.data == "interests_done")
async def edit_interests_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    selected = data.get("interests", [])
    await update_profile(callback.from_user.id, interests=selected)
    await state.clear()
    try:
        await callback.message.edit_text("✅ Интересы обновлены!", reply_markup=main_menu_keyboard())
    except Exception:
        await callback.message.answer("✅ Интересы обновлены!", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "referral")
async def show_referral(callback: CallbackQuery):
    await callback.answer()
    code = await get_or_create_referral_code(callback.from_user.id)
    stats = await get_referral_stats(callback.from_user.id)
    bot_username = (await callback.bot.me()).username
    link = f"https://t.me/{bot_username}?start=ref_{code}"

    trial_text = ""
    if stats.get("premium_trial"):
        trial_text = f"\n⭐ Премиум-триал активен: {stats['premium_trial_days']} дн."
    else:
        trial_text = "\n⭐ Премиум-триал: не активен"

    text = (
        "🔗 <b>Реферальная программа</b>\n\n"
        f"Твоя ссылка: {link}\n\n"
        "🎁 <b>Бонусы за каждого друга:</b>\n"
        f"🔸 Тебе: +{REFERRER_BONUS_LIKES} лайков + 7 дней ⭐ Премиум\n"
        f"🔸 Другу: +{REFERRED_BONUS_LIKES} лайков + 7 дней ⭐ Премиум + 🏆 значок\n\n"
        "🔥 Приведи 3 друзей — получи <b>ещё +50 лайков</b>\n"
        "🔥 Приведи 5 друзей — <b>Премиум на месяц бесплатно</b>\n\n"
        f"📊 Приведено друзей: {stats['count']}\n"
        f"💎 Бонусных лайков: {stats['bonus_likes']}"
        f"{trial_text}"
    )
    await safe_edit(callback, text, reply_markup=referral_keyboard(code))


@router.callback_query(F.data == "referral_stats")
async def show_referral_stats(callback: CallbackQuery):
    await callback.answer()
    stats = await get_referral_stats(callback.from_user.id)
    trial_text = ""
    if stats.get("premium_trial"):
        trial_text = f"\n⭐ Премиум-триал: {stats['premium_trial_days']} дн."
    await safe_edit(callback,
        f"📊 Реферальная статистика:\n\n"
        f"👥 Приведено друзей: {stats['count']}\n"
        f"💎 Бонусных лайков: {stats['bonus_likes']}\n"
        f"🔗 Твой код: {stats['code']}\n"
        f"{trial_text}\n\n"
        f"🎁 За каждого друга:\n"
        f"• Тебе: +{REFERRER_BONUS_LIKES} лайков + 7 дней Премиум\n"
        f"• Другу: +{REFERRED_BONUS_LIKES} лайков + 7 дней Премиум + значок 🏆",
        reply_markup=referral_keyboard(stats['code']),
    )


@router.callback_query(F.data == "copy_referral_link")
async def copy_referral_link(callback: CallbackQuery):
    await callback.answer("Скопируйте ссылку из сообщения выше и отправьте другу!", show_alert=True)


@router.callback_query(F.data == "profile_stats")
async def show_profile_stats(callback: CallbackQuery):
    await callback.answer()
    from app.database import async_session
    from sqlalchemy import select, func, and_, or_
    from app.models import User, Profile, Like, Match
    import datetime

    async with async_session() as session:
        user = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = user.scalar_one_or_none()
        if user is None:
            return

        profile = await session.execute(select(Profile).where(Profile.user_id == user.id))
        profile = profile.scalar_one_or_none()
        if profile is None:
            return

        now = datetime.datetime.now(datetime.UTC)
        week_ago = now - datetime.timedelta(days=7)
        month_ago = now - datetime.timedelta(days=30)

        likes_rec_week = (
            await session.execute(
                select(func.count(Like.id))
                .where(and_(Like.to_user_id == user.id, Like.is_like == True, Like.created_at >= week_ago))
            )
        ).scalar() or 0

        likes_rec_month = (
            await session.execute(
                select(func.count(Like.id))
                .where(and_(Like.to_user_id == user.id, Like.is_like == True, Like.created_at >= month_ago))
            )
        ).scalar() or 0

        likes_rec_total = (
            await session.execute(
                select(func.count(Like.id))
                .where(and_(Like.to_user_id == user.id, Like.is_like == True))
            )
        ).scalar() or 0

        matches_total = (
            await session.execute(
                select(func.count(Match.id))
                .where(or_(Match.user1_id == user.id, Match.user2_id == user.id))
            )
        ).scalar() or 0

        text = (
            f"📊 Статистика анкеты\n\n"
            f"👁 Просмотров всего: {profile.views_count or 0}\n\n"
            f"❤️ Получено лайков:\n"
            f"  • За неделю: {likes_rec_week}\n"
            f"  • За месяц: {likes_rec_month}\n"
            f"  • Всего: {likes_rec_total}\n\n"
            f"💕 Совпадений всего: {matches_total}"
        )
        await safe_edit(callback, text, reply_markup=main_menu_keyboard())
