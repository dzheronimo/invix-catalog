import io

import pytest

from bot.api_client import BackendClient
from bot.config import Settings
from bot.handlers import (
    NEW_PRODUCT_HINT,
    NO_CAPTION_HINT,
    START_TEXT,
    catalog_keyboard,
    on_any_message,
    on_new_product,
    on_photo,
    on_start,
)

ADMIN_ID = 1001
OTHER_ID = 2002


def make_settings(**overrides) -> Settings:
    base = {
        "telegram_bot_token": "token",
        "telegram_admin_ids": str(ADMIN_ID),
        "backend_url": "http://backend:8000",
        "internal_token": "internal",
        "mini_app_url": "https://catalog.example.com/",
    }
    base.update(overrides)
    return Settings(**base)


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakePhoto:
    def __init__(self, unique_id: str) -> None:
        self.file_unique_id = unique_id
        self.file_id = f"file-{unique_id}"


class FakeBot:
    def __init__(self, data: bytes = b"jpeg-bytes") -> None:
        self._data = data

    async def download(self, photo) -> io.BytesIO:
        return io.BytesIO(self._data)


class FakeApiClient:
    def __init__(self) -> None:
        self.calls = []
        self.next_id = 1

    async def create_product(self, name, data, filename, content_type):
        self.calls.append(
            {
                "name": name,
                "data": data,
                "filename": filename,
                "content_type": content_type,
            }
        )
        product_id = self.next_id
        self.next_id += 1
        return {"id": product_id, "name": name}


class FakeMessage:
    def __init__(
        self,
        user_id: int,
        photo=None,
        caption: str | None = None,
        bot_data: bytes = b"jpeg-bytes",
    ) -> None:
        self.from_user = FakeUser(user_id)
        self.photo = photo
        self.caption = caption
        self.bot = FakeBot(bot_data)
        self.answers: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


def last_answer(message: FakeMessage):
    return message.answers[-1]


@pytest.mark.asyncio
async def test_start_replies_with_goods_phrase_and_mini_app_button():
    settings = make_settings()
    message = FakeMessage(user_id=OTHER_ID)
    await on_start(message, settings)
    text, keyboard = last_answer(message)
    assert text == START_TEXT
    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app.url == settings.mini_app_url


@pytest.mark.asyncio
async def test_plain_message_gets_same_reply():
    settings = make_settings()
    message = FakeMessage(user_id=OTHER_ID)
    await on_any_message(message, settings)
    text, keyboard = last_answer(message)
    assert text == START_TEXT
    assert keyboard is not None


@pytest.mark.asyncio
async def test_keyboard_absent_without_mini_app_url():
    settings = make_settings(mini_app_url="")
    assert catalog_keyboard(settings) is None


@pytest.mark.asyncio
async def test_new_product_hint_for_admin_only():
    settings = make_settings()

    admin_message = FakeMessage(user_id=ADMIN_ID)
    await on_new_product(admin_message, settings)
    assert last_answer(admin_message)[0] == NEW_PRODUCT_HINT

    user_message = FakeMessage(user_id=OTHER_ID)
    await on_new_product(user_message, settings)
    assert last_answer(user_message)[0] == START_TEXT


@pytest.mark.asyncio
async def test_admin_photo_with_caption_creates_product():
    settings = make_settings()
    client = FakeApiClient()
    message = FakeMessage(
        user_id=ADMIN_ID, photo=[FakePhoto("small"), FakePhoto("large")], caption="Ваза"
    )
    await on_photo(message, settings, client)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["name"] == "Ваза"
    assert call["data"] == b"jpeg-bytes"
    assert call["filename"] == "large.jpg"
    assert call["content_type"] == "image/jpeg"

    text, _ = last_answer(message)
    assert "Ваза" in text
    assert "id: 1" in text


@pytest.mark.asyncio
async def test_admin_photo_without_caption_is_asked_for_name():
    settings = make_settings()
    client = FakeApiClient()
    message = FakeMessage(user_id=ADMIN_ID, photo=[FakePhoto("p1")], caption=None)
    await on_photo(message, settings, client)
    assert client.calls == []
    assert last_answer(message)[0] == NO_CAPTION_HINT


@pytest.mark.asyncio
async def test_photo_from_regular_user_does_not_create_product():
    settings = make_settings()
    client = FakeApiClient()
    message = FakeMessage(user_id=OTHER_ID, photo=[FakePhoto("p1")], caption="Ваза")
    await on_photo(message, settings, client)
    assert client.calls == []
    assert last_answer(message)[0] == START_TEXT


@pytest.mark.asyncio
async def test_backend_failure_is_reported():
    settings = make_settings()

    class FailingClient:
        async def create_product(self, **kwargs):
            raise RuntimeError("backend down")

    message = FakeMessage(user_id=ADMIN_ID, photo=[FakePhoto("p1")], caption="Ваза")
    await on_photo(message, settings, FailingClient())
    assert "Не удалось сохранить" in last_answer(message)[0]


def test_real_api_client_builds_multipart_request():
    client = BackendClient("http://backend:8000/", "secret")
    assert client._base_url == "http://backend:8000"
    assert client._internal_token == "secret"
