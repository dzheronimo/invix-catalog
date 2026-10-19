import asyncio
import logging

from aiogram import Bot, Dispatcher

from .api_client import BackendClient
from .config import Settings
from .handlers import router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    api_client = BackendClient(settings.backend_url, settings.internal_token)
    # Handlers are stateless; Telegram distributes updates between polling
    # replicas, so any number of bot instances can run side by side.
    await dp.start_polling(
        bot,
        settings=settings,
        api_client=api_client,
        allowed_updates=["message"],
    )


if __name__ == "__main__":
    asyncio.run(main())
