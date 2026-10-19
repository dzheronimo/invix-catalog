from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import Settings, get_settings
from .db import Base
from .routers import products
from .storage import S3Storage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    storage = S3Storage(
        endpoint=settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Bucket and schema are ensured on startup so the stack comes up
        # with one command; storage waits for MinIO if it is still booting.
        await storage.ensure_bucket()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        await engine.dispose()

    app = FastAPI(title="INVIX Catalog API", lifespan=lifespan)
    app.state.engine = engine
    app.state.session_maker = session_maker
    app.state.storage = storage
    app.state.settings = settings
    app.include_router(products.router)
    return app


app = create_app()
