from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.profile import INTEREST_CHOICES


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Смотреть анкеты", callback_data="search")
    builder.button(text="📝 Моя анкета", callback_data="my_profile")
    builder.button(text="💕 Мои совпадения", callback_data="my_matches")
    builder.button(text="💬 Чаты", callback_data="my_chats")
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
        builder.button(text="⭐", callback_data=f"superlike_{target_id}")
        builder.button(text="👎", callback_data=f"dislike_{target_id}")
        builder.button(text="🚫 Заблокировать", callback_data=f"block_{target_id}")
    builder.button(text="💬 Пожаловаться", callback_data=f"complaint_{target_id}")
    builder.button(text="🕵️ Анонимно", callback_data=f"anon_{target_id}")
    builder.button(text="🎁 Подарок", callback_data=f"send_gift_{target_id}")
    builder.button(text="⏭ В меню", callback_data="main_menu")
    if is_match:
        builder.adjust(2, 2, 1, 1)
    else:
        builder.adjust(3, 1, 1, 1, 1, 1)
    return builder.as_markup()


def edit_profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Имя", callback_data="edit_name")
    builder.button(text="🎂 Возраст", callback_data="edit_age")
    builder.button(text="⚧ Пол", callback_data="edit_gender")
    builder.button(text="🔍 Кого ищу", callback_data="edit_looking_for")
    builder.button(text="🏙 Город", callback_data="edit_city")
    builder.button(text="📄 О себе", callback_data="edit_bio")
    builder.button(text="🎯 Интересы", callback_data="edit_interests")
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
    builder.button(text="🎁 Мои подарки", callback_data="my_gifts")
    builder.button(text="🛒 Магазин подарков", callback_data="gift_shop")
    builder.button(text="🔗 Реферальная ссылка", callback_data="referral")
    builder.button(text="📊 Статистика", callback_data="profile_stats")
    builder.button(text="🏠 На главную", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def search_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👫 Кого ищу", callback_data="set_looking_for")
    builder.button(text="📏 Возраст: от", callback_data="set_age_min")
    builder.button(text="📏 Возраст: до", callback_data="set_age_max")
    builder.button(text="🏙 Город", callback_data="set_city")
    builder.button(text="🗺 Радиус поиска (км)", callback_data="set_radius")
    builder.button(text="📍 Обновить геопозицию", callback_data="set_location")
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


def interests_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for interest in INTEREST_CHOICES:
        mark = "✅ " if interest in selected else ""
        builder.button(text=f"{mark}{interest}", callback_data=f"interest_{interest}")
    builder.button(text="✅ Готово", callback_data="interests_done")
    builder.adjust(2)
    return builder.as_markup()


def referral_keyboard(code: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Копировать ссылку", callback_data="copy_referral_link")
    builder.button(text="📊 Мои рефералы", callback_data="referral_stats")
    builder.button(text="🔙 Назад", callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()
