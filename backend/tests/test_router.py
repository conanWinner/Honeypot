import json

import pytest

from app.agent.prompts import PERSONA_SYSTEM
from app.agent.schemas import PersonaOutput
from app.config import Settings
from app.llm.base import LLMError
from app.llm.factory import build_provider
from app.llm.openai_provider import (
    FallbackProvider,
    OpenAIProvider,
    assemble_message,
    parse_structured,
    repair_json,
)


def test_json_body_ignores_reasoning_content():
    body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": '{"reply": "Cô nghe.", "memory_note": "n"}',
                        "reasoning_content": "secret chain of thought",
                    }
                }
            ]
        }
    )
    text = assemble_message(body, "application/json")
    assert "secret" not in text
    parsed = parse_structured(PersonaOutput, text)
    assert parsed.reply == "Cô nghe."


def test_sse_assembles_content_and_drops_reasoning():
    def chunk(delta: dict) -> str:
        return "data: " + json.dumps({"choices": [{"delta": delta}]})

    body = "\n".join(
        [
            chunk({"reasoning_content": "thinking"}),
            chunk({"content": '{"reply": "'}),
            chunk({"content": 'Cô nghe.", "memory_note": "n"}'}),
            "data: [DONE]",
        ]
    )
    text = assemble_message(body, "text/event-stream")
    assert "thinking" not in text
    parsed = parse_structured(PersonaOutput, text)
    assert parsed.reply == "Cô nghe."


def test_trailing_comma_is_repaired():
    raw = repair_json('{"reply": "Cô nghe.", "memory_note": "n",}')
    assert parse_structured(PersonaOutput, raw).memory_note == "n"


def test_validation_retries_once(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, api_key, payload, timeout=40):
        calls["n"] += 1
        if calls["n"] == 1:
            content = "không phải json"
        else:
            content = '{"reply": "Cô nghe.", "memory_note": "n"}'
        body = json.dumps({"choices": [{"message": {"content": content}}]})
        return 200, "application/json", body

    monkeypatch.setattr("app.llm.openai_provider.post_chat", fake_post)
    provider = OpenAIProvider("secret-key", "cx/gpt-6-luna", "https://router.example/v1")
    parsed = provider.complete(PersonaOutput, "system", "user")
    assert parsed.reply == "Cô nghe."
    assert calls["n"] == 2


def test_cloudflare_530_fails_over_once_then_raises(monkeypatch):
    calls = []

    def fake_post(url, api_key, payload, timeout=40):
        calls.append((payload["model"], timeout))
        assert api_key == "secret-key"
        assert payload["stream"] is False
        return 530, "text/html", "cloudflare"

    monkeypatch.setattr("app.llm.openai_provider.post_chat", fake_post)
    provider = OpenAIProvider("secret-key", "cx/gpt-6-luna", "https://router.example/v1")
    with pytest.raises(LLMError, match="530"):
        provider.complete(PersonaOutput, "system", "user", timeout=12, fallback_model="cx/gpt-5.6-luna")
    assert calls == [("cx/gpt-6-luna", 12), ("cx/gpt-5.6-luna", 12)]


def test_router_failure_falls_through_to_next_chat_provider():
    class Boom:
        name = "openai-compatible"
        model = "cx/gpt-6-luna"
        is_mock = False

        def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
            raise LLMError("router 530: cloudflare")

    class Ok:
        name = "gemini"
        model = "gemini-2.5-flash"
        is_mock = False

        def complete(self, schema, system, user, temperature=0.4, thinking=False, **kwargs):
            return schema(reply="Cô nghe.", memory_note="n")

    provider = FallbackProvider([Boom(), Ok()])
    assert provider.complete(PersonaOutput, "", "").reply == "Cô nghe."
    assert provider.name == "gemini"


def test_default_chat_order_is_router_then_gemini_embeddings_stay_gemini():
    settings = Settings(
        llm_api_key="router-key",
        gemini_api_key="gem-key",
        llm_provider="auto",
        openai_base_url="https://router.example/v1",
        openai_model="cx/gpt-6-luna",
    )
    provider = build_provider(settings)
    assert provider.is_mock is False
    assert provider.embeddings_mock is False
    assert provider.embed_model == "gemini-embedding-001"
    assert provider.role_models["persona"] == "cx/gpt-6-luna"
    assert provider.role_models["analyst"] == "ag/gemini-3.8-flash-low"
    assert provider.role_models["guard"] == "ag/gemini-3.8-flash-low"
    assert provider.role_models["extract"] == "cx/gpt-5.6-luna"
    assert provider._chat.chain[0].name == "openai-compatible"
    assert provider._chat.chain[0].model == "cx/gpt-6-luna"
    assert provider._chat.chain[0].base_url == "https://router.example/v1"
    assert provider._chat.chain[1].name == "gemini"


def test_gemini_mode_reverses_the_chat_order():
    settings = Settings(
        llm_api_key="router-key",
        gemini_api_key="gem-key",
        llm_provider="gemini",
    )
    provider = build_provider(settings)
    assert provider._chat.chain[0].name == "gemini"
    assert provider._chat.chain[1].name == "openai-compatible"


def test_router_without_gemini_does_not_embed_via_router():
    settings = Settings(llm_api_key="router-key", gemini_api_key="", llm_provider="openai-compatible")
    provider = build_provider(settings)
    assert provider.is_mock is False
    assert provider.embeddings_mock is True
    with pytest.raises(LLMError):
        provider.embed(["tin nhắn lừa đảo"])


def test_persona_prompt_teaches_naive_stalling():
    assert "chậm hiểu" in PERSONA_SYSTEM
    assert "mã vận đơn qua ứng dụng" in PERSONA_SYSTEM
    assert "Ủa đơn nào vậy" in PERSONA_SYSTEM
    assert "đổi đại từ cho đúng hồ sơ" in PERSONA_SYSTEM
