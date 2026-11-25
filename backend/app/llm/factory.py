"""Chat and embeddings are chosen separately.

Default chat order is the OpenAI-compatible router, then Gemini. Embeddings stay
on Gemini even when chat is the router. No key at all means the bannered mock.
"""

from app.config import Settings
from app.llm.base import LLMError
from app.llm.gemini import GeminiProvider
from app.llm.mock import MockProvider
from app.llm.openai_provider import FallbackProvider, OpenAIProvider


class SplitProvider:
    """complete() follows the chat chain. embed() uses the embedding provider only."""

    def __init__(
        self,
        chat,
        embedder,
        roles: dict[str, str] | None = None,
        fallbacks: dict[str, str] | None = None,
        timeouts: dict[str, float] | None = None,
        fallback_timeouts: dict[str, float] | None = None,
    ):
        self._chat = chat
        self._embedder = embedder
        self.role_models = roles or {}
        self.role_fallbacks = fallbacks or {}
        self.role_timeouts = timeouts or {}
        self.role_fallback_timeouts = fallback_timeouts or {}
        self.name = chat.name
        self.model = chat.model
        self.embed_model = getattr(embedder, "embed_model", "") or ""
        self.embeddings_mock = bool(getattr(embedder, "is_mock", True))

    @property
    def is_mock(self) -> bool:
        return bool(self._chat.is_mock)

    def complete(
        self,
        schema,
        system: str,
        user: str,
        temperature: float = 0.4,
        thinking: bool = False,
        model: str | None = None,
        role: str = "",
        max_tokens: int | None = None,
        timeout: float | None = None,
        fallback_model: str | None = None,
        fallback_timeout: float | None = None,
    ):
        chosen = (model or "").strip()
        if not chosen and role:
            chosen = (self.role_models.get(role) or "").strip()
        alt = (fallback_model or "").strip()
        if not alt and role:
            alt = (self.role_fallbacks.get(role) or "").strip()
        budget = timeout if timeout and timeout > 0 else self.role_timeouts.get(role)
        alt_budget = fallback_timeout if fallback_timeout and fallback_timeout > 0 else self.role_fallback_timeouts.get(role)
        result = self._chat.complete(
            schema,
            system,
            user,
            temperature,
            thinking=thinking,
            model=chosen or None,
            role=role,
            max_tokens=max_tokens,
            timeout=budget,
            fallback_model=alt or None,
            fallback_timeout=alt_budget,
        )
        self.name = self._chat.name
        self.model = self._chat.model
        return result

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.embeddings_mock:
            raise LLMError("Chưa cấu hình Gemini cho embedding.")
        vectors = self._embedder.embed(texts)
        self.embed_model = self._embedder.embed_model
        return vectors


def router_api_key(settings: Settings) -> str:
    return (settings.llm_api_key or settings.openai_api_key or "").strip()


def role_model(settings: Settings, role: str) -> str:
    raw = (getattr(settings, f"model_{role}", "") or "").strip()
    return raw or settings.openai_model


def role_models(settings: Settings) -> dict[str, str]:
    return {role: role_model(settings, role) for role in ("persona", "analyst", "planner", "guard", "extract", "sim")}


def role_fallbacks(settings: Settings) -> dict[str, str]:
    found = {}
    for role in ("persona", "analyst", "planner", "guard", "extract", "sim"):
        raw = (getattr(settings, f"model_{role}_fallback", "") or "").strip()
        primary = role_model(settings, role)
        if raw and raw != primary:
            found[role] = raw
    return found


def role_timeouts(settings: Settings) -> dict[str, float]:
    return {
        "persona": float(settings.timeout_persona),
        "analyst": float(settings.timeout_analyst),
        "planner": float(settings.timeout_planner),
        "guard": float(settings.timeout_guard),
        "extract": float(settings.timeout_extract),
        "sim": float(settings.timeout_sim),
    }


def role_fallback_timeouts(settings: Settings) -> dict[str, float]:
    return {
        "persona": float(settings.timeout_persona_fallback),
        "analyst": float(settings.timeout_analyst_fallback),
        "planner": float(settings.timeout_planner_fallback),
        "guard": float(settings.timeout_guard_fallback),
        "extract": float(settings.timeout_extract_fallback),
        "sim": float(settings.timeout_sim_fallback),
    }


def build_provider(settings: Settings):
    mode = (settings.llm_provider or "auto").strip().lower()
    if mode == "mock":
        return MockProvider()

    gemini = None
    if settings.gemini_api_key:
        gemini = GeminiProvider(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.gemini_embed_model,
            settings.embed_dim,
            preferred_model=settings.gemini_model_preferred,
            fallback_model=settings.gemini_model_fallback,
        )
    openai = None
    key = router_api_key(settings)
    if key:
        openai = OpenAIProvider(key, settings.openai_model, settings.openai_base_url)

    if mode == "gemini":
        chain = [item for item in (gemini, openai) if item]
    else:
        # auto, openai, openai-compatible: router first, Gemini if the tunnel fails.
        chain = [item for item in (openai, gemini) if item]

    if not chain:
        return MockProvider()
    chat = chain[0] if len(chain) == 1 else FallbackProvider(chain)
    embedder = gemini if gemini is not None else MockProvider()
    return SplitProvider(
        chat,
        embedder,
        role_models(settings),
        role_fallbacks(settings),
        role_timeouts(settings),
        role_fallback_timeouts(settings),
    )
