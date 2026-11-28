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
    model_analyst: str = "ag/gemini-4-hydrogen-low"
    model_planner: str = "ag/gemini-3.8-flash-low"
    model_guard: str = "ag/gemini-3.8-flash-low"
    model_extract: str = "cx/gpt-5.6-luna"
    model_sim: str = "ag/gemini-3.8-flash-low"
    # One failover on the router, then MODEL_LAST_RESORT, then the direct Gemini key if set. Same id as the primary is skipped.
    model_persona_fallback: str = "cx/gpt-5.6-luna"
    model_analyst_fallback: str = "ag/gemini-3.8-flash-low"
    model_planner_fallback: str = "cx/gpt-5.6-luna"
    model_guard_fallback: str = "cx/gpt-5.6-luna"
    model_extract_fallback: str = "cx/gpt-6-luna"
    model_sim_fallback: str = "cx/gpt-5.6-luna"
    # Tried after a role's primary and fallback both fail. Pick another upstream than
    # ag/ and cx/ so one rate limit cannot take out all three. Empty = no extra layer.
    model_last_resort: str = "gemini/gemini-3.5-flash-lite"
    timeout_last_resort: float = 8
    # Seconds. A hung router call used to sit for 40s, then retry the same model.
    timeout_persona: float = 12
    timeout_analyst: float = 18
    timeout_planner: float = 18
    timeout_guard: float = 9
    timeout_extract: float = 30
    timeout_sim: float = 7
    # Separate budget for the one failover call. It does not reuse the primary timer.
    timeout_persona_fallback: float = 10
    timeout_analyst_fallback: float = 12
    timeout_planner_fallback: float = 12
    timeout_guard_fallback: float = 7
    timeout_extract_fallback: float = 20
    timeout_sim_fallback: float = 5
    # Whole turn, including analyst, planner, persona, repair, and guard.
    turn_deadline: float = 25
    # Skip the guard model on a short line the rules found clean that touches no
    # money, code, app, link, paper or bot question. Saves 3 to 5 s on such turns.
    guard_skip_plain: bool = True
    # Seconds the analyst may run past the planner before the turn goes on without
    # it, steering on the library match. 0 waits the analyst's full budget.
    analyst_grace: float = 1.0
    # Reliable default. gemini-2.5-flash-lite returns 404 and is rejected in the provider.
    gemini_model: str = "gemini-2.5-flash"
    # Optional. Tried first; 503, timeout, or 404 falls through to gemini_model.
    gemini_model_preferred: str = ""
    gemini_model_fallback: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768
    # Embeddings: auto = 9router when a router key is set, else Gemini. 9router | gemini | none.
    embed_provider: str = "auto"
    # Small, fast, honors dimensions=768. qwen3-embedding-8b is the quality alternative (4 s/query).
    model_embed: str = "openrouter/openai/text-embedding-3-small"
    # Must share the vector space of MODEL_EMBED (same model on another route). Empty = keyword fallback.
    model_embed_fallback: str = ""
    timeout_embed: float = 6
    # Cosine is rescaled to 0..1 before the hybrid score: (cos - floor) / span. -1 = provider default.
    embed_cos_floor: float = -1
    embed_cos_span: float = -1
    # cautious | normal | persistent. Persistent pushes the planner toward the next open checklist item.
    agent_aggressiveness: str = "normal"
    admin_token: str = ""
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
