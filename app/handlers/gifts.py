from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import main_menu_keyboard
from app.models.gift import GIFT_OPTIONS
from app.services.gift_service import (
    send_gift, get_gift_invoice_params, get_received_gifts,
)
from app.services.profile_service import get_user_by_id, is_banned

router = Router()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data.startswith("send_gift_"))
async def show_gift_choices(callback: CallbackQuery):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    target_id = int(callback.data.replace("send_gift_", ""))

    builder = InlineKeyboardBuilder()
    for key, info in GIFT_OPTIONS.items():
        builder.button(
            text=f"{info['label']} — {info['stars']} ⭐",
            callback_data=f"gift_buy_{key}_{target_id}",
        )
    builder.button(text="🔙 Назад", callback_data="my_matches")
    builder.adjust(1)

    await safe_edit(callback, "🎁 Выберите подарок:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("gift_buy_"))
async def buy_gift(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    gift_type = parts[2]
    target_id = int(parts[3])

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
    if not gifts:
        await safe_edit(callback,
            "🎁 У вас пока нет подарков.",
            reply_markup=main_menu_keyboard(),
        )
        return

    text = "🎁 Ваши подарки:\n\n"
    for g in gifts:
        text += f"• {g['label']} от {g['from_name']}"
        if g.get("message"):
            text += f" — {g['message']}"
        text += "\n"

    await safe_edit(callback, text, reply_markup=main_menu_keyboard())
