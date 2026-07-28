from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.profile import main_menu_keyboard
from app.services.matching_service import get_matches, unmatch

router = Router()


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "my_matches")
async def show_matches(callback: CallbackQuery):
    await callback.answer()
    matches = await get_matches(callback.from_user.id)

    if not matches:
        await safe_edit(callback,
            "💕 У вас пока нет совпадений. Смотрите анкеты и ставьте лайки!",
            reply_markup=main_menu_keyboard(),
        )
        return

    builder = InlineKeyboardBuilder()
    for m in matches:
        btn_text = f"{m['name']}, {m['age']}, {m['city']}"
        builder.button(text=btn_text, callback_data=f"match_view_{m['id']}")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)

    await safe_edit(callback,
        f"💕 Твои совпадения ({len(matches)}):",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("match_view_"))
async def view_match(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.replace("match_view_", ""))

    from app.services.profile_service import get_user_by_id, get_profile_by_telegram_id

    user = await get_user_by_id(target_id)
    if user is None:
        return

    profile = await get_profile_by_telegram_id(user.telegram_id)
    if profile is None:
        return

    builder = InlineKeyboardBuilder()
    username = user.username
    if username:
        builder.button(text="💌 Написать", url=f"https://t.me/{username}")
    else:
        builder.button(text="💌 Написать (нет username)", callback_data="no_username")
    builder.button(text="👎 Удалить", callback_data=f"unmatch_confirm_{target_id}")
    builder.button(text="🔙 Назад", callback_data="my_matches")
    builder.adjust(1)

    gender_map = {"male": "👨", "female": "👩"}
    text = (
        f"{gender_map.get(profile.gender, '')} {profile.name}, {profile.age}\n"
        f"🏙 {profile.city}\n\n"
        f"{profile.bio or ''}"
    )

    photos = profile.photos or []
    videos = profile.videos or []
    try:
        await callback.message.delete()
    except Exception:
        pass
    if photos:
        await callback.message.answer_photo(photos[0], caption=text, reply_markup=builder.as_markup())
    elif videos:
        await callback.message.answer_video(videos[0], caption=text, reply_markup=builder.as_markup())
    else:
        await safe_edit(callback, text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("unmatch_confirm_"))
async def confirm_unmatch(callback: CallbackQuery):
    await callback.answer()
    target_id = int(callback.data.replace("unmatch_confirm_", ""))
    await unmatch(callback.from_user.id, target_id)
    await safe_edit(callback, "✅ Совпадение удалено.", reply_markup=main_menu_keyboard())
