import io
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from .api_client import BackendClient
from .config import Settings

logger = logging.getLogger(__name__)

router = Router()

START_TEXT = "У меня есть товар"
CATALOG_BUTTON_TEXT = "Открыть каталог"
NEW_PRODUCT_COMMANDS = {"/new", "Создать товар"}

NEW_PRODUCT_HINT = (
    "Пришлите фотографию товара одним сообщением: "
    "фото + название в подписи к нему."
)
NO_CAPTION_HINT = "У фото нет названия. Пришлите фото ещё раз, указав название в подписи."
SAVE_ERROR_TEXT = "Не удалось сохранить товар. Попробуйте ещё раз чуть позже."


def catalog_keyboard(settings: Settings) -> InlineKeyboardMarkup | None:
    if not settings.mini_app_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=CATALOG_BUTTON_TEXT,
                    web_app=WebAppInfo(url=settings.mini_app_url),
                )
            ]
        ]
    )


def is_admin(message: Message, settings: Settings) -> bool:
    user = message.from_user
    return user is not None and user.id in settings.admin_ids


@router.message(CommandStart())
async def on_start(message: Message, settings: Settings) -> None:
    await message.answer(START_TEXT, reply_markup=catalog_keyboard(settings))


@router.message(Command("new"))
@router.message(F.text == "Создать товар")
async def on_new_product(message: Message, settings: Settings) -> None:
    if not is_admin(message, settings):
        await message.answer(START_TEXT, reply_markup=catalog_keyboard(settings))
        return
    await message.answer(NEW_PRODUCT_HINT)


@router.message(F.photo)
async def on_photo(
    message: Message, settings: Settings, api_client: BackendClient
) -> None:
    if not is_admin(message, settings):
        await message.answer(START_TEXT, reply_markup=catalog_keyboard(settings))
        return

    name = (message.caption or "").strip()
    if not name:
        await message.answer(NO_CAPTION_HINT)
        return

    photo = message.photo[-1]  # largest size Telegram sent
    buffer: io.BytesIO = await message.bot.download(photo)
    data = buffer.read()

    try:
        product = await api_client.create_product(
            name=name,
            data=data,
            filename=f"{photo.file_unique_id}.jpg",
            content_type="image/jpeg",
        )
    except Exception:
        logger.exception("failed to create product via backend")
        await message.answer(SAVE_ERROR_TEXT)
        return

    await message.answer(f"Товар «{name}» добавлен в каталог (id: {product['id']}).")


@router.message()
async def on_any_message(message: Message, settings: Settings) -> None:
    await message.answer(START_TEXT, reply_markup=catalog_keyboard(settings))
