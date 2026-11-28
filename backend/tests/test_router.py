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


def test_every_chat_call_sets_stream_false(monkeypatch):
    payloads = []

    class Response:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = json.dumps({"choices": [{"message": {"content": '{"reply": "Cô nghe.", "memory_note": "n"}'}}]})

    def fake_post(url, headers=None, json=None, timeout=None):
        payloads.append(dict(json or {}))
        return Response()

    monkeypatch.setattr("app.llm.openai_provider.httpx.post", fake_post)
    provider = OpenAIProvider("secret-key", "ag/gemini-3.8-flash-low", "https://router.example/v1")
    provider.complete(PersonaOutput, "system", "user")
    provider.complete_text("system", "user", role="sim", max_tokens=120, timeout=7)
    assert len(payloads) >= 2
    assert all(item.get("stream") is False for item in payloads)


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
    assert [item[0] for item in calls] == ["cx/gpt-6-luna", "cx/gpt-5.6-luna"]
    assert calls[0][1] <= 12
    assert calls[1][1] <= 12


def test_fallback_keeps_its_own_budget(monkeypatch):
    calls = []

    def fake_post(url, api_key, payload, timeout=40):
        calls.append((payload["model"], timeout))
        return 530, "text/html", "cloudflare"

    monkeypatch.setattr("app.llm.openai_provider.post_chat", fake_post)
    provider = OpenAIProvider("secret-key", "primary", "https://router.example/v1")
    with pytest.raises(LLMError):
        provider.complete(PersonaOutput, "system", "user", timeout=9, fallback_timeout=7, fallback_model="fallback")
    assert [item[0] for item in calls] == ["primary", "fallback"]
    assert calls[0][1] >= 8
    assert 6 <= calls[1][1] <= 7.2


def test_slow_primary_is_hedged(monkeypatch):
    import time

    def fake_post(url, api_key, payload, timeout=40):
        if payload["model"] == "slow-primary":
            time.sleep(1.2)
        content = json.dumps({"reply": payload["model"], "memory_note": ""})
        body = json.dumps({"choices": [{"message": {"content": content}}]})
        return 200, "application/json", body

    monkeypatch.setattr("app.llm.openai_provider.post_chat", fake_post)
    provider = OpenAIProvider("secret-key", "slow-primary", "https://router.example/v1")
    started = time.perf_counter()
    parsed = provider.complete(
        PersonaOutput,
        "system",
        "user",
        timeout=1.0,
        fallback_timeout=1.0,
        fallback_model="fast-alt",
    )
    elapsed = time.perf_counter() - started
    assert parsed.reply == "fast-alt"
    assert elapsed < 1.0


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


def test_default_chat_order_is_router_then_gemini_embeddings_via_router():
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
    assert provider.embed_model == "openrouter/openai/text-embedding-3-small"
    assert provider.role_models["persona"] == "cx/gpt-6-luna"
    assert provider.role_models["analyst"] == "ag/gemini-4-hydrogen-low"
    assert provider.role_models["guard"] == "ag/gemini-3.8-flash-low"
    assert provider.role_models["extract"] == "cx/gpt-5.6-luna"
    assert provider._chat.chain[0].name == "openai-compatible"
    assert provider._chat.chain[0].model == "cx/gpt-6-luna"
    assert provider._chat.chain[0].base_url == "https://router.example/v1"
    assert provider._chat.chain[1].name == "router-last-resort"
    assert provider._chat.chain[1].model == "gemini/gemini-3.5-flash-lite"
    assert provider._chat.chain[2].name == "gemini"


def test_last_resort_runs_after_role_models_and_ignores_them():
    from app.agent.schemas import SafetyOutput
    from app.llm.openai_provider import FallbackProvider, LastResortProvider

    calls = []

    class Router:
        name = "openai-compatible"
        model = "cx/gpt-6-luna"

        def complete(self, schema, system, user, temperature=0.4, **kw):
            calls.append((kw["model"], kw.get("fallback_model")))
            if kw["model"] != "gemini/gemini-3.5-flash-lite":
                raise RuntimeError("router 503")
            return schema(action="allow")

    router = Router()
    chat = FallbackProvider([router, LastResortProvider(router, "gemini/gemini-3.5-flash-lite")])
    out = chat.complete(SafetyOutput, "s", "u", model="ag/gemini-3.8-flash-low", fallback_model="cx/gpt-5.6-luna")
    assert out.action == "allow"
    assert calls == [("ag/gemini-3.8-flash-low", "cx/gpt-5.6-luna"), ("gemini/gemini-3.5-flash-lite", None)]


def test_no_last_resort_when_unset_and_no_gemini_key():
    settings = Settings(llm_api_key="router-key", gemini_api_key="", model_last_resort="", llm_provider="auto")
    provider = build_provider(settings)
    assert provider._chat.name == "openai-compatible"


def test_gemini_mode_reverses_the_chat_order():
    settings = Settings(
        llm_api_key="router-key",
        gemini_api_key="gem-key",
        llm_provider="gemini",
    )
    provider = build_provider(settings)
    assert provider._chat.chain[0].name == "gemini"
    assert provider._chat.chain[1].name == "openai-compatible"


def test_embed_provider_none_keeps_keyword_search():
    settings = Settings(llm_api_key="router-key", gemini_api_key="", llm_provider="openai-compatible", embed_provider="none")
    provider = build_provider(settings)
    assert provider.is_mock is False
    assert provider.embeddings_mock is True
    with pytest.raises(LLMError):
        provider.embed(["tin nhắn lừa đảo"])


def test_persona_prompt_teaches_naive_stalling():
    # Naive, not an expert: no lecturing, no official-channel advice.
    assert "ứng dụng chính thức" in PERSONA_SYSTEM
    assert "không rành" in PERSONA_SYSTEM
    # Shows a machine-sounding reply next to a human one.
    assert "Ơ đơn nào vậy" in PERSONA_SYSTEM
    assert "đổi theo hồ sơ" in PERSONA_SYSTEM
    # The loudest tells from the Turing-test studies and the review of our transcripts.
    assert "anh/chị" in PERSONA_SYSTEM
    assert "KHÔNG phải tin nào cũng nói" in PERSONA_SYSTEM


def test_rate_limited_model_cools_down_and_role_goes_to_fallback(monkeypatch):
    from app.agent.schemas import SafetyOutput
    from app.llm import openai_provider as op

    calls = []

    def fake_post(url, key, payload, timeout):
        calls.append(payload["model"])
        if payload["model"] == "ag/gemini-3.8-flash-low":
            return 503, "application/json", '{"error":{"message":"[antigravity] [403]: HTTP 403 (reset after 1m 30s)"}}'
        return 200, "application/json", json.dumps({"choices": [{"message": {"content": '{"action":"allow"}'}}]})

    monkeypatch.setattr(op, "post_chat", fake_post)
    provider = op.OpenAIProvider("k", "cx/gpt-6-luna", "https://router.example/v1")
    first = provider.complete(SafetyOutput, "s", "u", model="ag/gemini-3.8-flash-low", fallback_model="cx/gpt-5.6-luna", timeout=5)
    assert first.action == "allow"
    assert op.is_cooling("ag/gemini-3.8-flash-low")
    assert 80 < op.cooling_models()["ag/gemini-3.8-flash-low"] <= 92
    calls.clear()
    provider.complete(SafetyOutput, "s", "u", model="ag/gemini-3.8-flash-low", fallback_model="cx/gpt-5.6-luna", timeout=5)
    # Second call skips the cooling model entirely.
    assert calls == ["cx/gpt-5.6-luna"]
