from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.keyboards.profile import main_menu_keyboard

router = Router()


class AnonymousMessage(StatesGroup):
    text = State()


@router.callback_query(F.data.startswith("anon_"))
async def start_anon(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    target_id = int(parts[1])
    await state.update_data(anon_target_id=target_id)
    await state.set_state(AnonymousMessage.text)
    await callback.message.answer(
        "🕵️ Напиши текст анонимного сообщения.\n"
        "Получатель не узнает, кто ты — увидит только текст."
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

    from app.services.profile_service import get_user_by_id
    target_user = await get_user_by_id(target_id)
    if target_user:
        try:
            await message.bot.send_message(
                target_user.telegram_id,
                f"🕵️ Тебе пришло анонимное сообщение:\n\n{text}",
            )
            await message.answer(
                "✅ Сообщение отправлено анонимно!",
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
