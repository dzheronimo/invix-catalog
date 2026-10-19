from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend configuration, taken from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://catalog:catalog@localhost:5432/catalog"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "catalog-images"
    s3_region: str = "us-east-1"
    # Shared secret between the bot and the backend: only the bot may create products.
    internal_token: str = "change-me"
    max_image_bytes: int = 10 * 1024 * 1024


def get_settings() -> Settings:
    return Settings()
