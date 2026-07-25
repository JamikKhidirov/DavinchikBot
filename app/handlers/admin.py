from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.config import config
from app.keyboards.admin import admin_keyboard, ads_management_keyboard
from app.keyboards.profile import main_menu_keyboard
from app.services.profile_service import (
    get_all_users, get_user_by_telegram_id,
    is_admin, ban_user, unban_user, has_profile,
    get_pending_verifications, verify_profile, reject_verification,
)
from app.services.ad_service import get_all_ads, get_ad_by_id, toggle_ad
from app.states.admin_states import AddAdvertisement, Broadcast

router = Router()


def admin_required(func):
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


@router.message(Command("admin"))
@admin_required
async def cmd_admin(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if user and not user.is_admin:
        user.is_admin = True
    await message.answer(
        "👑 Админ-панель:",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(F.data == "admin_menu")
@admin_required
async def admin_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "👑 Админ-панель:",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
@admin_required
async def admin_stats(callback: CallbackQuery):
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
    await callback.message.edit_text(text, reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_ads")
@admin_required
async def admin_ads(callback: CallbackQuery):
    await callback.message.edit_text(
        "📢 Управление рекламой:",
        reply_markup=ads_management_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_ad")
@admin_required
async def admin_add_ad(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddAdvertisement.text)
    await callback.message.edit_text(
        "📢 Введите текст рекламы:"
    )
    await callback.answer()


@router.message(AddAdvertisement.text)
async def ad_text_received(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(AddAdvertisement.photo)
    await message.answer(
        "📸 Отправьте фото для рекламы (или /skip чтобы без фото):"
    )


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


@router.message(AddAdvertisement.button_text)
async def ad_button_text_received(message: Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await state.set_state(AddAdvertisement.button_url)
    await message.answer("🔗 Ссылка для кнопки (или /skip):")


@router.message(AddAdvertisement.button_text, Command("skip"))
async def ad_button_skip(message: Message, state: FSMContext):
    await state.update_data(button_text=None, button_url=None)
    await save_ad(message, state)


@router.message(AddAdvertisement.button_url)
async def ad_url_received(message: Message, state: FSMContext):
    await state.update_data(button_url=message.text)
    await save_ad(message, state)


@router.message(AddAdvertisement.button_url, Command("skip"))
async def ad_url_skip(message: Message, state: FSMContext):
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
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    ads = await get_all_ads()
    if not ads:
        await callback.message.edit_text(
            "Рекламы пока нет.",
            reply_markup=ads_management_keyboard(),
        )
        await callback.answer()
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

    await callback.message.edit_text(
        "📋 Список рекламы:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ad_detail_"))
@admin_required
async def ad_detail(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    ad_id = int(callback.data.replace("ad_detail_", ""))
    ad = await get_ad_by_id(ad_id)
    if ad is None:
        await callback.answer("Реклама не найдена", show_alert=True)
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
    builder.button(text="🔙 Назад", callback_data="admin_list_ads")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("ad_toggle_"))
@admin_required
async def ad_toggle(callback: CallbackQuery):
    ad_id = int(callback.data.replace("ad_toggle_", ""))
    new_status = await toggle_ad(ad_id)
    if new_status is None:
        await callback.answer("Реклама не найдена", show_alert=True)
        return

    status_text = "включена" if new_status else "отключена"
    await callback.message.edit_text(
        f"✅ Реклама #{ad_id} {status_text}!",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_users")
@admin_required
async def admin_users(callback: CallbackQuery):
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

    await callback.message.edit_text(text, reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_complaints")
@admin_required
async def admin_complaints(callback: CallbackQuery):
    from app.database import async_session
    from sqlalchemy import select
    from app.models import Complaint
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with async_session() as session:
        result = await session.execute(
            select(Complaint).where(Complaint.status == "pending").order_by(Complaint.created_at.desc())
        )
        complaints = list(result.scalars().all())

    if not complaints:
        await callback.message.edit_text(
            "🚫 Нет новых жалоб.",
            reply_markup=admin_keyboard(),
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for c in complaints[:10]:
        builder.button(
            text=f"Жалоба #{c.id} от user#{c.from_user_id} на user#{c.complained_user_id}",
            callback_data=f"complaint_view_{c.id}",
        )
    builder.button(text="🔙 Назад", callback_data="admin_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        f"🚫 Жалобы ({len(complaints)}):",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("complaint_view_"))
@admin_required
async def complaint_view(callback: CallbackQuery):
    from app.database import async_session
    from sqlalchemy import select
    from app.models import Complaint
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    complaint_id = int(callback.data.replace("complaint_view_", ""))
    async with async_session() as session:
        result = await session.execute(select(Complaint).where(Complaint.id == complaint_id))
        c = result.scalar_one_or_none()

    if c is None:
        await callback.answer("Жалоба не найдена", show_alert=True)
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

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("complaint_close_"))
@admin_required
async def complaint_close(callback: CallbackQuery):
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

    await callback.message.edit_text(
        "✅ Жалоба закрыта.",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("complaint_ban_"))
@admin_required
async def complaint_ban(callback: CallbackQuery):
    target_user_id = int(callback.data.replace("complaint_ban_", ""))

    from app.services.profile_service import get_user_by_id
    user = await get_user_by_id(target_user_id)
    if user:
        from app.services.profile_service import ban_user
        await ban_user(user.telegram_id)

    await callback.message.edit_text(
        f"✅ Пользователь #{target_user_id} забанен.",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
@admin_required
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.text)
    await callback.message.edit_text(
        "📨 Введите текст для рассылки:"
    )
    await callback.answer()


@router.message(Broadcast.text)
async def broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(Broadcast.photo)
    await message.answer(
        "📸 Отправьте фото для рассылки (или /skip чтобы без фото):"
    )


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
    from app.keyboards.profile import confirm_keyboard
    await state.set_state(Broadcast.confirm)
    await message.answer(text, reply_markup=confirm_keyboard())


@router.callback_query(Broadcast.confirm, F.data == "confirm_yes")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    from app.services.notification_service import send_broadcast
    from app.services.profile_service import get_all_users

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
    await callback.message.edit_text(
        f"📨 Рассылка завершена!\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(Broadcast.confirm, F.data == "confirm_no")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Рассылка отменена.",
        reply_markup=admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_verifications")
@admin_required
async def admin_verifications(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    pending = await get_pending_verifications()
    if not pending:
        await callback.message.edit_text(
            "✅ Нет заявок на верификацию.",
            reply_markup=admin_keyboard(),
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for p in pending:
        builder.button(
            text=f"{p['name']} (user#{p['user_id']})",
            callback_data=f"verify_view_{p['profile_id']}",
        )
    builder.button(text="🔙 Назад", callback_data="admin_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        f"✅ Заявки на верификацию ({len(pending)}):",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("verify_view_"))
@admin_required
async def verify_view(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    profile_id = int(callback.data.replace("verify_view_", ""))
    pending = await get_pending_verifications()
    item = next((p for p in pending if p["profile_id"] == profile_id), None)
    if item is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"verify_approve_{profile_id}")
    builder.button(text="❌ Отклонить", callback_data=f"verify_reject_{profile_id}")
    builder.button(text="🔙 Назад", callback_data="admin_verifications")
    builder.adjust(1)

    text = f"✅ Верификация: {item['name']} (ID: {item['user_id']})"
    await callback.message.answer_photo(
        item["photo_id"],
        caption=text,
        reply_markup=builder.as_markup(),
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("verify_approve_"))
@admin_required
async def verify_approve(callback: CallbackQuery):
    profile_id = int(callback.data.replace("verify_approve_", ""))
    await verify_profile(profile_id)
    await callback.message.edit_text("✅ Фото верифицировано! Пользователь получил отметку.")
    await callback.answer()


@router.callback_query(F.data.startswith("verify_reject_"))
@admin_required
async def verify_reject(callback: CallbackQuery):
    profile_id = int(callback.data.replace("verify_reject_", ""))
    await reject_verification(profile_id)
    await callback.message.edit_text("❌ Верификация отклонена.")
    await callback.answer()
