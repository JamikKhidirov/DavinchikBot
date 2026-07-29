from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import main_menu_keyboard
from app.models.gift import GIFT_OPTIONS
from app.services.gift_service import (
    send_gift, get_gift_invoice_params, get_received_gifts,
)
from app.services.profile_service import get_user_by_id, is_banned, get_user_by_telegram_id

router = Router()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


async def gift_catalog_keyboard(source: str, target_id: int = None):
    builder = InlineKeyboardBuilder()
    for key, info in GIFT_OPTIONS.items():
        builder.button(
            text=f"{info['label']} — {info['stars']} ⭐",
            callback_data=f"gift_buy_{source}_{key}_{target_id or 0}",
        )
    back_data = "main_menu" if source == "self" else "my_matches"
    builder.button(text="🔙 Назад", callback_data=back_data)
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data.startswith("send_gift_"))
async def show_gift_choices(callback: CallbackQuery):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    target_id = int(callback.data.replace("send_gift_", ""))
    kb = await gift_catalog_keyboard("user", target_id)
    try:
        await callback.message.edit_text("🎁 Выберите подарок:", reply_markup=kb)
    except Exception:
        await callback.message.answer("🎁 Выберите подарок:", reply_markup=kb)


@router.callback_query(F.data == "gift_shop")
async def gift_shop_self(callback: CallbackQuery):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    kb = await gift_catalog_keyboard("self")
    text = (
        "🎁 Магазин подарков\n\n"
        "Купи подарок себе или отправь другому!\n"
        "Оплата через ⭐ Telegram Stars\n\n"
        "Выбери подарок:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("gift_buy_"))
async def buy_gift(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_", 4)
    source = parts[2]
    gift_type = parts[3]
    target_id = int(parts[4])

    if source == "self":
        my_user = await get_user_by_telegram_id(callback.from_user.id)
        if my_user is None:
            return
        target_id = my_user.id

    params = get_gift_invoice_params(gift_type, callback.from_user.id, target_id)
    if params is None:
        return

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_invoice(**params)


@router.callback_query(F.data == "my_gifts")
async def show_my_gifts(callback: CallbackQuery):
    await callback.answer()
    gifts = await get_received_gifts(callback.from_user.id)

    text = "🎁 Мои подарки\n\n"
    if gifts:
        for g in gifts:
            text += f"• {g['label']} от {g['from_name']}"
            if g.get("message"):
                text += f" — {g['message']}"
            text += "\n"
    else:
        text += "У вас пока нет подарков.\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Магазин подарков", callback_data="gift_shop")
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(1)

    await safe_edit(callback, text, reply_markup=builder.as_markup())
