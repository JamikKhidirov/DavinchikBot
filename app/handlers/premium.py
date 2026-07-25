from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import main_menu_keyboard

router = Router()


@router.callback_query(F.data == "premium")
async def show_premium(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Оформить Премиум", callback_data="premium_buy")
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(1)

    text = (
        "⭐ <b>Премиум-доступ</b>\n\n"
        "💎 Безлимитные лайки — ставь сколько хочешь\n"
        "👀 Смотри кто тебя лайкнул\n"
        "🚀 Буст анкеты — ты в начале поиска\n"
        "🎨 Эксклюзивные стили\n\n"
        "Скоро будет доступно!\n"
        "Следи за обновлениями."
    )
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "premium_buy")
async def premium_buy(callback: CallbackQuery):
    await callback.message.edit_text(
        "💎 Оплата Премиум пока в разработке.\n\n"
        "Скоро вы сможете оформить подписку прямо в боте!",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "blocked_list")
async def show_blocked(callback: CallbackQuery):
    from app.services.block_service import get_blocked_users
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    blocked = await get_blocked_users(callback.from_user.id)

    if not blocked:
        await callback.message.edit_text(
            "🚫 У вас нет заблокированных пользователей.",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for b in blocked:
        builder.button(
            text=f"❌ Разблокировать {b['name']}",
            callback_data=f"unblock_{b['id']}",
        )
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "🚫 Заблокированные пользователи:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("unblock_"))
async def process_unblock(callback: CallbackQuery):
    from app.services.block_service import unblock_user

    target_id = int(callback.data.split("_")[1])
    await unblock_user(callback.from_user.id, target_id)

    await callback.message.edit_text(
        "✅ Пользователь разблокирован.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
