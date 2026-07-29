from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import main_menu_keyboard
from app.services.message_service import (
    send_message, get_messages, get_match_chat_info,
    get_user_matches_with_messages,
)
from app.services.profile_service import is_banned
from app.states.chat_states import Chat

router = Router()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "my_chats")
async def show_chats(callback: CallbackQuery):
    await callback.answer()
    if await is_banned(callback.from_user.id):
        await callback.message.answer("🚫 Вы забанены.")
        return

    chats = await get_user_matches_with_messages(callback.from_user.id)
    if not chats:
        await safe_edit(callback,
            "💬 У вас пока нет чатов. Начните общаться с вашими совпадениями!",
            reply_markup=main_menu_keyboard(),
        )
        return

    builder = InlineKeyboardBuilder()
    for c in chats:
        name = f"{c['partner_name']}, {c['partner_age']}"
        last = ""
        if c.get("last_message"):
            last = f" — {c['last_message'][:20]}{'...' if len(c['last_message']) > 20 else ''}"
        builder.button(text=f"💬 {name}{last}", callback_data=f"open_chat_{c['match_id']}")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)

    await safe_edit(callback, "💬 Ваши чаты:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("open_chat_"))
async def open_chat(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    match_id = int(callback.data.replace("open_chat_", ""))

    info = await get_match_chat_info(match_id, callback.from_user.id)
    if info is None:
        await safe_edit(callback, "❌ Чат недоступен.", reply_markup=main_menu_keyboard())
        return

    messages = await get_messages(match_id, callback.from_user.id, limit=20)

    header = (
        f"💬 Чат с {info['partner_name']}\n"
        f"└ {'@' + info['partner_username'] if info.get('partner_username') else 'нет username'}\n"
        f"Сообщений: {info['message_count']}\n\n"
    )

    text = header
    if messages:
        for m in messages:
            sender = "Вы" if m["sender_telegram_id"] == callback.from_user.id else info["partner_name"]
            text += f"{sender}: {m['text']}\n"
    else:
        text += "Напишите первое сообщение!"

    builder = InlineKeyboardBuilder()
    builder.button(text="💌 Написать в Telegram", url=f"https://t.me/{info['partner_username']}" if info.get("partner_username") else "https://t.me/")
    builder.button(text="✏️ Написать сообщение", callback_data=f"chat_type_{match_id}")
    builder.button(text="🔙 Назад", callback_data="my_chats")
    builder.adjust(1)

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("chat_type_"))
async def start_typing(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    match_id = int(callback.data.replace("chat_type_", ""))
    await state.set_state(Chat.typing)
    await state.update_data(chat_match_id=match_id)
    try:
        await callback.message.edit_text("✏️ Напишите сообщение (или /cancel чтобы выйти):")
    except Exception:
        await callback.message.answer("✏️ Напишите сообщение (или /cancel чтобы выйти):")


@router.message(F.text, F.text.startswith("/cancel"))
async def cancel_chat(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("chat_match_id"):
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=main_menu_keyboard())
    else:
        await message.answer("Нет активного чата.")


@router.message(F.text)
async def handle_chat_message(message: Message, state: FSMContext):
    data = await state.get_data()
    match_id = data.get("chat_match_id")
    if not match_id:
        return
    if not message.text or message.text.startswith("/"):
        return

    if await is_banned(message.from_user.id):
        await state.clear()
        await message.answer("🚫 Вы забанены.")
        return

    msg = await send_message(match_id, message.from_user.id, message.text)
    if msg:
        info = await get_match_chat_info(match_id, message.from_user.id)
        builder = InlineKeyboardBuilder()
        builder.button(text="💌 Написать в Telegram",
                       url=f"https://t.me/{info['partner_username']}" if info and info.get("partner_username") else "https://t.me/")
        builder.button(text="✏️ Ещё сообщение", callback_data=f"chat_type_{match_id}")
        builder.button(text="💬 Все чаты", callback_data="my_chats")
        builder.adjust(1)

        from app.services.profile_service import get_profile_by_telegram_id
        my_profile = await get_profile_by_telegram_id(message.from_user.id)
        sender_name = my_profile.name if my_profile else (message.from_user.first_name or "Пользователь")

        await message.answer(
            f"✅ Сообщение отправлено!\n\n"
            f"Ты: {message.text}",
            reply_markup=builder.as_markup(),
        )

        if info:
            notify_builder = InlineKeyboardBuilder()
            notify_builder.button(text="💬 Ответить", callback_data=f"open_chat_{match_id}")
            notify_builder.button(text="💬 Все чаты", callback_data="my_chats")
            notify_builder.adjust(1)
            try:
                await message.bot.send_message(
                    info["partner_telegram_id"],
                    f"💬 Новое сообщение от {sender_name}:\n\n{message.text}",
                    reply_markup=notify_builder.as_markup(),
                )
            except Exception:
                pass
    else:
        await message.answer("❌ Ошибка отправки. Попробуйте ещё раз.")

    await state.clear()
