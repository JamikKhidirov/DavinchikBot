from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from app.keyboards.profile import main_menu_keyboard
from app.services.profile_service import get_or_create_user, has_profile, is_banned, update_last_active

router = Router()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.message(Command("start"))
async def cmd_start(message: Message):
    if await is_banned(message.from_user.id):
        await message.answer("🚫 Вы забанены в боте.")
        return

    await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )

    await update_last_active(message.from_user.id)

    if await has_profile(message.from_user.id):
        await message.answer(
            f"👋 С возвращением, {message.from_user.first_name}!\n\n"
            f"🔍 Смотри анкеты, ставь лайки и находи пару!",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            "👋 Добро пожаловать в бот знакомств!\n\n"
            "Для начала нужно создать анкету. Нажми /register чтобы начать."
        )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    if await is_banned(message.from_user.id):
        await message.answer("🚫 Вы забанены в боте.")
        return

    if not await has_profile(message.from_user.id):
        await message.answer("Сначала создайте анкету через /register")
        return

    await message.answer("🏠 Главное меню:", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены в боте.")
        return

    if not await has_profile(callback.from_user.id):
        await callback.message.answer("Сначала создайте анкету через /register")
        return

    await safe_edit(callback, "🏠 Главное меню:", reply_markup=main_menu_keyboard())
