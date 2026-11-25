"""Pick Gemini, then OpenAI, then an explicit mock when no key is configured."""

from app.config import Settings
from app.llm.gemini import GeminiProvider
from app.llm.mock import MockProvider
from app.llm.openai_provider import FallbackProvider, OpenAIProvider


def build_provider(settings: Settings):
    mode = (settings.llm_provider or "auto").strip().lower()
    gemini = None
    openai = None
    if settings.gemini_api_key:
        gemini = GeminiProvider(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.gemini_embed_model,
            settings.embed_dim,
            preferred_model=settings.gemini_model_preferred,
            fallback_model=settings.gemini_model_fallback,
        )
    if settings.openai_api_key:
        openai = OpenAIProvider(
            settings.openai_api_key,
            settings.openai_model,
            settings.openai_embed_model,
            settings.embed_dim,
        )

    if mode == "mock":
        return MockProvider()
    if mode == "gemini":
        chain = [item for item in (gemini, openai) if item]
    elif mode == "openai":
        chain = [item for item in (openai, gemini) if item]
    else:
        chain = [item for item in (gemini, openai) if item]

    if not chain:
        return MockProvider()
    if len(chain) == 1:
        return chain[0]
    return FallbackProvider(chain)
