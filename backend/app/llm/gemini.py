"""Gemini Flash for the agent, Gemini embeddings for the library.

Per-turn calls disable thinking (thinking_budget=0). That is the difference between
about 0.7s and 6–8s on gemini-2.5-flash. Script extraction is the only call that
keeps a thinking budget. 503 and timeouts retry with a short backoff, then the
next model in the chain (preferred, then the configured model, then 2.5-flash).
"""

import time

from pydantic import BaseModel
from google import genai
from google.genai import types

from app.llm.base import LLMError, extract_json

_BLOCKED_MODELS = ("gemini-2.5-flash-lite",)
_RETRYABLE = ("503", "unavailable", "timeout", "timed out", "deadline", "429", "resource exhausted", "overloaded")
_SWITCH = ("404", "not found", "not_found", "400", "invalid argument", "api version", "api_version")


def usable_model(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if any(blocked in lowered for blocked in _BLOCKED_MODELS):
        return "gemini-2.5-flash"
    return cleaned


def model_chain(preferred: str, primary: str, fallback: str) -> list[str]:
    ordered: list[str] = []
    for name in (preferred, primary, fallback or "gemini-2.5-flash"):
        cleaned = usable_model(name)
        if cleaned and cleaned not in ordered:
            ordered.append(cleaned)
    return ordered or ["gemini-2.5-flash"]


def is_retryable(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(token in message for token in _RETRYABLE)


def should_switch_model(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(token in message for token in _SWITCH) or is_retryable(exc)


def normalize_embedding(values: list[float], dim: int) -> list[float]:
    """Matryoshka models default to 3072. The column is vector(768), so cut and renormalize."""
    vector = [float(value) for value in values]
    if len(vector) > dim:
        vector = vector[:dim]
    elif len(vector) < dim:
        vector = vector + [0.0] * (dim - len(vector))
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class GeminiProvider:
    name = "gemini"
    is_mock = False

    def __init__(
        self,
        api_key: str,
        model: str,
        embed_model: str,
        dim: int,
        preferred_model: str = "",
        fallback_model: str = "gemini-2.5-flash",
    ):
        self.models = model_chain(preferred_model, model, fallback_model)
        self.model = self.models[0]
        self.embed_model = usable_model(embed_model) or "gemini-embedding-001"
        self.dim = dim
        # The stable Gemini API for generateContent on these models is v1beta.
        # The SDK default (v1) returns 400 for every chat call.
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))

    def complete(
        self,
        schema: type[BaseModel],
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
    ) -> BaseModel:
        del model, role, timeout, fallback_model, fallback_timeout  # Router ids stay off the Gemini API.
        errors: list[str] = []
        for model_name in self.models:
            try:
                parsed = self._complete_one(model_name, schema, system, user, temperature, thinking, max_tokens)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{model_name}: {exc}")
                if not should_switch_model(exc):
                    break
                continue
            self.model = model_name
            return parsed
        raise LLMError(f"Gemini không trả JSON hợp lệ: {errors[-1][:400]}")

    def _complete_one(
        self,
        model_name: str,
        schema: type[BaseModel],
        system: str,
        user: str,
        temperature: float,
        thinking: bool,
        max_tokens: int | None = None,
    ) -> BaseModel:
        configs = self._configs(schema, system, temperature, thinking, max_tokens)
        last_error: Exception | None = None
        for index, config in enumerate(configs):
            attempts = 3 if index == 0 else 1
            for attempt in range(attempts):
                try:
                    response = self.client.models.generate_content(model=model_name, contents=user, config=config)
                    parsed = getattr(response, "parsed", None)
                    if isinstance(parsed, schema):
                        return parsed
                    if isinstance(parsed, dict):
                        return schema.model_validate(parsed)
                    return schema.model_validate_json(extract_json(response.text or ""))
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if is_retryable(exc) and attempt < attempts - 1:
                        time.sleep(0.4 * (2**attempt))
                        continue
                    if is_retryable(exc):
                        raise
                    break
        assert last_error is not None
        raise last_error

    def _configs(self, schema: type[BaseModel], system: str, temperature: float, thinking: bool, max_tokens: int | None = None) -> list:
        base = {
            "system_instruction": system,
            "temperature": temperature,
            "response_mime_type": "application/json",
        }
        if max_tokens:
            base["max_output_tokens"] = max_tokens
        thinking_on = types.ThinkingConfig(thinking_budget=1024)
        thinking_off = types.ThinkingConfig(thinking_budget=0)
        chosen = thinking_on if thinking else thinking_off
        return [
            types.GenerateContentConfig(**base, response_schema=schema, thinking_config=chosen),
            types.GenerateContentConfig(**base, response_schema=schema),
            types.GenerateContentConfig(**base, response_json_schema=schema.model_json_schema()),
        ]

    def embed(self, texts: list[str]) -> list[list[float]]:
        # One text per call. gemini-embedding-2 returns a single vector for a batch,
        # which makes a backfill look successful and then fail the length check.
        if not texts:
            return []
        vectors: list[list[float]] = []
        try:
            for text in texts:
                result = self._embed_with_retry([text])
                embeddings = list(result.embeddings or [])
                if not embeddings:
                    raise LLMError("Gemini trả thiếu embedding.")
                vectors.append(normalize_embedding(list(embeddings[0].values), self.dim))
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Gemini embedding lỗi: {exc}") from exc
        return vectors

    def _embed_with_retry(self, chunk: list[str]):
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return self.client.models.embed_content(
                    model=self.embed_model,
                    contents=chunk,
                    config=types.EmbedContentConfig(output_dimensionality=self.dim),
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if is_retryable(exc) and attempt < 2:
                    time.sleep(0.4 * (2**attempt))
                    continue
                raise
        raise last_error  # pragma: no cover
