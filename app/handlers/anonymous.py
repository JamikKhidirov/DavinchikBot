from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import main_menu_keyboard

router = Router()


class AnonymousMessage(StatesGroup):
    text = State()


class AnonymousReply(StatesGroup):
    text = State()


@router.callback_query(F.data.startswith("anon_"))
async def start_anon(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    target_id = int(parts[1])

    from app.services.block_service import is_blocked
    from app.services.profile_service import get_user_by_telegram_id, get_user_by_id
    my_user = await get_user_by_telegram_id(callback.from_user.id)
    if my_user and await is_blocked(my_user.id, target_id):
        await callback.answer("Вы заблокированы или пользователь заблокирован", show_alert=True)
        return

    await state.update_data(anon_target_id=target_id)
    await state.set_state(AnonymousMessage.text)
    await callback.message.answer(
        "🕵️ Напиши текст анонимного сообщения.\n"
        "Получатель не узнает, кто ты — увидит только текст.\n"
        "У получателя будет кнопка чтобы ответить (тоже анонимно)."
    )
    await callback.answer()


@router.message(AnonymousMessage.text)
async def process_anon_text(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("anon_target_id")
    text = message.text.strip()

    if not text:
        await message.answer("Напиши что-нибудь.")
        return

    from app.services.profile_service import get_user_by_id, get_user_by_telegram_id
    target_user = await get_user_by_id(target_id)
    if target_user:
        from app.services.block_service import is_blocked
        my_user = await get_user_by_telegram_id(message.from_user.id)
        if my_user and await is_blocked(my_user.id, target_id):
            await message.answer(
                "❌ Невозможно отправить сообщение.",
                reply_markup=main_menu_keyboard(),
            )
            await state.clear()
            return

        try:
            builder = InlineKeyboardBuilder()
            builder.button(text="🕵️ Ответить анонимно", callback_data=f"anon_reply_{message.from_user.id}")
            builder.button(text="⏭ Пропустить", callback_data="main_menu")
            builder.adjust(1)

            await message.bot.send_message(
                target_user.telegram_id,
                f"🕵️ Тебе пришло анонимное сообщение:\n\n{text}",
                reply_markup=builder.as_markup(),
            )
            await message.answer(
                "✅ Сообщение отправлено анонимно!\n\n"
                "Если тебе ответят — ты получишь уведомление и сможешь продолжить анонимный диалог.",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            await message.answer(
                "❌ Не удалось доставить сообщение. Возможно, пользователь заблокировал бота.",
                reply_markup=main_menu_keyboard(),
            )
    else:
        await message.answer(
            "❌ Пользователь не найден.",
            reply_markup=main_menu_keyboard(),
        )
    await state.clear()


@router.callback_query(F.data.startswith("anon_reply_"))
async def start_anon_reply(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка", show_alert=True)
        return
    original_sender_id = int(parts[2])
    await state.update_data(anon_reply_to=original_sender_id)
    await state.set_state(AnonymousReply.text)
    await callback.message.answer(
        "🕵️ Напиши ответ (он тоже будет анонимным):"
    )
    await callback.answer()


@router.message(AnonymousReply.text)
async def process_anon_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    original_sender_id = data.get("anon_reply_to")
    text = message.text.strip()

    if not text:
        await message.answer("Напиши что-нибудь.")
        return

    try:
        builder = InlineKeyboardBuilder()
        builder.button(text="🕵️ Ответить анонимно", callback_data=f"anon_reply_{message.from_user.id}")
        builder.adjust(1)

        await message.bot.send_message(
            original_sender_id,
            f"🕵️ Тебе пришёл анонимный ответ:\n\n{text}",
            reply_markup=builder.as_markup(),
        )
        await message.answer(
            "✅ Ответ отправлен анонимно!",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await message.answer(
            "❌ Не удалось доставить ответ.",
            reply_markup=main_menu_keyboard(),
        )
    await state.clear()
