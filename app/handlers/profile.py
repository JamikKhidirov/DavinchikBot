from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.keyboards.profile import (
    edit_profile_keyboard, main_menu_keyboard, my_gender_keyboard,
    gender_keyboard, settings_keyboard, search_settings_keyboard,
)
from app.services.profile_service import (
    get_profile_by_telegram_id, update_profile, has_profile, is_banned,
    get_profile_stats, request_verification, get_user_by_telegram_id,
)
from app.states.registration import Registration

router = Router()


@router.callback_query(F.data == "my_profile")
async def show_my_profile(callback: CallbackQuery):
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        await callback.answer()
        return

    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        await callback.message.edit_text(
            "У вас нет анкеты. Создайте через /register",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    user = await get_user_by_telegram_id(callback.from_user.id)
    stats = await get_profile_stats(callback.from_user.id)

    gender_map = {"male": "👨 Мужской", "female": "👩 Женский"}
    looking_map = {"male": "Мужчин", "female": "Женщин", "all": "Всех"}

    verified_badge = "✅ Верифицирован(а)" if profile.is_verified else "❌ Не верифицирован(а)"
    premium_badge = "⭐ Премиум" if user and user.is_premium else "👤 Бесплатный"

    text = (
        "📝 Твоя анкета:\n\n"
        f"📝 Имя: {profile.name}\n"
        f"🎂 Возраст: {profile.age}\n"
        f"⚧ Пол: {gender_map.get(profile.gender, profile.gender)}\n"
        f"🔍 Ищу: {looking_map.get(profile.looking_for, profile.looking_for)}\n"
        f"🏙 Город: {profile.city}\n"
        f"📄 О себе: {profile.bio or '—'}\n"
        f"📸 Фото: {len(profile.photos or [])} 📸\n"
        f"{verified_badge} | {premium_badge}\n\n"
        f"📊 Статистика:\n"
        f"👁 Просмотров: {stats.get('views', 0)}\n"
        f"❤️ Получено лайков: {stats.get('likes_received', 0)}\n"
        f"💕 Совпадений: {stats.get('matches', 0)}"
    )

    if profile.photos:
        await callback.message.answer_photo(
            profile.photos[0],
            caption=text,
            reply_markup=edit_profile_keyboard(),
        )
        try:
            await callback.message.delete()
        except Exception:
            pass
    else:
        await callback.message.edit_text(text, reply_markup=edit_profile_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_"))
async def edit_profile_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_", "")

    field_states = {
        "name": Registration.name,
        "age": Registration.age,
        "gender": Registration.gender,
        "looking_for": Registration.looking_for,
        "city": Registration.city,
        "bio": Registration.bio,
        "photos": Registration.photos,
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

    if field in field_states:
        await state.update_data(edit_field=field)

        if field in ("gender", "looking_for", "photos"):
            await state.set_state(Registration(field))
            msg = prompts.get(field, "")
            kb = None
            if field == "gender":
                kb = my_gender_keyboard()
            elif field == "looking_for":
                kb = gender_keyboard()
            await callback.message.edit_text(msg, reply_markup=kb)
        else:
            await state.set_state(Registration(field))
            await callback.message.edit_text(prompts.get(field, "Введите значение:"))

    await callback.answer()


@router.message(Registration.name)
async def update_name(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field", "name")
    if len(message.text) > 64:
        await message.answer("Слишком длинное (макс 64). Попробуйте ещё:")
        return

    await update_profile(message.from_user.id, **{field: message.text})
    await state.clear()
    profile = await get_profile_by_telegram_id(message.from_user.id)
    await message.answer("✅ Обновлено!", reply_markup=main_menu_keyboard())


@router.message(Registration.age)
async def update_age(message: Message, state: FSMContext):
    try:
        val = int(message.text)
        if val < 16 or val > 99:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 16 до 99:")
        return

    data = await state.get_data()
    field = data.get("edit_field", "age")

    await update_profile(message.from_user.id, **{field: val})
    await state.clear()
    await message.answer("✅ Обновлено!", reply_markup=main_menu_keyboard())


@router.callback_query(Registration.gender, F.data.in_({"mygender_male", "mygender_female"}))
async def update_gender(callback: CallbackQuery, state: FSMContext):
    gender = "male" if callback.data == "mygender_male" else "female"
    await update_profile(callback.from_user.id, gender=gender)
    await state.clear()
    await callback.message.edit_text("✅ Пол обновлён!", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(Registration.looking_for, F.data.in_({"gender_male", "gender_female", "gender_all"}))
async def update_looking_for(callback: CallbackQuery, state: FSMContext):
    mapping = {"gender_male": "male", "gender_female": "female", "gender_all": "all"}
    await update_profile(callback.from_user.id, looking_for=mapping[callback.data])
    await state.clear()
    await callback.message.edit_text("✅ Настройки поиска обновлены!", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(Registration.city)
async def update_city(message: Message, state: FSMContext):
    if len(message.text) > 128:
        await message.answer("Слишком длинное название. Попробуйте ещё:")
        return
    await update_profile(message.from_user.id, city=message.text.strip())
    await state.clear()
    await message.answer("✅ Город обновлён!", reply_markup=main_menu_keyboard())


@router.message(Registration.bio)
async def update_bio(message: Message, state: FSMContext):
    bio = message.text.strip()
    if bio == "-":
        bio = ""
    await update_profile(message.from_user.id, bio=bio)
    await state.clear()
    await message.answer("✅ Информация обновлена!", reply_markup=main_menu_keyboard())


@router.message(Registration.photos, F.photo)
async def update_photos(message: Message, state: FSMContext):
    from app.handlers.registration import photos_storage

    user_id = message.from_user.id
    if user_id not in photos_storage:
        photos_storage[user_id] = []

    photos_storage[user_id].append(message.photo[-1].file_id)

    if len(photos_storage[user_id]) >= 3:
        await update_profile(message.from_user.id, photos=photos_storage[user_id])
        photos_storage.pop(user_id, None)
        await state.clear()
        await message.answer("✅ Фото обновлены!", reply_markup=main_menu_keyboard())
    else:
        await message.answer(f"✅ Фото #{len(photos_storage[user_id])} добавлено. Ещё или /done.")


@router.message(Registration.photos, Command("done"))
async def done_update_photos(message: Message, state: FSMContext):
    from app.handlers.registration import photos_storage

    user_id = message.from_user.id
    photos = photos_storage.pop(user_id, [])
    await update_profile(message.from_user.id, photos=photos)
    await state.clear()
    await message.answer("✅ Фото обновлены!", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "request_verify")
async def request_verify(callback: CallbackQuery, state: FSMContext):
    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        await callback.answer("Сначала создайте анкету.", show_alert=True)
        return

    if profile.is_verified:
        await callback.message.edit_text(
            "✅ Ваша анкета уже верифицирована!",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    await state.set_state(Registration.photos)
    await state.update_data(edit_field="verification_photo")
    await callback.message.edit_text(
        "📸 Отправьте фото, на котором вы держите листок с написанным"
        "вашим Telegram @username.\n\n"
        "Это нужно для подтверждения, что вы реальный человек."
    )
    await callback.answer()


@router.message(Registration.photos, F.photo)
async def handle_verify_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("edit_field")
    if field == "verification_photo":
        photo_id = message.photo[-1].file_id
        await request_verification(message.from_user.id, photo_id)
        await state.clear()
        await message.answer(
            "✅ Фото отправлено на верификацию администратору. Ожидайте.",
            reply_markup=main_menu_keyboard(),
        )
        return

    from app.handlers.registration import photos_storage
    user_id = message.from_user.id
    if user_id not in photos_storage:
        photos_storage[user_id] = []
    photos_storage[user_id].append(message.photo[-1].file_id)
    if len(photos_storage[user_id]) >= 3:
        await update_profile(message.from_user.id, photos=photos_storage[user_id])
        photos_storage.pop(user_id, None)
        await state.clear()
        await message.answer("✅ Фото обновлены!", reply_markup=main_menu_keyboard())
    else:
        await message.answer(f"✅ Фото #{len(photos_storage[user_id])} добавлено. Ещё или /done.")


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    is_premium = user and user.is_premium
    await callback.message.edit_text(
        "⚙️ Настройки:",
        reply_markup=settings_keyboard(is_premium=is_premium),
    )
    await callback.answer()


@router.callback_query(F.data == "search_settings")
async def show_search_settings(callback: CallbackQuery):
    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        await callback.answer("Сначала создайте анкету.", show_alert=True)
        return

    looking_map = {"male": "Мужчин", "female": "Женщин", "all": "Всех"}
    text = (
        "🎯 Настройки поиска:\n\n"
        f"👫 Ищу: {looking_map.get(profile.looking_for, profile.looking_for)}\n"
        f"📏 Возраст: от {profile.age_min_preference} до {profile.age_max_preference}\n"
        f"🏙 Город: {profile.city}"
    )
    await callback.message.edit_text(text, reply_markup=search_settings_keyboard())
    await callback.answer()


@router.callback_query(F.data == "set_looking_for")
async def set_looking_for(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_field="looking_for")
    await state.set_state(Registration.looking_for)
    await callback.message.edit_text(
        "🔍 Кого ищем?",
        reply_markup=gender_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "set_age_min")
async def set_age_min(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_field="age_min_preference")
    await state.set_state(Registration.age)
    await callback.message.edit_text("📏 Минимальный возраст (от 16):")
    await callback.answer()


@router.callback_query(F.data == "set_age_max")
async def set_age_max(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_field="age_max_preference")
    await state.set_state(Registration.age)
    await callback.message.edit_text("📏 Максимальный возраст (до 99):")
    await callback.answer()


@router.callback_query(F.data == "set_city")
async def set_city(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_field="city")
    await state.set_state(Registration.city)
    await callback.message.edit_text("🏙 Введите город:")
    await callback.answer()
