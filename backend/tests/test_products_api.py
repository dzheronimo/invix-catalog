import pytest

from .conftest import auth_headers

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_healthz(client):
    ac, _ = client
    resp = await ac.get("/api/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_catalog_is_empty_at_start(client):
    ac, _ = client
    resp = await ac.get("/api/products")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_product_requires_internal_token(client):
    ac, _ = client
    resp = await ac.post(
        "/api/products",
        data={"name": "Стул"},
        files={"file": ("chair.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 403

    resp = await ac.post(
        "/api/products",
        data={"name": "Стул"},
        files={"file": ("chair.png", PNG_BYTES, "image/png")},
        headers={"X-Internal-Token": "wrong"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_product_stores_image_and_row(client):
    ac, storage = client
    resp = await ac.post(
        "/api/products",
        data={"name": "Кружка"},
        files={"file": ("mug.png", PNG_BYTES, "image/png")},
        headers=auth_headers(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Кружка"
    assert body["image_url"] == f"/api/products/{body['id']}/image"

    assert len(storage.objects) == 1
    key, (data, content_type) = next(iter(storage.objects.items()))
    assert key.startswith("products/")
    assert key.endswith(".png")
    assert data == PNG_BYTES
    assert content_type == "image/png"

    resp = await ac.get("/api/products")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Кружка"


@pytest.mark.asyncio
async def test_create_product_validation(client):
    ac, _ = client

    resp = await ac.post(
        "/api/products",
        data={"name": "   "},
        files={"file": ("x.png", PNG_BYTES, "image/png")},
        headers=auth_headers(),
    )
    assert resp.status_code == 422

    resp = await ac.post(
        "/api/products",
        data={"name": "Файл"},
        files={"file": ("x.txt", b"not an image", "text/plain")},
        headers=auth_headers(),
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_long_name_is_rejected_before_upload(client):
    ac, storage = client
    resp = await ac.post(
        "/api/products",
        data={"name": "д" * 501},
        files={"file": ("x.png", PNG_BYTES, "image/png")},
        headers=auth_headers(),
    )
    assert resp.status_code == 422
    # Nothing may reach the storage when the row cannot be created.
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_product_image_is_served_from_storage(client):
    ac, _ = client
    resp = await ac.post(
        "/api/products",
        data={"name": "Лампа"},
        files={"file": ("lamp.png", PNG_BYTES, "image/png")},
        headers=auth_headers(),
    )
    product_id = resp.json()["id"]

    resp = await ac.get(f"/api/products/{product_id}/image")
    assert resp.status_code == 200
    assert resp.content == PNG_BYTES
    assert resp.headers["content-type"] == "image/png"

    resp = await ac.get("/api/products/9999/image")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_two_instances_share_data(client, tmp_path, storage):
    """Two app processes on one database see the same catalog (stateless check)."""
    ac_first, _ = client

    resp = await ac_first.post(
        "/api/products",
        data={"name": "Стол"},
        files={"file": ("table.png", PNG_BYTES, "image/png")},
        headers=auth_headers(),
    )
    assert resp.status_code == 201

    from httpx import ASGITransport, AsyncClient

    from .conftest import build_app

    second_app = build_app(tmp_path, storage)
    async with AsyncClient(
        transport=ASGITransport(app=second_app), base_url="http://test2"
    ) as ac_second:
        resp = await ac_second.get("/api/products")
        assert resp.status_code == 200
        names = [item["name"] for item in resp.json()]
        assert names == ["Стол"]
