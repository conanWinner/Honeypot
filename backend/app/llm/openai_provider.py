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
import time
from concurrent.futures import ThreadPoolExecutor, wait
from concurrent.futures import TimeoutError as FuturesTimeout

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
        "User-Agent": "honeypot/1.0",
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


def _first_success(futures, horizon: float | None, role: str, names: tuple[str, str]):
    pending = set(futures)
    errors: list[str] = []
    while pending:
        timeout = None
        if horizon is not None:
            timeout = horizon - time.monotonic()
            if timeout <= 0:
                break
        done, pending = wait(pending, timeout=timeout, return_when="FIRST_COMPLETED")
        if not done:
            break
        for future in done:
            try:
                return future.result()
            except (LLMError, ValidationError, json.JSONDecodeError, ValueError) as exc:
                errors.append(str(exc))
                _record_failover(role, names[0] if future is futures[0] else names[1], str(exc))
    raise LLMError(f"Router không trả JSON hợp lệ: {(errors[-1] if errors else 'role deadline')[:400]}")


def http_timeout(seconds: float) -> httpx.Timeout:
    """One budget for the whole request. httpx otherwise applies the same number to every phase."""
    seconds = max(0.4, float(seconds))
    connect = min(2.0, seconds)
    return httpx.Timeout(connect=connect, read=max(0.2, seconds - connect), write=min(3.0, seconds), pool=min(1.0, seconds))


def post_chat(url: str, api_key: str, payload: dict, timeout: float = 40) -> tuple[int, str, str]:
    headers = request_headers(api_key)
    body = dict(payload)
    # Gemini on 9router otherwise answers as SSE and the JSON body comes back empty.
    body["stream"] = False
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=http_timeout(timeout))
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
        deadline: float | None = None,
    ) -> BaseModel:
        del thinking
        # Primary and fallback each have their own budget. A repair stays inside
        # the model that produced the bad JSON. The turn horizon, if any, still caps both.
        primary_budget = timeout if timeout and timeout > 0 else self.timeout
        primary = (model or "").strip() or self.model
        alternate = (fallback_model or "").strip()
        if alternate == primary:
            alternate = ""
        alt_budget = fallback_timeout if fallback_timeout and fallback_timeout > 0 else primary_budget
        horizon = deadline
        hint = schema_hint(schema)
        messages = [
            {"role": "system", "content": f"{system}\n\n{hint}"},
            {"role": "user", "content": user},
        ]

        def run_model(name: str, use_schema: bool, budget: float) -> BaseModel:
            model_end = time.monotonic() + max(0.0, budget)
            if horizon is not None:
                model_end = min(model_end, horizon)
            left = model_end - time.monotonic()
            if left < 0.8:
                raise LLMError("role deadline")
            try:
                text = self._complete_text(messages, temperature, schema, max_tokens, name, left, use_schema)
            except LLMError:
                raise
            try:
                return parse_structured(schema, text)
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                left = model_end - time.monotonic()
                if left < 0.8:
                    raise LLMError(f"role deadline: {exc}") from exc
                repaired = [
                    *messages,
                    {"role": "assistant", "content": (text or "")[:1500]},
                    {
                        "role": "user",
                        "content": f"JSON không hợp lệ ({exc}). Trả lại đúng một JSON object, không markdown.",
                    },
                ]
                text = self._complete_text(repaired, temperature, schema, max_tokens, name, left, False)
                return parse_structured(schema, text)

        if not alternate:
            try:
                return run_model(primary, True, primary_budget)
            except (LLMError, ValidationError, json.JSONDecodeError, ValueError) as exc:
                _record_failover(role, primary, str(exc))
                raise LLMError(f"Router không trả JSON hợp lệ: {exc}"[:400]) from exc

        # If the primary is still silent after a few seconds, start the fallback
        # beside it and keep whichever answer parses first.
        room = (horizon - time.monotonic()) if horizon is not None else primary_budget
        hedge = min(5.0, max(0.4, min(primary_budget, room) * 0.55))
        pool = ThreadPoolExecutor(max_workers=2)
        try:
            primary_future = pool.submit(run_model, primary, True, primary_budget)
            try:
                return primary_future.result(timeout=hedge)
            except FuturesTimeout:
                alt_future = pool.submit(run_model, alternate, False, alt_budget)
                return _first_success((primary_future, alt_future), horizon, role, (primary, alternate))
            except (LLMError, ValidationError, json.JSONDecodeError, ValueError) as exc:
                _record_failover(role, primary, str(exc))
                try:
                    return run_model(alternate, False, alt_budget)
                except (LLMError, ValidationError, json.JSONDecodeError, ValueError) as again:
                    _record_failover(role, alternate, str(again))
                    raise LLMError(f"Router không trả JSON hợp lệ: {again}"[:400]) from again
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

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
        if use_schema and schema is not None:
            payload["response_format"] = json_schema_format(schema)
        status, content_type, body = post_chat(url, self.api_key, payload, timeout)
        if status == 400 and use_schema:
            raise LLMError(f"router schema {status}: {body[:180]}")
        if status_is_retryable(status):
            raise LLMError(f"router {status}: {body[:180]}")
        if status >= 400:
            raise LLMError(f"router {status}: {body[:300]}")
        return assemble_message(body, content_type)

    def complete_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.4,
        model: str | None = None,
        role: str = "",
        max_tokens: int | None = 120,
        timeout: float | None = None,
        fallback_model: str | None = None,
        fallback_timeout: float | None = None,
        prefer_fallback: bool = False,
    ) -> str:
        """One plain-text completion. No JSON schema, so a short line is not parsed twice."""
        primary = (fallback_model if prefer_fallback and fallback_model else model) or self.model
        primary = primary.strip() or self.model
        budget = timeout if timeout and timeout > 0 else 6.0
        if prefer_fallback and fallback_timeout and fallback_timeout > 0:
            budget = fallback_timeout
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            return self._complete_text(messages, temperature, None, max_tokens, primary, budget, False).strip()
        except LLMError as exc:
            alternate = "" if prefer_fallback else (fallback_model or "").strip()
            if not alternate or alternate == primary:
                raise
            _record_failover(role, primary, str(exc))
            alt_budget = fallback_timeout if fallback_timeout and fallback_timeout > 0 else budget
            return self._complete_text(messages, temperature, None, max_tokens, alternate, alt_budget, False).strip()

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError("Chat provider không làm embedding. Dùng OpenAIEmbedder.")


def _fit_dim(vector: list[float], dim: int) -> list[float]:
    """Matryoshka models (text-embedding-3, qwen3, nemotron) keep meaning in the prefix."""
    if len(vector) < dim:
        raise LLMError(f"embedding có {len(vector)} chiều, cần {dim}")
    head = [float(value) for value in vector[:dim]]
    norm = sum(value * value for value in head) ** 0.5 or 1.0
    return [value / norm for value in head]


class OpenAIEmbedder:
    """POST /embeddings on the OpenAI-compatible router, batched, with a 429/5xx cooldown."""

    is_mock = False
    name = "openai-compatible-embed"
    batch = 16
    pause_seconds = 120

    def __init__(self, api_key: str, base_url: str, model: str, dim: int = 768, timeout: float = 6, fallback_model: str = ""):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = model
        self.dim = int(dim)
        self.timeout = float(timeout)
        self.fallback_model = (fallback_model or "").strip()
        self.embed_paused_until = 0.0
        self.embed_pause_logged = False

    def _post(self, model: str, texts: list[str]) -> list[list[float]]:
        payload = {"model": model, "input": texts, "dimensions": self.dim, "encoding_format": "float"}
        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                headers=request_headers(self.api_key),
                json=payload,
                # One query text sits on the turn's critical path; a backfill batch may take longer.
                timeout=http_timeout(self.timeout if len(texts) == 1 else max(self.timeout, 60.0)),
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"embedding timeout: {exc}") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise LLMError(f"embedding {response.status_code}: {response.text[:160]}")
        if response.status_code >= 400:
            raise LLMError(f"embedding {response.status_code}: {response.text[:300]}")
        try:
            data = sorted(response.json()["data"], key=lambda item: item.get("index", 0))
            vectors = [_fit_dim(item["embedding"], self.dim) for item in data]
        except (KeyError, TypeError, ValueError) as exc:
            raise LLMError(f"embedding trả sai định dạng: {exc}") from exc
        if len(vectors) != len(texts):
            raise LLMError(f"embedding trả {len(vectors)} vector cho {len(texts)} đoạn")
        return vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        if time.monotonic() < self.embed_paused_until:
            raise LLMError("semantic search paused")
        out: list[list[float]] = []
        for start in range(0, len(texts), self.batch):
            chunk = texts[start : start + self.batch]
            try:
                out.extend(self._post(self.model, chunk))
                continue
            except LLMError as exc:
                last = exc
            if self.fallback_model:
                try:
                    out.extend(self._post(self.fallback_model, chunk))
                    continue
                except LLMError as exc:
                    last = exc
            self.embed_paused_until = time.monotonic() + self.pause_seconds
            if not self.embed_pause_logged:
                log.warning("Embedding router lỗi (%s), tìm theo từ khóa trong %s giây.", str(last)[:80], self.pause_seconds)
                self.embed_pause_logged = True
            raise LLMError("semantic search paused") from None
        self.embed_pause_logged = False
        return out


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
        deadline: float | None = None,
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
                    deadline=deadline,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.name}: {exc}")
                continue
            self.name = provider.name
            self.model = provider.model
            return result
        raise LLMError(" ; ".join(errors))

    def complete_text(self, system: str, user: str, temperature: float = 0.4, **kwargs) -> str:
        errors: list[str] = []
        for provider in self.chain:
            try:
                text = provider.complete_text(system, user, temperature, **kwargs)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.name}: {exc}")
                continue
            self.name = provider.name
            self.model = provider.model
            return text
        raise LLMError(" ; ".join(errors))

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError("Embedding không đi theo chuỗi chat.")


class LastResortProvider:
    """One more router model on a different upstream, tried after a role's primary
    and fallback both failed. Replaces the direct Gemini key, whose free quota runs
    out: the router's gemini/ route bills the router key, not Google's free tier."""

    is_mock = False

    def __init__(self, router: OpenAIProvider, model: str, timeout: float = 8.0):
        self.router = router
        self.model = model
        self.timeout = timeout
        self.name = "router-last-resort"
        self.embed_model = ""

    def complete(self, schema, system, user, temperature=0.4, thinking=False, model=None, role="",
                 max_tokens=None, timeout=None, fallback_model=None, fallback_timeout=None, deadline=None):
        del model, fallback_model, fallback_timeout, timeout
        return self.router.complete(
            schema, system, user, temperature, thinking=thinking, model=self.model, role=role,
            max_tokens=max_tokens, timeout=self.timeout, fallback_model=None, deadline=deadline,
        )

    def complete_text(self, system, user, temperature=0.4, model=None, role="", max_tokens=120,
                      timeout=None, fallback_model=None, fallback_timeout=None, prefer_fallback=False):
        del model, fallback_model, fallback_timeout, prefer_fallback, timeout
        return self.router.complete_text(
            system, user, temperature, model=self.model, role=role, max_tokens=max_tokens, timeout=self.timeout,
        )
