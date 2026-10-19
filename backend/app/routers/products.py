import hmac
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import Product
from ..schemas import ProductOut
from ..storage import S3Storage

router = APIRouter()

CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


async def get_session(request: Request):
    session_maker = request.app.state.session_maker
    async with session_maker() as session:
        yield session


def get_storage(request: Request) -> S3Storage:
    return request.app.state.storage


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_internal_token(request: Request, settings: Settings) -> None:
    token = request.headers.get("X-Internal-Token", "")
    if not hmac.compare_digest(token, settings.internal_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")


def product_out(product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        name=product.name,
        image_url=f"/api/products/{product.id}/image",
        created_at=product.created_at,
    )


@router.get("/api/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/api/products", response_model=list[ProductOut])
async def list_products(session: AsyncSession = Depends(get_session)) -> list[ProductOut]:
    result = await session.execute(select(Product).order_by(Product.id.desc()))
    return [product_out(p) for p in result.scalars().all()]


@router.post(
    "/api/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    request: Request,
    name: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    storage: S3Storage = Depends(get_storage),
    settings: Settings = Depends(get_app_settings),
) -> ProductOut:
    require_internal_token(request, settings)

    name = name.strip()
    if not name:
        raise HTTPException(422, detail="name is empty")
    if len(name) > 500:
        raise HTTPException(422, detail="name is too long (max 500 characters)")

    if file.content_type not in CONTENT_TYPE_TO_EXT:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported image type: {file.content_type}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(422, detail="empty file")
    if len(data) > settings.max_image_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="image too large")

    ext = CONTENT_TYPE_TO_EXT[file.content_type]
    key = f"products/{uuid.uuid4().hex}{ext}"
    await storage.upload(key, data, file.content_type)

    product = Product(name=name, image_key=key)
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product_out(product)


@router.get("/api/products/{product_id}/image")
async def product_image(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    storage: S3Storage = Depends(get_storage),
) -> Response:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="product not found")
    obj = await storage.get(product.image_key)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="image not found")
    data, content_type = obj
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )
