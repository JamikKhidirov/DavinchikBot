import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, LabeledPrice
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import main_menu_keyboard
from app.services.premium_service import (
    PLANS, get_invoice_params, get_boost_invoice_params,
    activate_premium, activate_boost, can_boost,
)
from app.services.profile_service import (
    get_profile_by_telegram_id, get_user_by_telegram_id, is_banned,
)

router = Router()


@router.callback_query(F.data == "premium")
async def show_premium(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    is_premium = user and user.is_premium

    builder = InlineKeyboardBuilder()
    if is_premium:
        builder.button(text="🚀 Буст анкеты", callback_data="boost_anketa")
    builder.button(text="💎 1 месяц — 50 ⭐", callback_data="buy_premium_1m")
    builder.button(text="💎 3 месяца — 120 ⭐", callback_data="buy_premium_3m")
    builder.button(text="💎 Навсегда — 300 ⭐", callback_data="buy_premium_lifetime")
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(1)

    status = f"✅ Активен до {user.premium_expires_at.strftime('%d.%m.%Y')}" if is_premium else "❌ Не активен"

    text = (
        "⭐ <b>Премиум-доступ</b>\n\n"
        f"Статус: {status}\n\n"
        "💎 <b>Безлимитные лайки</b> — ставь сколько хочешь\n"
        "🚀 <b>Буст анкеты</b> — ты в начале поиска\n"
        "👀 <b>Кто лайкнул</b> — смотри список\n"
        "🎨 <b>Приоритетная поддержка</b>\n\n"
        "Оплата через ⭐ Telegram Stars"
    )
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("buy_premium_"))
async def buy_premium(callback: CallbackQuery):
    plan_id = callback.data.replace("buy_premium_", "")
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("План не найден", show_alert=True)
        return

    params = get_invoice_params(plan_id, callback.from_user.id)
    if not params:
        await callback.answer("Ошибка создания счёта", show_alert=True)
        return

    await callback.message.delete()
    await callback.message.answer_invoice(**params)
    await callback.answer()


@router.callback_query(F.data == "boost_anketa")
async def boost_anketa(callback: CallbackQuery):
    if await is_banned(callback.from_user.id):
        await callback.answer("🚫 Вы забанены.", show_alert=True)
        return

    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        await callback.answer("Сначала создайте анкету.", show_alert=True)
        return

    if profile.is_boosted and profile.boost_expires_at and profile.boost_expires_at > datetime.datetime.utcnow():
        left = (profile.boost_expires_at - datetime.datetime.utcnow()).days
        await callback.message.edit_text(
            f"🚀 Буст уже активен! Осталось {left} дн.\n"
            "Можно продлить ещё на 7 дней.",
        )
        await callback.answer()
        return

    params = get_boost_invoice_params(callback.from_user.id)
    await callback.message.delete()
    await callback.message.answer_invoice(**params)
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    telegram_id = message.from_user.id

    if payload.startswith("premium_"):
        parts = payload.split("_")
        plan_id = parts[1]
        ok = await activate_premium(telegram_id, plan_id)
        if ok:
            plan = PLANS.get(plan_id, {})
            await message.answer(
                f"✅ Премиум на {plan.get('label', '')} активирован!\n\n"
                "💎 Безлимитные лайки\n"
                "🚀 Буст анкеты\n"
                "👀 Список лайкнувших\n\n"
                "Спасибо за поддержку! ❤️",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await message.answer("❌ Ошибка активации.", reply_markup=main_menu_keyboard())

    elif payload.startswith("boost_"):
        ok = await activate_boost(telegram_id)
        if ok:
            await message.answer(
                "🚀 Буст анкеты активирован на 7 дней!\n"
                "Твоя анкета будет показываться одной из первых.",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await message.answer("❌ Ошибка активации буста.", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "blocked_list")
async def show_blocked(callback: CallbackQuery):
    from app.services.block_service import get_blocked_users

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
