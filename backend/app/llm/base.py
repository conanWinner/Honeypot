"""Provider interface. Gemini is primary, OpenAI is the fallback, mock is not a silent stand-in."""

from typing import Protocol

from pydantic import BaseModel


class LLMError(RuntimeError):
    pass


class LLMProvider(Protocol):
    name: str
    is_mock: bool
    model: str
    embed_model: str

    def complete(self, schema: type[BaseModel], system: str, user: str, temperature: float = 0.4) -> BaseModel: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def extract_json(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return raw
