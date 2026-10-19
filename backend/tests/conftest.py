import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db import Base
from app.main import create_app

TEST_TOKEN = "test-internal-token"


class FakeStorage:
    """In-memory stand-in for S3Storage used by the API tests."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def get(self, key: str) -> tuple[bytes, str] | None:
        return self.objects.get(key)

    async def ensure_bucket(self) -> None:
        return None


def build_app(tmp_path, storage):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/catalog-test.db",
        internal_token=TEST_TOKEN,
    )
    app = create_app(settings)
    app.state.storage = storage
    return app


@pytest_asyncio.fixture
async def storage():
    return FakeStorage()


@pytest_asyncio.fixture
async def client(tmp_path, storage):
    app = build_app(tmp_path, storage)
    async with app.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, storage


def auth_headers() -> dict[str, str]:
    return {"X-Internal-Token": TEST_TOKEN}
