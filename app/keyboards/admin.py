from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📢 Реклама", callback_data="admin_ads")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="🚫 Жалобы", callback_data="admin_complaints")
    builder.button(text="✅ Верификация", callback_data="admin_verifications")
    builder.button(text="📨 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def ads_management_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать рекламу", callback_data="admin_add_ad")
    builder.button(text="📋 Список рекламы", callback_data="admin_list_ads")
    builder.button(text="🔙 Назад", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()
