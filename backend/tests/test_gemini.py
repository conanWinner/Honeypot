from types import SimpleNamespace

import app.llm.gemini as gemini
from app.agent.schemas import PersonaOutput
from app.config import Settings
from app.llm.gemini import GeminiProvider, model_chain, normalize_embedding, usable_model


def test_default_model_is_2_5_flash():
    settings = Settings(gemini_api_key="", openai_api_key="", llm_provider="mock")
    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.gemini_model_fallback == "gemini-2.5-flash"
    assert settings.embed_dim == 768


def test_lite_model_is_replaced_and_preferred_is_first():
    assert usable_model("gemini-2.5-flash-lite") == "gemini-2.5-flash"
    chain = model_chain("gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash")
    assert chain == ["gemini-3.5-flash", "gemini-2.5-flash"]
    chain = model_chain("gemini-2.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash")
    assert chain == ["gemini-2.5-flash"]


def test_embedding_is_cut_to_768_and_normalized():
    raw = [1.0] * 3072
    vector = normalize_embedding(raw, 768)
    assert len(vector) == 768
    norm = sum(value * value for value in vector) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_preferred_model_falls_back_after_503(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda *_args, **_kwargs: None)
    provider = GeminiProvider(
        "test-key",
        "gemini-2.5-flash",
        "gemini-embedding-2",
        768,
        preferred_model="gemini-3.5-flash",
    )
    calls: list[str] = []

    class Response:
        parsed = None
        text = '{"reply": "Cô nghe.", "memory_note": ""}'

    class Models:
        @staticmethod
        def generate_content(model, contents, config):
            calls.append(model)
            budget = config.thinking_config.thinking_budget
            assert budget == 0
            if model == "gemini-3.5-flash":
                raise RuntimeError("503 UNAVAILABLE")
            return Response()

    provider.client = SimpleNamespace(models=Models())
    result = provider.complete(PersonaOutput, "system", "user", thinking=False)
    assert result.reply == "Cô nghe."
    assert provider.model == "gemini-2.5-flash"
    assert calls[0] == "gemini-3.5-flash"
    assert calls.count("gemini-3.5-flash") == 3
    assert calls[-1] == "gemini-2.5-flash"


def test_extraction_keeps_a_thinking_budget(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda *_args, **_kwargs: None)
    provider = GeminiProvider("test-key", "gemini-2.5-flash", "gemini-embedding-2", 768)
    seen: list[int] = []

    class Response:
        parsed = None
        text = '{"reply": "Cô nghe.", "memory_note": ""}'

    class Models:
        @staticmethod
        def generate_content(model, contents, config):
            seen.append(config.thinking_config.thinking_budget)
            return Response()

    provider.client = SimpleNamespace(models=Models())
    provider.complete(PersonaOutput, "system", "user", thinking=True)
    assert seen == [1024]
