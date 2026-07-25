import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import config
from app.database import init_db, engine
from app.middlewares.throttling import ThrottlingMiddleware
from app.handlers import (
    start, registration, search, profile, matches, admin, complaints, premium,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def on_startup():
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова.")

    from app.services.profile_service import get_all_users, deactivate_inactive_profiles
    users = await get_all_users()
    for user in users:
        if user.telegram_id in config.admin_ids_list:
            user.is_admin = True

    deactivated = await deactivate_inactive_profiles()
    if deactivated:
        logger.info(f"Скрыто неактивных анкет: {deactivated}")

    from app.services.premium_service import check_premium_expired, check_boost_expired
    expired_premium = await check_premium_expired()
    expired_boost = await check_boost_expired()
    if expired_premium:
        logger.info(f"Истекших премиум-подписок: {expired_premium}")
    if expired_boost:
        logger.info(f"Истекших бустов: {expired_boost}")

    from app.setup_bot import setup_bot
    await setup_bot(bot)
    logger.info("Бот запущен!")


async def on_shutdown():
    logger.info("Завершение работы...")
    await engine.dispose()
    logger.info("Соединения с БД закрыты.")


async def main():
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())

    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(search.router)
    dp.include_router(profile.router)
    dp.include_router(matches.router)
    dp.include_router(admin.router)
    dp.include_router(complaints.router)
    dp.include_router(premium.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        logger.info("Запуск polling...")
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал завершения.")
    finally:
        await bot.session.close()
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
