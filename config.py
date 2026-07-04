from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env")

    app_name: str = "BBL Dev Fest 2026"
    debug: bool = False
    database_url: str = f"sqlite:///{BASE_DIR / 'data.db'}"


settings = Settings()
