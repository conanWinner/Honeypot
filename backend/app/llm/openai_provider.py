"""OpenAI-compatible chat router (9router). Embeddings are not called here.

cx/gpt-6-luna returns a normal JSON body. Some other router models ignore
stream=false and answer as SSE, including reasoning_content deltas. This client
accepts both and never treats reasoning as the answer.

Structured output is prompted JSON plus one validation retry. The router is not
assumed to support response_format json_schema. 5xx, Cloudflare 530, and
timeouts are retried, then raised so the caller can fall back to Gemini.
"""

import json
import logging
import re
import threading

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMError, extract_json

_TRAILING_COMMA = re.compile(r",\s*([}\]])")
log = logging.getLogger("gianan.llm")
_failover_lock = threading.Lock()
_failover_counts: dict[str, int] = {}


def failover_counts() -> dict[str, int]:
    with _failover_lock:
        return dict(_failover_counts)


def _record_failover(role: str, model: str, reason: str) -> None:
    key = role or "unknown"
    with _failover_lock:
        _failover_counts[key] = _failover_counts.get(key, 0) + 1
    log.warning("llm failover role=%s model=%s reason=%s", key, model, (reason or "")[:180])


def schema_hint(schema: type[BaseModel]) -> str:
    body = schema.model_json_schema()
    fields = ", ".join(schema.model_fields)
    return (
        "Chỉ trả về một JSON object, không markdown, không lời dẫn. "
        f"Đúng các trường: {fields}. "
        f"Schema: {json.dumps(body, ensure_ascii=False)}"
    )


def json_schema_format(schema: type[BaseModel]) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "schema": schema.model_json_schema(),
            "strict": False,
        },
    }


def request_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "gia-nan/1.0",
    }


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
    headers = request_headers(api_key)
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise LLMError(f"timeout calling router: {exc}") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"timeout calling router: {exc}") from exc
    return response.status_code, response.headers.get("content-type", ""), response.text


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
        del thinking
        # One shot per model. A schema failure or a timeout moves to the alternate
        # small model instead of retrying the same slow call as plain JSON.
        budget = timeout if timeout and timeout > 0 else self.timeout
        alt_budget = fallback_timeout if fallback_timeout and fallback_timeout > 0 else budget
        primary = (model or "").strip() or self.model
        alternate = (fallback_model or "").strip()
        plan = [(primary, True, budget)]
        if alternate and alternate != primary:
            plan.append((alternate, False, alt_budget))
        hint = schema_hint(schema)
        messages = [
            {"role": "system", "content": f"{system}\n\n{hint}"},
            {"role": "user", "content": user},
        ]
        last_error = "không rõ"
        for name, use_schema, call_timeout in plan:
            try:
                text = self._complete_text(messages, temperature, schema, max_tokens, name, call_timeout, use_schema)
            except LLMError as exc:
                last_error = str(exc)
                _record_failover(role, name, last_error)
                continue
            try:
                return parse_structured(schema, text)
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                repaired = [
                    *messages,
                    {"role": "assistant", "content": (text or "")[:1500]},
                    {
                        "role": "user",
                        "content": f"JSON không hợp lệ ({exc}). Trả lại đúng một JSON object, không markdown.",
                    },
                ]
                try:
                    text = self._complete_text(repaired, temperature, schema, max_tokens, name, call_timeout, False)
                    return parse_structured(schema, text)
                except (LLMError, ValidationError, json.JSONDecodeError, ValueError) as again:
                    last_error = str(again)
                    _record_failover(role, name, last_error)
                    continue
        raise LLMError(f"Router không trả JSON hợp lệ: {last_error[:400]}")

    def _complete_text(
        self,
        messages: list[dict],
        temperature: float,
        schema: type[BaseModel],
        max_tokens: int | None,
        model_name: str,
        timeout: float,
        use_schema: bool,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: dict = {
            "model": model_name,
            "temperature": temperature,
            "stream": False,
            "messages": messages,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if use_schema:
            payload["response_format"] = json_schema_format(schema)
        status, content_type, body = post_chat(url, self.api_key, payload, timeout)
        if status == 400 and use_schema:
            raise LLMError(f"router schema {status}: {body[:180]}")
        if status_is_retryable(status):
            raise LLMError(f"router {status}: {body[:180]}")
        if status >= 400:
            raise LLMError(f"router {status}: {body[:300]}")
        return assemble_message(body, content_type)

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
        errors: list[str] = []
        for provider in self.chain:
            try:
                result = provider.complete(
                    schema,
                    system,
                    user,
                    temperature,
                    thinking=thinking,
                    model=model,
                    role=role,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    fallback_model=fallback_model,
                    fallback_timeout=fallback_timeout,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.name}: {exc}")
                continue
            self.name = provider.name
            self.model = provider.model
            return result
        raise LLMError(" ; ".join(errors))

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError("Embedding không đi theo chuỗi chat.")
