"""Retrieve library scripts with embeddings when they exist, and keywords always.

pgvector runs the nearest-neighbour query on Postgres. SQLite tests use the
same blend in Python so the ranking rules stay one piece of code.
"""

import logging

from sqlalchemy import select, text

from app.agent.textutil import contains_phrase, cosine, fold, tokenize
from app.models import Script

log = logging.getLogger("gianan.match")


def script_blob(script: Script) -> str:
    parts = [script.title or "", script.summary or "", script.brand or "", script.category or ""]
    parts.extend(script.hooks or [])
    parts.extend(script.red_flags or [])
    for step in script.steps or []:
        parts.append(step.get("intent") or "")
        parts.extend(step.get("phrases") or [])
    return "\n".join(parts)


def keyword_score(message: str, document: str) -> float:
    msg = tokenize(message)
    doc = tokenize(document)
    if not msg or not doc:
        return 0.0
    return len(msg & doc) / len(msg)


def best_step(message: str, steps: list[dict]) -> tuple[int, float]:
    msg_tokens = tokenize(message)
    folded_msg = fold(message or "")
    best_i, best_s = 0, 0.0
    for index, step in enumerate(steps or []):
        if step.get("actor") != "scammer":
            continue
        blob = (step.get("intent") or "") + " " + " ".join(step.get("phrases") or [])
        step_tokens = tokenize(blob)
        score = 0.0
        if msg_tokens and step_tokens:
            score = len(msg_tokens & step_tokens) / len(msg_tokens)
        for phrase in step.get("phrases") or []:
            words = [word for word in tokenize(phrase) if len(word) > 3]
            if words and sum(word in msg_tokens for word in words) / len(words) >= 0.55:
                score += 0.35
            folded_phrase = fold(phrase)
            if len(folded_phrase) > 12 and folded_phrase in folded_msg:
                score += 0.25
        if score > best_s:
            best_i, best_s = index, min(score, 1.0)
    return best_i, best_s


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.6f}" for value in values) + "]"


def _pg_scores(session, embedding: list[float], limit: int) -> dict[str, float]:
    rows = session.execute(
        text(
            """
            SELECT id, 1 - (embedding_vec <=> CAST(:q AS vector)) AS score
            FROM scripts
            WHERE status = 'published' AND embedding_vec IS NOT NULL
            ORDER BY embedding_vec <=> CAST(:q AS vector)
            LIMIT :k
            """
        ),
        {"q": vector_literal(embedding), "k": limit},
    ).all()
    return {row.id: max(0.0, float(row.score)) for row in rows}


def _stick(ranked: list[dict], prefer_ids: set[str]) -> list[dict]:
    """Stay with the script already in play unless another one is clearly better."""
    if not prefer_ids:
        return ranked

    def preferred(item: dict) -> bool:
        script = item["script"]
        return script.id in prefer_ids or (script.parent_id or "") in prefer_ids

    chosen = [item for item in ranked if preferred(item)]
    if not chosen:
        return ranked
    chosen.sort(key=lambda item: item["score"], reverse=True)
    best_other = max((item["score"] for item in ranked if not preferred(item)), default=0.0)
    if best_other > chosen[0]["score"] + 0.22:
        return ranked
    rest = [item for item in ranked if item["script"].id != chosen[0]["script"].id]
    return [chosen[0], *rest]


def search_scripts(session, message: str, provider, k: int = 6, status: str = "published", prefer_ids: set[str] | None = None) -> list[dict]:
    scripts = list(session.scalars(select(Script).where(Script.status == status)).all())
    if not scripts or not (message or "").strip():
        return []
    embedding = None
    vector_scores: dict[str, float] | None = None
    if provider and not provider.is_mock:
        try:
            embedding = provider.embed([message])[0]
        except Exception:
            log.warning("Không tạo được embedding cho lượt này, tạm xếp theo từ khóa.", exc_info=True)
            embedding = None
    if embedding is not None:
        found: dict[str, float] = {}
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            try:
                found = _pg_scores(session, embedding, max(k * 4, 20))
            except Exception:
                log.warning("Truy vấn pgvector lỗi, dùng cosine trong Python.", exc_info=True)
                found = {}
        if not found:
            for script in scripts:
                if script.embedding:
                    found[script.id] = max(0.0, cosine(embedding, script.embedding))
        # An empty map is not a vector result. Treating it as zeros halves every keyword score.
        if found:
            vector_scores = found
    ranked = []
    folded_message = fold(message)
    for script in scripts:
        kw = keyword_score(message, script_blob(script))
        step_index, step_score = best_step(message, script.steps or [])
        brand_boost = 0.08 if script.brand and fold(script.brand) in folded_message else 0.0
        # Missing embedding stays None so that script keeps its keyword score.
        vec = None if vector_scores is None else vector_scores.get(script.id)
        if vec is None:
            score = 0.62 * kw + 0.38 * step_score + brand_boost
        else:
            score = 0.48 * vec + 0.30 * kw + 0.22 * step_score + brand_boost
        ranked.append(
            {
                "script": script,
                "score": round(min(score, 0.97), 4),
                "step_index": step_index,
                "step_score": round(step_score, 4),
                "vector": None if vec is None else round(vec, 4),
            }
        )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return _stick(ranked, prefer_ids or set())[:k]


def branch_hint(message: str, persona, ranked: list[dict], scripts: list[Script]) -> dict:
    empty = {"detected": False, "kind": "none", "hook": "", "description": "", "variant_script_id": ""}
    if not ranked:
        return empty
    by_id = {script.id: script for script in scripts}
    top = ranked[0]["script"]
    root_id = top.parent_id or top.id
    family_ids = {root_id, top.id}
    for script in scripts:
        if script.parent_id == root_id or script.id == root_id:
            family_ids.add(script.id)
    hits = []
    for token in persona.hook_tokens or []:
        if contains_phrase(message, token):
            hits.append(token)
    if not hits:
        return empty
    hook = hits[0]

    def carries(script: Script, token: str) -> bool:
        return contains_phrase(script_blob(script), token)

    carriers = [by_id[sid] for sid in family_ids if sid in by_id and carries(by_id[sid], hook)]
    variant = next((script for script in carriers if script.parent_id), None)
    if variant is not None:
        return {
            "detected": True,
            "kind": "known_variant",
            "hook": hook,
            "description": f"Khớp nhánh đã có trong thư viện: {variant.title}",
            "variant_script_id": variant.id,
        }
    if carriers:
        return empty
    return {
        "detected": True,
        "kind": "new",
        "hook": hook,
        "description": f"Đối phương khai thác hoàn cảnh riêng («{hook}») chưa có trong kịch bản đang khớp.",
        "variant_script_id": "",
    }


def candidate_payload(ranked: list[dict]) -> list[dict]:
    payload = []
    for item in ranked:
        script = item["script"]
        steps = []
        for index, step in enumerate(script.steps or []):
            phrases = step.get("phrases") or []
            steps.append(
                {
                    "index": index,
                    "actor": step.get("actor"),
                    "intent": step.get("intent"),
                    "phrase": phrases[0] if phrases else "",
                }
            )
        payload.append(
            {
                "script_id": script.id,
                "title": script.title,
                "category": script.category,
                "brand": script.brand,
                "parent_id": script.parent_id or "",
                "retrieval_score": item["score"],
                "heuristic_step_index": item["step_index"],
                "heuristic_step_score": item["step_score"],
                "hooks": script.hooks or [],
                "steps": steps,
            }
        )
    return payload
