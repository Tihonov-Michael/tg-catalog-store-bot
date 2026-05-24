import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery

from config import settings
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from db.connection import async_session, async_main
from bot.handlers import start, catalog, cart, order, admin, support

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await async_main()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    dp.update.middleware(DbSessionMiddleware(session_pool=async_session))
    dp.message.middleware(ThrottlingMiddleware())

    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(order.router)
    dp.include_router(admin.router)
    dp.include_router(support.router)

    # Silence taps on decorative/spacer buttons
    @dp.callback_query(F.data == "noop")
    async def noop_handler(callback: CallbackQuery) -> None:
        await callback.answer()

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass