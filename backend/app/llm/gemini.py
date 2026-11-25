"""Gemini Flash for the agent, Gemini embeddings for the library."""

from pydantic import BaseModel
from google import genai
from google.genai import types

from app.llm.base import LLMError, extract_json


class GeminiProvider:
    name = "gemini"
    is_mock = False

    def __init__(self, api_key: str, model: str, embed_model: str, dim: int):
        self.model = model
        self.embed_model = embed_model
        self.dim = dim
        self.client = genai.Client(api_key=api_key)

    def complete(self, schema: type[BaseModel], system: str, user: str, temperature: float = 0.4) -> BaseModel:
        errors: list[str] = []
        attempts = (
            {"thinking": True, "schema": schema},
            {"thinking": False, "schema": schema},
            {"thinking": False, "json_schema": schema.model_json_schema()},
        )
        for attempt in attempts:
            try:
                config_kwargs = {
                    "system_instruction": system,
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                }
                if "schema" in attempt:
                    config_kwargs["response_schema"] = attempt["schema"]
                else:
                    config_kwargs["response_json_schema"] = attempt["json_schema"]
                if attempt["thinking"]:
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW
                    )
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, schema):
                    return parsed
                if isinstance(parsed, dict):
                    return schema.model_validate(parsed)
                return schema.model_validate_json(extract_json(response.text or ""))
            except Exception as exc:  # noqa: BLE001 — retry once without thinking
                errors.append(str(exc))
        raise LLMError(f"Gemini không trả JSON hợp lệ: {errors[-1][:400]}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        try:
            for start in range(0, len(texts), 16):
                chunk = texts[start : start + 16]
                result = self.client.models.embed_content(
                    model=self.embed_model,
                    contents=chunk,
                    config=types.EmbedContentConfig(output_dimensionality=self.dim),
                )
                for item in result.embeddings:
                    vectors.append([float(value) for value in item.values])
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Gemini embedding lỗi: {exc}") from exc
        if len(vectors) != len(texts):
            raise LLMError("Gemini trả thiếu embedding.")
        return vectors
