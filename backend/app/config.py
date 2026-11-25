"""Runtime configuration. Keys come from the environment, never from the repo."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())

    database_url: str = "postgresql+psycopg://gianan:gianan@localhost:5433/gianan"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    # Router key. OPENAI_API_KEY is accepted as an alias when this is empty.
    llm_api_key: str = ""
    # auto and openai-compatible: router first, Gemini fallback. gemini: the reverse. mock: tests.
    llm_provider: str = "auto"
    openai_base_url: str = "https://rm7g66d.abc-tunnel.us/v1"
    openai_model: str = "cx/gpt-6-luna"
    # Per-role router models. Empty falls back to OPENAI_MODEL. Small models only.
    model_persona: str = "cx/gpt-6-luna"
    model_analyst: str = "ag/gemini-3.8-flash-low"
    model_planner: str = "ag/gemini-3.8-flash-low"
    model_guard: str = "ag/gemini-3.8-flash-low"
    model_extract: str = "cx/gpt-5.6-luna"
    # Reliable default. gemini-2.5-flash-lite returns 404 and is rejected in the provider.
    gemini_model: str = "gemini-2.5-flash"
    # Optional. Tried first; 503, timeout, or 404 falls through to gemini_model.
    gemini_model_preferred: str = ""
    gemini_model_fallback: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768
    # cautious | normal | persistent. Persistent pushes the planner toward the next open checklist item.
    agent_aggressiveness: str = "normal"
    admin_token: str = ""
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
