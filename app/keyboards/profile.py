from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Смотреть анкеты", callback_data="search")
    builder.button(text="📝 Моя анкета", callback_data="my_profile")
    builder.button(text="💕 Мои совпадения", callback_data="my_matches")
    builder.button(text="⚙️ Настройки", callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()


def profile_action_keyboard(target_id: int, is_match: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_match:
        builder.button(text="💌 Написать", url="https://t.me/")
        builder.button(text="👎 Удалить из совпадений", callback_data=f"unmatch_{target_id}")
    else:
        builder.button(text="❤️", callback_data=f"like_{target_id}")
        builder.button(text="👎", callback_data=f"dislike_{target_id}")
        builder.button(text="🚫 Заблокировать", callback_data=f"block_{target_id}")
    builder.button(text="💬 Пожаловаться", callback_data=f"complaint_{target_id}")
    builder.button(text="⏭ В меню", callback_data="main_menu")
    if is_match:
        builder.adjust(2, 1, 1)
    else:
        builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


def edit_profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Имя", callback_data="edit_name")
    builder.button(text="🎂 Возраст", callback_data="edit_age")
    builder.button(text="⚧ Пол", callback_data="edit_gender")
    builder.button(text="🔍 Кого ищу", callback_data="edit_looking_for")
    builder.button(text="🏙 Город", callback_data="edit_city")
    builder.button(text="📄 О себе", callback_data="edit_bio")
    builder.button(text="📸 Фото", callback_data="edit_photos")
    builder.button(text="✅ Запросить верификацию", callback_data="request_verify")
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(2)
    return builder.as_markup()


def settings_keyboard(is_premium: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎯 Настройки поиска", callback_data="search_settings")
    builder.button(text="⭐ Премиум", callback_data="premium")
    if is_premium:
        builder.button(text="🚀 Буст анкеты", callback_data="boost_anketa")
    builder.button(text="🚫 Заблокированные", callback_data="blocked_list")
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def search_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👫 Кого ищу", callback_data="set_looking_for")
    builder.button(text="📏 Возраст: от", callback_data="set_age_min")
    builder.button(text="📏 Возраст: до", callback_data="set_age_max")
    builder.button(text="🏙 Город", callback_data="set_city")
    builder.button(text="🔙 Назад", callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()


def gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="gender_male")
    builder.button(text="👩 Женский", callback_data="gender_female")
    builder.button(text="👫 Все", callback_data="gender_all")
    builder.adjust(1)
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, всё верно", callback_data="confirm_yes")
    builder.button(text="❌ Заполнить заново", callback_data="confirm_no")
    builder.adjust(1)
    return builder.as_markup()


def my_gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="mygender_male")
    builder.button(text="👩 Женский", callback_data="mygender_female")
    builder.adjust(1)
    return builder.as_markup()
