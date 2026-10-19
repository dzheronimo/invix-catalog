from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot configuration, taken from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    # Comma-separated Telegram user ids allowed to add products.
    telegram_admin_ids: str = ""
    backend_url: str = "http://localhost:8000"
    internal_token: str = "change-me"
    # Public https URL of the catalog page, opened by the Mini App button.
    mini_app_url: str = ""

    @property
    def admin_ids(self) -> set[int]:
        return {
            int(part)
            for part in self.telegram_admin_ids.replace(" ", "").split(",")
            if part
        }
