"""OpenAI fallback for chat and embeddings. Used only when Gemini is missing or fails."""

from pydantic import BaseModel
from openai import OpenAI

from app.llm.base import LLMError, extract_json


class OpenAIProvider:
    name = "openai"
    is_mock = False

    def __init__(self, api_key: str, model: str, embed_model: str, dim: int):
        self.model = model
        self.embed_model = embed_model
        self.dim = dim
        self.client = OpenAI(api_key=api_key)

    def complete(self, schema: type[BaseModel], system: str, user: str, temperature: float = 0.4, thinking: bool = False) -> BaseModel:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        schema_body = schema.model_json_schema()
        attempts = (
            {"temperature": temperature, "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema_body, "strict": False},
            }},
            {"temperature": temperature, "response_format": {"type": "json_object"}},
            {},
        )
        last_error = "không rõ"
        for extra in attempts:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **extra,
                )
                text = response.choices[0].message.content or ""
                return schema.model_validate_json(extract_json(text))
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
        if hasattr(self.client, "responses"):
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user + "\n\nChỉ trả về một JSON object, không markdown."},
                    ],
                )
                text = getattr(response, "output_text", "") or ""
                return schema.model_validate_json(extract_json(text))
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
        raise LLMError(f"OpenAI không trả JSON hợp lệ: {last_error[:400]}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self.client.embeddings.create(
                model=self.embed_model,
                input=texts,
                dimensions=self.dim,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"OpenAI embedding lỗi: {exc}") from exc
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]


class FallbackProvider:
    """Try each real provider in order. Never falls through to the mock."""

    is_mock = False

    def __init__(self, chain: list):
        if not chain:
            raise ValueError("Cần ít nhất một nhà cung cấp.")
        self.chain = chain
        self.name = chain[0].name
        self.model = chain[0].model
        self.embed_model = chain[0].embed_model

    def complete(self, schema: type[BaseModel], system: str, user: str, temperature: float = 0.4, thinking: bool = False) -> BaseModel:
        errors: list[str] = []
        for provider in self.chain:
            try:
                result = provider.complete(schema, system, user, temperature, thinking=thinking)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.name}: {exc}")
                continue
            self.name = provider.name
            self.model = provider.model
            return result
        raise LLMError(" ; ".join(errors))

    def embed(self, texts: list[str]) -> list[list[float]]:
        errors: list[str] = []
        for provider in self.chain:
            try:
                vectors = provider.embed(texts)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.name}: {exc}")
                continue
            self.embed_model = provider.embed_model
            return vectors
        raise LLMError(" ; ".join(errors))
