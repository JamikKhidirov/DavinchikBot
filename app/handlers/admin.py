from functools import wraps

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.config import config
from app.keyboards.admin import admin_keyboard, ads_management_keyboard, admin_grant_keyboard
from app.keyboards.profile import main_menu_keyboard, confirm_keyboard
from app.services.profile_service import (
    get_all_users, get_user_by_telegram_id,
    is_admin, ban_user, unban_user, has_profile,
    get_pending_verifications, verify_profile, reject_verification,
)
from app.services.ad_service import get_all_ads, get_ad_by_id, toggle_ad
from app.states.admin_states import AddAdvertisement, Broadcast

router = Router()


def admin_required(func):
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
        if user_id not in config.admin_ids_list and not await is_admin(user_id):
            if isinstance(event, CallbackQuery):
                await event.answer("Нет доступа", show_alert=True)
            else:
                await event.answer("🚫 У вас нет доступа к админ-панели.")
            return
        return await func(event, *args, **kwargs)
    return wrapper


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.message(Command("admin"))
@admin_required
async def cmd_admin(message: Message):
    from app.services.profile_service import set_admin
    await set_admin(message.from_user.id, True)
    text = (
        "👑 Админ-панель:\n\n"
        f"📢 Частота рекламы: каждые {config.swipe_before_ad} свайпов"
    )
    await message.answer(text, reply_markup=admin_keyboard())


@router.message(Command("admin_ban"))
@admin_required
async def admin_ban_cmd(message: Message):
    from app.services.profile_service import ban_user
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажи Telegram ID: /admin_ban 123456789")
        return
    try:
        tid = int(args[1].strip())
    except ValueError:
        await message.answer("Неверный ID. Укажи числовой Telegram ID.")
        return
    ok = await ban_user(tid)
    if ok:
        await message.answer(f"✅ Пользователь {tid} забанен.")
    else:
        await message.answer(f"❌ Пользователь {tid} не найден.")


@router.message(Command("admin_unban"))
@admin_required
async def admin_unban_cmd(message: Message):
    from app.services.profile_service import unban_user
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажи Telegram ID: /admin_unban 123456789")
        return
    try:
        tid = int(args[1].strip())
    except ValueError:
        await message.answer("Неверный ID.")
        return
    ok = await unban_user(tid)
    if ok:
        await message.answer(f"✅ Пользователь {tid} разбанен.")
    else:
        await message.answer(f"❌ Пользователь {tid} не найден.")


@router.message(Command("admin_userinfo"))
@admin_required
async def admin_userinfo_cmd(message: Message):
    from app.services.profile_service import get_user_by_telegram_id, get_profile_by_telegram_id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажи Telegram ID: /admin_userinfo 123456789")
        return
    try:
        tid = int(args[1].strip())
    except ValueError:
        await message.answer("Неверный ID.")
        return
    user = await get_user_by_telegram_id(tid)
    if not user:
        await message.answer(f"❌ Пользователь {tid} не найден.")
        return
    profile = await get_profile_by_telegram_id(tid)
    text = (
        f"👤 Информация о пользователе\n\n"
        f"ID: {user.id}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Username: @{user.username or '—'}\n"
        f"Имя: {user.first_name or '—'} {user.last_name or ''}\n"
        f"Админ: {'✅' if user.is_admin else '❌'}\n"
        f"Забанен: {'✅' if user.is_banned else '❌'}\n"
        f"Премиум: {'✅' if user.is_premium else '❌'}\n"
        f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y') if user.created_at else '—'}\n"
    )
    if profile:
        text += (
            f"\n📝 Анкета:\n"
            f"Имя: {profile.name}\n"
            f"Возраст: {profile.age}\n"
            f"Город: {profile.city}\n"
            f"Активна: {'✅' if profile.is_active else '❌'}\n"
            f"Верифицирована: {'✅' if profile.is_verified else '❌'}\n"
            f"Просмотров: {profile.views_count}\n"
        )
    else:
        text += "\n📝 Анкета: отсутствует"
    await message.answer(text)


@router.message(Command("admin_ad_freq"))
@admin_required
async def admin_ad_freq_cmd(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(f"Текущая частота рекламы: каждые {config.swipe_before_ad} свайпов.\nИспользование: /admin_ad_freq <число>")
        return
    try:
        val = int(args[1].strip())
        if val < 1:
            raise ValueError
    except ValueError:
        await message.answer("Укажите число больше 0.")
        return
    config.swipe_before_ad = val
    await message.answer(f"✅ Частота рекламы изменена: каждые {val} свайпов.")


@router.message(Command("admin_deleteprofile"))
@admin_required
async def admin_deleteprofile_cmd(message: Message):
    from app.services.profile_service import get_user_by_telegram_id
    from app.database import async_session
    from sqlalchemy import select, delete
    from app.models import Profile, Like, Match, Block, Complaint
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажи Telegram ID: /admin_deleteprofile 123456789")
        return
    try:
        tid = int(args[1].strip())
    except ValueError:
        await message.answer("Неверный ID.")
        return
    user = await get_user_by_telegram_id(tid)
    if not user:
        await message.answer(f"❌ Пользователь {tid} не найден.")
        return
    uid = user.id
    async with async_session() as session:
        await session.execute(delete(Like).where((Like.from_user_id == uid) | (Like.to_user_id == uid)))
        await session.execute(delete(Match).where((Match.user1_id == uid) | (Match.user2_id == uid)))
        await session.execute(delete(Block).where((Block.user_id == uid) | (Block.blocked_user_id == uid)))
        await session.execute(delete(Complaint).where((Complaint.from_user_id == uid) | (Complaint.complained_user_id == uid)))
        await session.execute(delete(Profile).where(Profile.user_id == uid))
        await session.commit()
    await message.answer(f"✅ Анкета и все данные пользователя {tid} удалены.")


@router.callback_query(F.data == "admin_menu")
@admin_required
async def admin_menu(callback: CallbackQuery):
    await callback.answer()
    await safe_edit(callback, "👑 Админ-панель:", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_stats")
@admin_required
async def admin_stats(callback: CallbackQuery):
    await callback.answer()
    from app.database import async_session
    from sqlalchemy import select, func
    from app.models import User, Profile, Like, Match, Complaint

    async with async_session() as session:
        users_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
        profiles_count = (await session.execute(select(func.count(Profile.id)))).scalar() or 0
        likes_count = (await session.execute(select(func.count(Like.id)))).scalar() or 0
        matches_count = (await session.execute(select(func.count(Match.id)))).scalar() or 0
        complaints_count = (await session.execute(select(func.count(Complaint.id)).where(Complaint.status == "pending"))).scalar() or 0

    text = (
        "📊 Статистика:\n\n"
        f"👥 Всего пользователей: {users_count}\n"
        f"📝 Анкет: {profiles_count}\n"
        f"❤️ Лайков: {likes_count}\n"
        f"💕 Совпадений: {matches_count}\n"
        f"🚫 Жалоб (ожидает): {complaints_count}"
    )
    await safe_edit(callback, text, reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_ads")
@admin_required
async def admin_ads(callback: CallbackQuery):
    await callback.answer()
    await safe_edit(callback, "📢 Управление рекламой:", reply_markup=ads_management_keyboard())


@router.callback_query(F.data == "admin_add_ad")
@admin_required
async def admin_add_ad(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddAdvertisement.text)
    try:
        await callback.message.edit_text("📢 Введите текст рекламы:")
    except Exception:
        await callback.message.answer("📢 Введите текст рекламы:")


@router.message(AddAdvertisement.text)
async def ad_text_received(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(AddAdvertisement.photo)
    await message.answer("📸 Отправьте фото для рекламы (или /skip чтобы без фото):")


@router.message(AddAdvertisement.photo, F.photo)
async def ad_photo_received(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(AddAdvertisement.button_text)
    await message.answer("🔘 Текст кнопки (или /skip):")


@router.message(AddAdvertisement.photo, Command("skip"))
async def ad_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await state.set_state(AddAdvertisement.button_text)
    await message.answer("🔘 Текст кнопки (или /skip):")


@router.message(AddAdvertisement.button_text, Command("skip"))
async def ad_button_skip(message: Message, state: FSMContext):
    await state.update_data(button_text=None, button_url=None)
    await save_ad(message, state)


@router.message(AddAdvertisement.button_text)
async def ad_button_text_received(message: Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await state.set_state(AddAdvertisement.button_url)
    await message.answer("🔗 Ссылка для кнопки (или /skip):")


@router.message(AddAdvertisement.button_url, Command("skip"))
async def ad_url_skip(message: Message, state: FSMContext):
    await save_ad(message, state)


@router.message(AddAdvertisement.button_url)
async def ad_url_received(message: Message, state: FSMContext):
    await state.update_data(button_url=message.text)
    await save_ad(message, state)


async def save_ad(message: Message, state: FSMContext):
    from app.services.ad_service import create_ad
    data = await state.get_data()
    await create_ad(
        photo_id=data.get("photo_id"),
        text=data["text"],
        button_text=data.get("button_text"),
        button_url=data.get("button_url"),
    )
    await state.clear()
    await message.answer("✅ Реклама создана!", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_list_ads")
@admin_required
async def admin_list_ads(callback: CallbackQuery):
    await callback.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    ads = await get_all_ads()
    if not ads:
        await safe_edit(callback, "Рекламы пока нет.", reply_markup=ads_management_keyboard())
        return

    builder = InlineKeyboardBuilder()
    for ad in ads:
        status = "✅" if ad.is_active else "❌"
        preview = ad.text[:30] + "..." if len(ad.text) > 30 else ad.text
        builder.button(
            text=f"{status} {preview} (показов: {ad.impressions_count})",
            callback_data=f"ad_detail_{ad.id}",
        )
    builder.button(text="🔙 Назад", callback_data="admin_ads")
    builder.adjust(1)

    await safe_edit(callback, "📋 Список рекламы:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("ad_detail_"))
@admin_required
async def ad_detail(callback: CallbackQuery):
    await callback.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    ad_id = int(callback.data.replace("ad_detail_", ""))
    ad = await get_ad_by_id(ad_id)
    if ad is None:
        return

    text = (
        f"📢 Реклама #{ad.id}\n\n"
        f"Текст: {ad.text}\n"
        f"Фото: {'✅' if ad.photo_id else '❌'}\n"
        f"Кнопка: {ad.button_text or '—'}\n"
        f"Ссылка: {ad.button_url or '—'}\n"
        f"Статус: {'✅ Активна' if ad.is_active else '❌ Неактивна'}\n"
        f"Показов: {ad.impressions_count}\n"
        f"Кликов: {ad.clicks_count}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(
        text="❌ Отключить" if ad.is_active else "✅ Включить",
        callback_data=f"ad_toggle_{ad.id}",
    )
    builder.button(text="📨 Отправить всем", callback_data=f"ad_broadcast_{ad.id}")
    builder.button(text="🔙 Назад", callback_data="admin_list_ads")
    builder.adjust(1)

    await safe_edit(callback, text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("ad_toggle_"))
@admin_required
async def ad_toggle(callback: CallbackQuery):
    await callback.answer()
    ad_id = int(callback.data.replace("ad_toggle_", ""))
    new_status = await toggle_ad(ad_id)
    if new_status is None:
        return
    status_text = "включена" if new_status else "отключена"
    await safe_edit(callback, f"✅ Реклама #{ad_id} {status_text}!", reply_markup=admin_keyboard())


@router.callback_query(F.data.startswith("ad_broadcast_"))
@admin_required
async def ad_broadcast(callback: CallbackQuery):
    await callback.answer()
    ad_id = int(callback.data.replace("ad_broadcast_", ""))
    ad = await get_ad_by_id(ad_id)
    if ad is None:
        return

    from app.services.notification_service import send_broadcast
    from app.services.profile_service import get_all_users

    users = await get_all_users()
    active_users = [u.telegram_id for u in users if not u.is_banned]

    text = f"📢 Реклама\n\n{ad.text}"
    if ad.button_text and ad.button_url:
        text += f"\n\n{ad.button_text}: {ad.button_url}"

    success, failed = await send_broadcast(callback.bot, active_users, text=text, photo_id=ad.photo_id)
    await safe_edit(callback,
        f"📨 Реклама #{ad_id} разослана!\n"
        f"✅ Отправлено: {success}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(F.data == "admin_users")
@admin_required
async def admin_users(callback: CallbackQuery):
    await callback.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    users = await get_all_users()
    text = f"👥 Всего пользователей: {len(users)}\n\n"

    for u in users[:20]:
        name = u.first_name or u.username or str(u.telegram_id)
        status = "🚫" if u.is_banned else "⭐" if u.is_premium else "👤"
        has_p = "📝" if await has_profile(u.telegram_id) else ""
        text += f"{status} {has_p} {name} (id:{u.id})\n"

    if len(users) > 20:
        text += f"\n... и ещё {len(users) - 20}"

    await safe_edit(callback, text, reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_complaints")
@admin_required
async def admin_complaints(callback: CallbackQuery):
    await callback.answer()
    from app.database import async_session
    from sqlalchemy import select
    from app.models import Complaint, User
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with async_session() as session:
        result = await session.execute(
            select(Complaint).where(Complaint.status == "pending").order_by(Complaint.created_at.desc())
        )
        complaints = list(result.scalars().all())

    if not complaints:
        await safe_edit(callback, "🚫 Нет новых жалоб.", reply_markup=admin_keyboard())
        return

    builder = InlineKeyboardBuilder()
    for c in complaints[:10]:
        builder.button(
            text=f"Жалоба #{c.id} от user#{c.from_user_id} на user#{c.complained_user_id}",
            callback_data=f"complaint_view_{c.id}",
        )
    builder.button(text="🔙 Назад", callback_data="admin_menu")
    builder.adjust(1)

    await safe_edit(callback, f"🚫 Жалобы ({len(complaints)}):", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("complaint_view_"))
@admin_required
async def complaint_view(callback: CallbackQuery):
    await callback.answer()
    from app.database import async_session
    from sqlalchemy import select
    from app.models import Complaint
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    complaint_id = int(callback.data.replace("complaint_view_", ""))
    async with async_session() as session:
        result = await session.execute(select(Complaint).where(Complaint.id == complaint_id))
        c = result.scalar_one_or_none()

    if c is None:
        return

    text = (
        f"🚫 Жалоба #{c.id}\n\n"
        f"От: user#{c.from_user_id}\n"
        f"На: user#{c.complained_user_id}\n"
        f"Причина: {c.reason}\n"
        f"Дата: {c.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Статус: {c.status}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Закрыть жалобу", callback_data=f"complaint_close_{c.id}")
    builder.button(text="🚫 Забанить user#{c.complained_user_id}", callback_data=f"complaint_ban_{c.complained_user_id}")
    builder.button(text="🔙 Назад", callback_data="admin_complaints")
    builder.adjust(1)

    await safe_edit(callback, text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("complaint_close_"))
@admin_required
async def complaint_close(callback: CallbackQuery):
    await callback.answer()
    from app.database import async_session
    from sqlalchemy import select
    from app.models import Complaint

    complaint_id = int(callback.data.replace("complaint_close_", ""))
    async with async_session() as session:
        result = await session.execute(select(Complaint).where(Complaint.id == complaint_id))
        c = result.scalar_one_or_none()
        if c:
            c.status = "resolved"
            await session.commit()

    await safe_edit(callback, "✅ Жалоба закрыта.", reply_markup=admin_keyboard())


@router.callback_query(F.data.startswith("complaint_ban_"))
@admin_required
async def complaint_ban(callback: CallbackQuery):
    await callback.answer()
    target_user_id = int(callback.data.replace("complaint_ban_", ""))

    from app.services.profile_service import get_user_by_id
    user = await get_user_by_id(target_user_id)
    if user:
        await ban_user(user.telegram_id)

    await safe_edit(callback, f"✅ Пользователь #{target_user_id} забанен.", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_broadcast")
@admin_required
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Broadcast.text)
    try:
        await callback.message.edit_text("📨 Введите текст для рассылки:")
    except Exception:
        await callback.message.answer("📨 Введите текст для рассылки:")


@router.message(Broadcast.text)
async def broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(Broadcast.photo)
    await message.answer("📸 Отправьте фото для рассылки (или /skip чтобы без фото):")


@router.message(Broadcast.photo, F.photo)
async def broadcast_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await confirm_broadcast(message, state)


@router.message(Broadcast.photo, Command("skip"))
async def broadcast_skip_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await confirm_broadcast(message, state)


async def confirm_broadcast(message: Message, state: FSMContext):
    data = await state.get_data()
    users = await get_all_users()
    active_users = [u for u in users if not u.is_banned]

    text = (
        f"📨 Рассылка:\n\n"
        f"Текст: {data['text']}\n"
        f"Фото: {'✅' if data.get('photo_id') else '❌'}\n"
        f"Получателей: {len(active_users)}\n\n"
        f"Отправить?"
    )
    await state.set_state(Broadcast.confirm)
    await message.answer(text, reply_markup=confirm_keyboard())


@router.callback_query(Broadcast.confirm, F.data == "confirm_yes")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from app.services.notification_service import send_broadcast

    data = await state.get_data()
    users = await get_all_users()
    active_users = [u.telegram_id for u in users if not u.is_banned]

    bot = callback.bot
    success, failed = await send_broadcast(
        bot, active_users,
        text=data["text"],
        photo_id=data.get("photo_id"),
    )

    await state.clear()
    await safe_edit(callback,
        f"📨 Рассылка завершена!\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(Broadcast.confirm, F.data == "confirm_no")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await safe_edit(callback, "❌ Рассылка отменена.", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_verifications")
@admin_required
async def admin_verifications(callback: CallbackQuery):
    await callback.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    pending = await get_pending_verifications()
    if not pending:
        await safe_edit(callback, "✅ Нет заявок на верификацию.", reply_markup=admin_keyboard())
        return

    builder = InlineKeyboardBuilder()
    for p in pending:
        builder.button(
            text=f"{p['name']} (user#{p['user_id']})",
            callback_data=f"verify_view_{p['profile_id']}",
        )
    builder.button(text="🔙 Назад", callback_data="admin_menu")
    builder.adjust(1)

    await safe_edit(callback, f"✅ Заявки на верификацию ({len(pending)}):", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("verify_view_"))
@admin_required
async def verify_view(callback: CallbackQuery):
    await callback.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    profile_id = int(callback.data.replace("verify_view_", ""))
    pending = await get_pending_verifications()
    item = next((p for p in pending if p["profile_id"] == profile_id), None)
    if item is None:
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"verify_approve_{profile_id}")
    builder.button(text="❌ Отклонить", callback_data=f"verify_reject_{profile_id}")
    builder.button(text="🔙 Назад", callback_data="admin_verifications")
    builder.adjust(1)

    text = f"✅ Верификация: {item['name']} (ID: {item['user_id']})"
    try:
        await callback.message.answer_photo(item["photo_id"], caption=text, reply_markup=builder.as_markup())
        try:
            await callback.message.delete()
        except Exception:
            pass
    except Exception:
        await safe_edit(callback, text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("verify_approve_"))
@admin_required
async def verify_approve(callback: CallbackQuery):
    await callback.answer()
    profile_id = int(callback.data.replace("verify_approve_", ""))
    await verify_profile(profile_id)
    try:
        await callback.message.edit_text("✅ Фото верифицировано! Пользователь получил отметку.")
    except Exception:
        await callback.message.answer("✅ Фото верифицировано! Пользователь получил отметку.")


@router.callback_query(F.data.startswith("verify_reject_"))
@admin_required
async def verify_reject(callback: CallbackQuery):
    await callback.answer()
    profile_id = int(callback.data.replace("verify_reject_", ""))
    await reject_verification(profile_id)
    try:
        await callback.message.edit_text("❌ Верификация отклонена.")
    except Exception:
        await callback.message.answer("❌ Верификация отклонена.")


@router.callback_query(F.data == "admin_stars_balance")
@admin_required
async def admin_stars_balance(callback: CallbackQuery):
    await callback.answer()
    from app.services.star_service import get_star_balance, STAR_CONVERSIONS
    from app.database import async_session
    from sqlalchemy import select, func
    from app.models import Payment

    balance = await get_star_balance()

    async with async_session() as session:
        payment_breakdown = await session.execute(
            select(Payment.payment_type, func.count(Payment.id), func.sum(Payment.amount))
            .where(Payment.currency == "XTR", Payment.status == "completed")
            .group_by(Payment.payment_type)
        )
        breakdown_text = ""
        for row in payment_breakdown:
            breakdown_text += f"  • {row[0]}: {row[1]} шт, {int(row[2])} ⭐\n"

    text = (
        "⭐ Баланс Telegram Stars\n\n"
        f"💰 Всего заработано: {balance['total_earned']} ⭐\n"
        f"💸 Использовано: {balance['total_used']} ⭐\n"
        f"📊 Доступно: {balance['available']} ⭐\n\n"
        f"📈 По типам:\n{breakdown_text or '  —'}\n\n"
        "💡 Конвертируй Stars во внутренние бонусы:"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for key, info in STAR_CONVERSIONS.items():
        builder.button(text=f"{info['label']} — {info['stars']}⭐", callback_data=f"star_convert_{key}")
    builder.button(text="💸 Вывести через Fragment.com", callback_data="admin_withdraw_request")
    builder.button(text="📋 История", callback_data="admin_stars_history")
    builder.button(text="🔙 Назад", callback_data="admin_menu")
    builder.adjust(1)

    await safe_edit(callback, text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("star_convert_"))
@admin_required
async def star_convert(callback: CallbackQuery):
    await callback.answer()
    from app.services.star_service import STAR_CONVERSIONS, get_star_balance, create_withdrawal
    from app.database import async_session
    from sqlalchemy import select
    from app.models import User, Profile, Gift
    from app.models.payment import GIFT_OPTIONS as GIFT_MAP
    import datetime

    conv_key = callback.data.replace("star_convert_", "")
    conv_info = STAR_CONVERSIONS.get(conv_key)
    if not conv_info:
        return

    balance = await get_star_balance()
    if conv_info["stars"] > balance["available"]:
        await safe_edit(callback, f"❌ Недостаточно Stars. Доступно: {balance['available']} ⭐, нужно: {conv_info['stars']} ⭐.")
        return

    async with async_session() as session:
        admin_user = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        admin_user = admin_user.scalar_one_or_none()
        if admin_user is None:
            return

        result_text = ""
        amount = conv_info["stars"]

        if conv_key == "premium_1m":
            admin_user.is_premium = True
            admin_user.premium_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)
            result_text = "✅ Премиум на 1 месяц активирован на вашем аккаунте!"

        elif conv_key == "premium_3m":
            admin_user.is_premium = True
            admin_user.premium_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=90)
            result_text = "✅ Премиум на 3 месяца активирован на вашем аккаунте!"

        elif conv_key == "premium_lifetime":
            admin_user.is_premium = True
            admin_user.premium_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=36500)
            result_text = "✅ Премиум навсегда активирован на вашем аккаунте!"

        elif conv_key == "boost":
            profile = await session.execute(select(Profile).where(Profile.user_id == admin_user.id))
            profile = profile.scalar_one_or_none()
            if profile:
                profile.is_boosted = True
                profile.boost_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
                result_text = "🚀 Буст на 7 дней активирован на вашей анкете!"
            else:
                await safe_edit(callback, "❌ У вас нет анкеты. Создайте через /register.")
                return

        elif conv_key == "likes_50":
            admin_user.extra_likes = (admin_user.extra_likes or 0) + 50
            result_text = "❤️ 50 бонусных лайков добавлены на ваш аккаунт!"

        elif conv_key.startswith("gift_"):
            gift_type = conv_key.replace("gift_", "")
            gift_info = GIFT_MAP.get(gift_type, {})
            gift = Gift(
                from_user_id=admin_user.id,
                to_user_id=admin_user.id,
                gift_type=gift_type,
                message="🎁 Подарок с баланса Stars",
                stars_cost=0,
            )
            session.add(gift)
            result_text = f"🎁 {gift_info.get('label', gift_type)} отправлена вам!"

        elif conv_key == "ad_banner":
            result_text = "📢 Рекламный баннер активирован! Он появится в ленте пользователей."

        await session.commit()

    ok = await create_withdrawal(admin_user.id, amount, conversion_type=conv_key, conversion_detail=result_text)
    if not ok:
        await safe_edit(callback, "❌ Ошибка конвертации. Попробуйте позже.")
        return

    await safe_edit(callback, result_text, reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_withdraw_request")
@admin_required
async def admin_withdraw_request(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from app.services.star_service import get_star_balance

    balance = await get_star_balance()
    text = (
        "💸 Вывод Stars через Fragment.com\n\n"
        "1. Открой Fragment.com\n"
        "2. Войди через Telegram\n"
        "3. Найди баланс Stars этого бота\n"
        "4. Выведи на TON/USDT\n\n"
        f"💰 Доступно: {balance['available']} ⭐\n"
        "Минимальная сумма: 1 ⭐\n\n"
        "Напиши сумму для вывода (в ⭐):"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Открыть Fragment.com", url="https://fragment.com/")
    builder.button(text="🔙 Назад", callback_data="admin_stars_balance")
    builder.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())

    await state.set_state("waiting_withdraw_amount")


@router.callback_query(F.data == "admin_stars_history")
@admin_required
async def admin_stars_history(callback: CallbackQuery):
    await callback.answer()
    from app.services.star_service import get_conversion_history
    from app.database import async_session
    from sqlalchemy import select
    from app.models import User

    async with async_session() as session:
        admin_user = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        admin_user = admin_user.scalar_one_or_none()
        if admin_user is None:
            return

    history = await get_conversion_history(admin_user.id)
    if not history:
        await safe_edit(callback, "📋 История операций пуста.", reply_markup=admin_keyboard())
        return

    text = "📋 История операций со Stars:\n\n"
    for h in history:
        status_map = {"pending": "⏳", "approved": "✅", "converted": "🔄", "rejected": "❌"}
        s = status_map.get(h["status"], "❓")
        conv_type = h["conversion_type"] or "вывод"
        text += f"{s} {h['amount']}⭐ — {conv_type}\n"

    await safe_edit(callback, text, reply_markup=admin_keyboard())


@router.message(F.text, F.text.startswith("/cancel"))
async def admin_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in ("waiting_withdraw_amount", "waiting_user_id"):
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_grant_menu")
@admin_required
async def admin_grant_menu(callback: CallbackQuery):
    await callback.answer()
    await safe_edit(callback, "🎁 Выдать пользователю:", reply_markup=admin_grant_keyboard())


@router.callback_query(F.data == "admin_grant_premium")
@admin_required
async def admin_grant_premium_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="grant_premium")
    await state.set_state("waiting_user_id")
    try:
        await callback.message.edit_text("⭐ Введите Telegram ID пользователя для выдачи премиума:")
    except Exception:
        await callback.message.answer("⭐ Введите Telegram ID пользователя для выдачи премиума:")


@router.callback_query(F.data == "admin_grant_boost")
@admin_required
async def admin_grant_boost_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="grant_boost")
    await state.set_state("waiting_user_id")
    try:
        await callback.message.edit_text("🚀 Введите Telegram ID пользователя для выдачи буста:")
    except Exception:
        await callback.message.answer("🚀 Введите Telegram ID пользователя для выдачи буста:")


@router.callback_query(F.data == "admin_grant_gift")
@admin_required
async def admin_grant_gift_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="grant_gift")
    await state.set_state("waiting_user_id")
    try:
        await callback.message.edit_text("🎁 Введите Telegram ID пользователя для отправки подарка:")
    except Exception:
        await callback.message.answer("🎁 Введите Telegram ID пользователя для отправки подарка:")


@router.callback_query(F.data == "admin_grant_likes")
@admin_required
async def admin_grant_likes_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="grant_likes")
    await state.set_state("waiting_user_id")
    try:
        await callback.message.edit_text("❤️ Введите Telegram ID пользователя для выдачи лайков:")
    except Exception:
        await callback.message.answer("❤️ Введите Telegram ID пользователя для выдачи лайков:")


async def _process_withdraw_amount(message: Message, state: FSMContext):
    from app.services.star_service import get_star_balance, create_withdrawal
    from app.database import async_session
    from sqlalchemy import select
    from app.models import User

    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число.")
        return

    balance = await get_star_balance()
    if amount > balance["available"]:
        await message.answer(f"❌ Недостаточно Stars. Доступно: {balance['available']} ⭐.")
        return

    async with async_session() as session:
        admin_user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        admin_user = admin_user.scalar_one_or_none()
        if admin_user is None:
            return

        ok = await create_withdrawal(admin_user.id, amount)
        if ok:
            await message.answer(
                f"✅ Заявка на вывод {amount} ⭐ создана!\n\n"
                f"Для вывода:\n"
                f"1. Открой Fragment.com\n"
                f"2. Войди через Telegram\n"
                f"3. Найди баланс Stars бота\n"
                f"4. Выведи на TON/USDT\n\n"
                f"Сумма: {amount} ⭐",
                reply_markup=admin_keyboard(),
            )
        else:
            await message.answer("❌ Ошибка создания заявки.", reply_markup=admin_keyboard())
    await state.clear()


async def _process_grant(message: Message, state: FSMContext):
    import datetime
    from app.database import async_session
    from sqlalchemy import select
    from app.models import User

    data = await state.get_data()
    edit_field = data.get("edit_field")

    try:
        target_tid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный Telegram ID. Введите число.")
        return

    async with async_session() as session:
        target = await session.execute(select(User).where(User.telegram_id == target_tid))
        target = target.scalar_one_or_none()
        if target is None:
            await message.answer(f"❌ Пользователь с ID {target_tid} не найден.")
            await state.clear()
            return

        if edit_field == "grant_premium":
            target.is_premium = True
            target.premium_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365)
            await session.commit()
            await message.answer(f"✅ Премиум выдан пользователю {target_tid} на 365 дней!", reply_markup=admin_keyboard())

        elif edit_field == "grant_boost":
            from app.models import Profile
            profile = await session.execute(select(Profile).where(Profile.user_id == target.id))
            profile = profile.scalar_one_or_none()
            if profile:
                profile.is_boosted = True
                profile.boost_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)
                await session.commit()
                await message.answer(f"✅ Буст выдан пользователю {target_tid} на 30 дней!", reply_markup=admin_keyboard())
            else:
                await message.answer(f"❌ У пользователя {target_tid} нет анкеты.")

        elif edit_field == "grant_gift":
            from app.models import Gift
            gift = Gift(
                from_user_id=target.id,
                to_user_id=target.id,
                gift_type="rose",
                message="🎁 Подарок от администрации!",
                stars_cost=0,
            )
            session.add(gift)
            await session.commit()
            await message.answer(f"✅ Подарок отправлен пользователю {target_tid}!", reply_markup=admin_keyboard())

        elif edit_field == "grant_likes":
            target.extra_likes = (target.extra_likes or 0) + 50
            await session.commit()
            await message.answer(f"✅ 50 лайков выдано пользователю {target_tid}!", reply_markup=admin_keyboard())

    await state.clear()


@router.message(F.text)
async def admin_text_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == "waiting_withdraw_amount":
        await _process_withdraw_amount(message, state)
    elif current_state == "waiting_user_id":
        await _process_grant(message, state)
