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

    def __init__(self, chat, embedder):
        self._chat = chat
        self._embedder = embedder
        self.name = chat.name
        self.model = chat.model
        self.embed_model = getattr(embedder, "embed_model", "") or ""
        self.embeddings_mock = bool(getattr(embedder, "is_mock", True))

    @property
    def is_mock(self) -> bool:
        return bool(self._chat.is_mock)

    def complete(self, schema, system: str, user: str, temperature: float = 0.4, thinking: bool = False):
        result = self._chat.complete(schema, system, user, temperature, thinking=thinking)
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
    return SplitProvider(chat, embedder)
