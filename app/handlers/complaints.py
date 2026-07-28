from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.keyboards.profile import main_menu_keyboard
from app.services.matching_service import complaint


class ComplaintState(StatesGroup):
    reason = State()


router = Router()


@router.callback_query(F.data.startswith("complaint_"))
async def start_complaint(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    target_id = int(parts[1])
    await state.update_data(complaint_target_id=target_id)
    await state.set_state(ComplaintState.reason)
    await callback.message.answer(
        "💬 Опишите причину жалобы (например: фейк, спам, оскорбление):"
    )
    await callback.answer()


@router.message(ComplaintState.reason)
async def process_complaint(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("complaint_target_id")
    reason = message.text.strip()

    if len(reason) < 10:
        await message.answer("Опишите причину подробнее (минимум 10 символов):")
        return

    success = await complaint(message.from_user.id, target_id, reason)
    if success:
        await message.answer(
            "✅ Жалоба отправлена администраторам.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            "❌ Не удалось отправить жалобу.",
            reply_markup=main_menu_keyboard(),
        )
    await state.clear()
