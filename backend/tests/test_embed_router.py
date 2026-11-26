import math

import pytest

from app.config import Settings
from app.llm import openai_provider as op
from app.llm.base import LLMError
from app.llm.factory import build_provider


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_router_is_default_embedder_with_key():
    provider = build_provider(Settings(llm_provider="auto", llm_api_key="k", gemini_api_key="", _env_file=None))
    assert not provider.embeddings_mock
    assert provider.embed_model == "openrouter/openai/text-embedding-3-small"
    assert provider.embed_cos_floor == pytest.approx(0.28)


def test_gemini_embedder_when_asked():
    provider = build_provider(Settings(llm_provider="auto", llm_api_key="k", gemini_api_key="g", embed_provider="gemini", _env_file=None))
    assert provider.embed_model == "gemini-embedding-001"
    assert provider.embed_cos_floor == 0.0


def test_embed_none_means_keyword_only():
    provider = build_provider(Settings(llm_provider="auto", llm_api_key="k", embed_provider="none", _env_file=None))
    assert provider.embeddings_mock


def test_embedder_sends_dimensions_and_truncates(monkeypatch):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(json)
        seen["ua"] = headers["User-Agent"]
        return _Resp(200, {"data": [{"index": i, "embedding": [1.0] * 1536} for i in range(len(json["input"]))]})

    monkeypatch.setattr(op.httpx, "post", fake_post)
    emb = op.OpenAIEmbedder("k", "https://x/v1", "m", 768)
    vectors = emb.embed(["a", "b"])
    assert seen["dimensions"] == 768 and seen["ua"].startswith("gia-nan")
    assert len(vectors) == 2 and len(vectors[0]) == 768
    assert math.isclose(sum(v * v for v in vectors[0]), 1.0, rel_tol=1e-6)


def test_embedder_pauses_on_429(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(1)
        return _Resp(429, text="rate")

    monkeypatch.setattr(op.httpx, "post", fake_post)
    emb = op.OpenAIEmbedder("k", "https://x/v1", "m", 768)
    with pytest.raises(LLMError, match="paused"):
        emb.embed(["a"])
    with pytest.raises(LLMError, match="paused"):
        emb.embed(["a"])
    assert len(calls) == 1
