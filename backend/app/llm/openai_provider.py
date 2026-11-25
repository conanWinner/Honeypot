"""OpenAI-compatible chat router (9router). Embeddings are not called here.

cx/gpt-6-luna returns a normal JSON body. Some other router models ignore
stream=false and answer as SSE, including reasoning_content deltas. This client
accepts both and never treats reasoning as the answer.

Structured output is prompted JSON plus one validation retry. The router is not
assumed to support response_format json_schema. 5xx, Cloudflare 530, and
timeouts are retried, then raised so the caller can fall back to Gemini.
"""

import json
import re
import time
import urllib.error
import urllib.request

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMError, extract_json

_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def schema_hint(schema: type[BaseModel]) -> str:
    fields = ", ".join(schema.model_fields)
    return (
        "Chỉ trả về một JSON object, không markdown, không lời dẫn. "
        f"Đúng các trường: {fields}."
    )


def repair_json(text: str) -> str:
    raw = extract_json(text or "")
    raw = raw.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    return _TRAILING_COMMA.sub(r"\1", raw)


def parse_structured(schema: type[BaseModel], text: str) -> BaseModel:
    repaired = repair_json(text)
    try:
        return schema.model_validate_json(repaired)
    except ValidationError:
        data = json.loads(repaired)
        return schema.model_validate(data)


def assemble_message(body: str, content_type: str) -> str:
    """Read assistant content from a JSON body or an SSE stream. Ignore reasoning_content."""
    raw = body or ""
    streamed = "text/event-stream" in (content_type or "").lower() or raw.lstrip().startswith("data:")
    if streamed:
        return _assemble_sse(raw)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return _content_from_payload(payload)


def _content_from_payload(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in (None, "text") and block.get("text"):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        if parts:
            return "".join(parts)
    return ""


def _assemble_sse(raw: str) -> str:
    parts: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        data = stripped[5:].strip()
        if not data or data == "[DONE]":
            if data == "[DONE]":
                break
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = event.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or choices[0].get("message") or {}
        content = delta.get("content")
        if isinstance(content, str) and content:
            parts.append(content)
    return "".join(parts)


def post_chat(url: str, api_key: str, payload: dict, timeout: float = 40) -> tuple[int, str, str]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, response.headers.get("Content-Type", ""), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, exc.headers.get("Content-Type", "") if exc.headers else "", body
    except (TimeoutError, urllib.error.URLError) as exc:
        raise LLMError(f"timeout calling router: {exc}") from exc


def status_is_retryable(status: int) -> bool:
    return status == 530 or status >= 500


class OpenAIProvider:
    """Chat through an OpenAI-compatible base URL. Not used for embeddings."""

    name = "openai-compatible"
    is_mock = False

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = 40):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.embed_model = ""

    def complete(self, schema: type[BaseModel], system: str, user: str, temperature: float = 0.4, thinking: bool = False) -> BaseModel:
        del thinking  # The router does not use Gemini's thinking budget.
        hint = schema_hint(schema)
        messages = [
            {"role": "system", "content": f"{system}\n\n{hint}"},
            {"role": "user", "content": user},
        ]
        last_error = "không rõ"
        for attempt in range(2):
            text = self._complete_text(messages, temperature)
            try:
                return parse_structured(schema, text)
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                messages = [
                    *messages,
                    {"role": "assistant", "content": (text or "")[:1500]},
                    {
                        "role": "user",
                        "content": f"JSON không hợp lệ ({exc}). Trả lại đúng một JSON object, không markdown.",
                    },
                ]
                if attempt == 0:
                    continue
        raise LLMError(f"Router không trả JSON hợp lệ: {last_error[:400]}")

    def _complete_text(self, messages: list[dict], temperature: float) -> str:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "stream": False,
            "messages": messages,
        }
        url = f"{self.base_url}/chat/completions"
        last_error = ""
        for attempt in range(3):
            try:
                status, content_type, body = post_chat(url, self.api_key, payload, self.timeout)
            except LLMError as exc:
                last_error = str(exc)
                if attempt < 2:
                    time.sleep(0.4 * (2**attempt))
                    continue
                raise
            if status_is_retryable(status):
                last_error = f"router {status}: {body[:180]}"
                if attempt < 2:
                    time.sleep(0.4 * (2**attempt))
                    continue
                raise LLMError(last_error)
            if status >= 400:
                raise LLMError(f"router {status}: {body[:300]}")
            return assemble_message(body, content_type)
        raise LLMError(last_error or "router không phản hồi")

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError("Embedding đi qua Gemini, không qua router.")


class FallbackProvider:
    """Try each chat provider in order. Never falls through to the mock."""

    is_mock = False

    def __init__(self, chain: list):
        if not chain:
            raise ValueError("Cần ít nhất một nhà cung cấp.")
        self.chain = chain
        self.name = chain[0].name
        self.model = chain[0].model
        self.embed_model = getattr(chain[0], "embed_model", "") or ""

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
        raise LLMError("Embedding không đi theo chuỗi chat.")
