from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import (
    my_gender_keyboard, gender_keyboard, confirm_keyboard, main_menu_keyboard,
)
from app.models.profile import INTEREST_CHOICES
from app.services.profile_service import create_profile, has_profile, get_or_create_user
from app.states.registration import Registration

router = Router()


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    if await has_profile(message.from_user.id):
        await message.answer(
            "У вас уже есть анкета!",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.set_state(Registration.name)
    await message.answer(
        "📝 Давай создадим твою анкету!\n\n"
        "Напиши своё имя:"
    )


@router.message(Registration.name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 64:
        await message.answer("Имя слишком длинное (макс 64 символа). Попробуй ещё:")
        return

    await state.update_data(name=message.text)
    await state.set_state(Registration.age)
    await message.answer("🎂 Сколько тебе лет? (от 16 до 99)")


@router.message(Registration.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < 16 or age > 99:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введи число от 16 до 99:")
        return

    await state.update_data(age=age)
    await state.set_state(Registration.gender)
    await message.answer("⚧ Твой пол:", reply_markup=my_gender_keyboard())


@router.callback_query(Registration.gender, F.data.in_({"mygender_male", "mygender_female"}))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    gender = "male" if callback.data == "mygender_male" else "female"
    await state.update_data(gender=gender)
    await state.set_state(Registration.looking_for)
    try:
        await callback.message.edit_text("🔍 Кого ты ищешь?", reply_markup=gender_keyboard())
    except Exception:
        await callback.message.answer("🔍 Кого ты ищешь?", reply_markup=gender_keyboard())


@router.callback_query(Registration.looking_for, F.data.in_({"gender_male", "gender_female", "gender_all"}))
async def process_looking_for(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    mapping = {"gender_male": "male", "gender_female": "female", "gender_all": "all"}
    await state.update_data(looking_for=mapping[callback.data])
    await state.set_state(Registration.city)
    try:
        await callback.message.edit_text("🏙 В каком городе ты живёшь?")
    except Exception:
        await callback.message.answer("🏙 В каком городе ты живёшь?")


@router.message(Registration.city)
async def process_city(message: Message, state: FSMContext):
    if len(message.text) > 128:
        await message.answer("Название города слишком длинное (макс 128 символов). Попробуй ещё:")
        return
    await state.update_data(city=message.text.strip())
    await state.set_state(Registration.bio)
    await message.answer(
        "📄 Напиши немного о себе (что ты ищешь, увлечения, интересы):\n\n"
        "Или отправь '-' чтобы пропустить."
    )


@router.message(Registration.bio)
async def process_bio(message: Message, state: FSMContext):
    bio = message.text.strip() if message.text.strip() != "-" else ""
    await state.update_data(bio=bio)
    await state.set_state(Registration.interests)
    from app.keyboards.profile import interests_keyboard
    await message.answer(
        "🎯 Выбери свои интересы (можно несколько):\n"
        "Нажимай на кнопки, потом нажми ✅ Готово.",
        reply_markup=interests_keyboard([]),
    )


@router.callback_query(Registration.interests, F.data.startswith("interest_"))
async def process_interest_toggle(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    selected = list(data.get("interests", []))
    interest = callback.data.replace("interest_", "")
    if interest in selected:
        selected.remove(interest)
    else:
        selected.append(interest)
    await state.update_data(interests=selected)
    from app.keyboards.profile import interests_keyboard
    try:
        await callback.message.edit_reply_markup(reply_markup=interests_keyboard(selected))
    except Exception:
        pass


@router.callback_query(Registration.interests, F.data == "interests_done")
async def process_interests_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Registration.photos)
    await callback.message.answer(
        "📸 Отправь до 3 фото и/или видео (по одному).\n"
        "Когда закончишь, нажми /done.\n"
        "Или отправь '-' чтобы пропустить."
    )


media_storage = {}


@router.message(Registration.photos, F.photo)
async def process_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in media_storage:
        media_storage[user_id] = {"photos": [], "videos": []}

    media_storage[user_id]["photos"].append(message.photo[-1].file_id)
    total = len(media_storage[user_id]["photos"]) + len(media_storage[user_id]["videos"])

    if total >= 3:
        await state.update_data(photos=media_storage[user_id]["photos"], videos=media_storage[user_id]["videos"])
        media_storage.pop(user_id, None)
        await show_confirm(message, state)
    else:
        await message.answer(f"✅ Фото #{len(media_storage[user_id]['photos'])} добавлено. Можешь отправить ещё или нажми /done.")


@router.message(Registration.photos, F.video)
async def process_video(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in media_storage:
        media_storage[user_id] = {"photos": [], "videos": []}

    media_storage[user_id]["videos"].append(message.video.file_id)
    total = len(media_storage[user_id]["photos"]) + len(media_storage[user_id]["videos"])

    if total >= 3:
        await state.update_data(photos=media_storage[user_id]["photos"], videos=media_storage[user_id]["videos"])
        media_storage.pop(user_id, None)
        await show_confirm(message, state)
    else:
        await message.answer(f"✅ Видео #{len(media_storage[user_id]['videos'])} добавлено. Можешь отправить ещё или нажми /done.")


@router.message(Registration.photos, Command("done"))
async def done_photos(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = media_storage.pop(user_id, {"photos": [], "videos": []})
    await state.update_data(photos=data["photos"], videos=data["videos"])
    await show_confirm(message, state)


@router.message(Registration.photos)
async def skip_photos(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "-":
        await state.update_data(photos=[], videos=[])
        await show_confirm(message, state)


async def show_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    gender_map = {"male": "👨 Мужской", "female": "👩 Женский"}
    looking_map = {"male": "👨 Мужчин", "female": "👩 Женщин", "all": "👫 Всех"}
    interests = data.get("interests", [])
    interests_text = ", ".join(interests) if interests else "—"

    text = (
        "📋 Проверь свою анкету:\n\n"
        f"📝 Имя: {data.get('name')}\n"
        f"🎂 Возраст: {data.get('age')}\n"
        f"⚧ Пол: {gender_map.get(data.get('gender', ''), data.get('gender'))}\n"
        f"🔍 Ищу: {looking_map.get(data.get('looking_for', ''), data.get('looking_for'))}\n"
        f"🏙 Город: {data.get('city')}\n"
        f"📄 О себе: {data.get('bio') or '—'}\n"
        f"🎯 Интересы: {interests_text}\n"
        f"📸 Фото: {len(data.get('photos', []))} | 🎬 Видео: {len(data.get('videos', []))}\n\n"
        "Всё верно?"
    )
    await state.set_state(Registration.confirm)
    await message.answer(text, reply_markup=confirm_keyboard())


@router.callback_query(Registration.confirm, F.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()

    await get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    try:
        profile = await create_profile(
            telegram_id=callback.from_user.id,
            name=data["name"],
            age=data["age"],
            gender=data["gender"],
            looking_for=data["looking_for"],
            city=data["city"],
            bio=data.get("bio", ""),
            photos=data.get("photos", []),
            videos=data.get("videos", []),
            interests=data.get("interests", []),
        )
    except Exception:
        await callback.message.answer("❌ Ошибка при создании анкеты. Попробуйте позже.")
        await state.clear()
        return

    from app.database import async_session
    from sqlalchemy import select
    from app.models import User
    async with async_session() as session:
        user = await session.execute(select(User).where(User.id == profile.user_id))
        user = user.scalar_one_or_none()
        if user and user.referral_bonus_claimed:
            profile.is_referral_badge = True
            await session.commit()

    await state.clear()
    await safe_edit_reg(callback,
        "✅ Анкета создана! Теперь ты можешь смотреть анкеты и находить пару!",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(Registration.confirm, F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("Давай начнём заново. Нажми /register")
    except Exception:
        await callback.message.answer("Давай начнём заново. Нажми /register")


async def safe_edit_reg(callback, text, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)
