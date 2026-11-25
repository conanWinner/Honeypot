"""Runtime configuration. Keys come from the environment, never from the repo."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://gianan:gianan@localhost:5433/gianan"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    # auto | gemini | openai | mock
    llm_provider: str = "auto"
    gemini_model: str = "gemini-3.8-flash"
    gemini_embed_model: str = "gemini-embedding-2"
    openai_model: str = "gpt-6-luna"
    openai_embed_model: str = "text-embedding-3-small"
    embed_dim: int = 768
    admin_token: str = ""
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
