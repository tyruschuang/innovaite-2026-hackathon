from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # OpenFEMA
    fema_api_base: str = "https://www.fema.gov/api/open/v2"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
