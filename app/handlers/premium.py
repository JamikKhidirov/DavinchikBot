import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import main_menu_keyboard
from app.services.premium_service import (
    PLANS, get_invoice_params, get_boost_invoice_params,
    activate_premium, activate_boost, can_boost,
)
from app.services.profile_service import (
    get_profile_by_telegram_id, get_user_by_telegram_id, is_banned,
)

UTC = datetime.timezone.utc
router = Router()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "premium")
async def show_premium(callback: CallbackQuery):
    await callback.answer()
    user = await get_user_by_telegram_id(callback.from_user.id)
    is_premium = user and user.is_premium

    builder = InlineKeyboardBuilder()
    if is_premium:
        builder.button(text="🚀 Буст анкеты", callback_data="boost_anketa")
    builder.button(text="💎 1 месяц — 50 ⭐", callback_data="buy_premium_1m")
    builder.button(text="💎 3 месяца — 120 ⭐", callback_data="buy_premium_3m")
    builder.button(text="💎 Навсегда — 300 ⭐", callback_data="buy_premium_lifetime")
    builder.button(text="📢 Рекламный баннер на 30 дней — 200 ⭐", callback_data="buy_ad_banner")
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(1)

    if is_premium and user and user.premium_expires_at:
        status = f"✅ Активен до {user.premium_expires_at.strftime('%d.%m.%Y')}"
    else:
        status = "❌ Не активен"

    text = (
        "⭐ <b>Премиум-доступ</b>\n\n"
        f"Статус: {status}\n\n"
        "💎 <b>Безлимитные лайки</b> — ставь сколько хочешь\n"
        "🚀 <b>Буст анкеты</b> — ты в начале поиска\n"
        "👀 <b>Кто лайкнул</b> — смотри список\n"
        "🎨 <b>Приоритетная поддержка</b>\n\n"
        "—\n"
        "📢 <b>Рекламный баннер</b> — 200 ⭐ за 30 дней\n"
        "Показывается пользователям в ленте поиска\n\n"
        "Оплата через ⭐ Telegram Stars"
    )
    await safe_edit(callback, text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("buy_premium_"))
async def buy_premium(callback: CallbackQuery):
    await callback.answer()
    plan_id = callback.data.replace("buy_premium_", "")
    plan = PLANS.get(plan_id)
    if not plan:
        return

    params = get_invoice_params(plan_id, callback.from_user.id)
    if not params:
        return

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_invoice(**params)


@router.callback_query(F.data == "buy_ad_banner")
async def buy_ad_banner(callback: CallbackQuery):
    await callback.answer()
    from app.services.ads_purchase_service import get_ad_banner_invoice_params
    params = get_ad_banner_invoice_params(callback.from_user.id)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_invoice(**params)


@router.callback_query(F.data == "boost_anketa")
async def boost_anketa(callback: CallbackQuery):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        return

    profile = await get_profile_by_telegram_id(callback.from_user.id)
    if profile is None:
        return

    if profile.is_boosted and profile.boost_expires_at and profile.boost_expires_at > datetime.datetime.now(UTC):
        left = (profile.boost_expires_at - datetime.datetime.now(UTC)).days
        await safe_edit(callback,
            f"🚀 Буст уже активен! Осталось {left} дн.\n"
            "Можно продлить ещё на 7 дней.",
        )
        return

    params = get_boost_invoice_params(callback.from_user.id)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_invoice(**params)


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

    elif payload.startswith("gift_"):
        parts = payload.split("_", 4)
        gift_type = parts[1]
        to_user_id = int(parts[3])
        msg_text = parts[4] if len(parts) > 4 else ""
        from app.services.gift_service import send_gift
        gift = await send_gift(telegram_id, to_user_id, gift_type, msg_text)
        if gift:
            from app.models.gift import GIFT_OPTIONS
            gift_info = GIFT_OPTIONS.get(gift_type, {})
            await message.answer(
                f"✅ Подарок {gift_info.get('label', gift_type)} отправлен!",
                reply_markup=main_menu_keyboard(),
            )
            try:
                to_user = await get_user_by_id(to_user_id)
                if to_user:
                    my_profile = await get_profile_by_telegram_id(telegram_id)
                    name = my_profile.name if my_profile else "Пользователь"
                    await message.bot.send_message(
                        to_user.telegram_id,
                        f"🎁 Вы получили подарок {gift_info.get('label', gift_type)} от {name}!"
                        + (f"\n💬 {msg_text}" if msg_text else ""),
                    )
            except Exception:
                pass
        else:
            await message.answer("❌ Ошибка отправки подарка.", reply_markup=main_menu_keyboard())

    elif payload.startswith("ad_banner_"):
        await message.answer(
            "✅ Рекламный баннер оплачен! Скоро он появится в ленте пользователей.\n"
            "Свяжитесь с администратором для уточнения деталей.",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(F.data == "blocked_list")
async def show_blocked(callback: CallbackQuery):
    await callback.answer()
    from app.services.block_service import get_blocked_users

    blocked = await get_blocked_users(callback.from_user.id)

    if not blocked:
        await safe_edit(callback, "🚫 У вас нет заблокированных пользователей.", reply_markup=main_menu_keyboard())
        return

    builder = InlineKeyboardBuilder()
    for b in blocked:
        builder.button(
            text=f"❌ Разблокировать {b['name']}",
            callback_data=f"unblock_{b['id']}",
        )
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(1)

    await safe_edit(callback, "🚫 Заблокированные пользователи:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("unblock_"))
async def process_unblock(callback: CallbackQuery):
    await callback.answer()
    from app.services.block_service import unblock_user

    target_id = int(callback.data.split("_")[1])
    await unblock_user(callback.from_user.id, target_id)
    await safe_edit(callback, "✅ Пользователь разблокирован.", reply_markup=main_menu_keyboard())
