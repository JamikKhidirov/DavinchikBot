"""
Скрипт настройки бота перед запуском.
Устанавливает: название, описание, список команд, кнопку меню.
Можно запустить отдельно: python -m app.setup_bot
"""
import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands

from app.config import config

logger = logging.getLogger(__name__)

BOT_NAME = "💕 Davinchik Bot"
BOT_SHORT_DESC = "Бот знакомств. Анкеты, лайки, взаимные симпатии."
BOT_DESCRIPTION = (
    "💕 Davinchik Bot — бот для знакомств\n\n"
    "🔍 Смотри анкеты людей из твоего города\n"
    "❤️ Ставь лайки и получай взаимные симпатии\n"
    "💕 Находи пару и общайся в Telegram\n\n"
    "Команды:\n"
    "/start — Запустить бота\n"
    "/register — Создать анкету\n"
    "/menu — Главное меню\n"
    "/admin — Админ-панель (только для админов)"
)

COMMANDS = [
    BotCommand(command="start", description="🚀 Запустить бота"),
    BotCommand(command="register", description="📝 Создать анкету"),
    BotCommand(command="menu", description="🏠 Главное меню"),
    BotCommand(command="admin", description="👑 Админ-панель"),
]


async def setup_bot(bot: Bot = None):
    if bot is None:
        bot = Bot(
            token=config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        close_bot = True
    else:
        close_bot = False

    try:
        me = await bot.get_me()
        logger.info(f"Бот: @{me.username} (id: {me.id})")

        await bot.set_my_name(name=BOT_NAME)
        logger.info(f"Название установлено: {BOT_NAME}")

        await bot.set_my_short_description(short_description=BOT_SHORT_DESC)
        logger.info("Краткое описание установлено")

        await bot.set_my_description(description=BOT_DESCRIPTION)
        logger.info("Описание установлено")

        await bot.set_my_commands(
            commands=COMMANDS,
            scope=BotCommandScopeDefault(),
        )
        logger.info(f"Команды ({len(COMMANDS)}) установлены")

        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Кнопка меню установлена")

        logger.info("✅ Настройка бота завершена успешно!")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка настройки бота: {e}")
        return False

    finally:
        if close_bot:
            await bot.session.close()


async def main():
    logging.basicConfig(level=logging.INFO)
    await setup_bot()


if __name__ == "__main__":
    asyncio.run(main())
