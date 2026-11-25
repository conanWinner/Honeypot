"""Library reads, seeding, and the merge that follows a finished conversation."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.agent.prompts import EXTRACT_SYSTEM
from app.agent.schemas import ExtractionOutput
from app.agent.state import AgentState
from app.data.personas import PERSONAS
from app.data.scripts import SCRIPTS
from app.models import Persona, Script, utcnow
from app.services.matching import script_blob, vector_literal
from app.taxonomy import CATEGORIES, CHANNELS

log = logging.getLogger("gianan.library")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def seed(session) -> None:
    have_personas = set(session.scalars(select(Persona.id)).all())
    for row in PERSONAS:
        if row["id"] in have_personas:
            continue
        session.add(Persona(**row))
    have_scripts = set(session.scalars(select(Script.id)).all())
    pending = [row for row in SCRIPTS if row["id"] not in have_scripts]
    # Parents first.
    pending.sort(key=lambda row: 0 if not row.get("parent_id") else 1)
    for row in pending:
        session.add(
            Script(
                id=row["id"],
                parent_id=row.get("parent_id"),
                title=row["title"],
                category=row["category"],
                channel=row["channel"],
                brand=row.get("brand") or "",
                summary=row["summary"],
                steps=row["steps"],
                hooks=row["hooks"],
                red_flags=row["red_flags"],
                advice=row["advice"],
                sources=row["sources"],
                first_seen=_dt(row["first_seen"]),
                last_seen=_dt(row["last_seen"]),
                occurrence_count=row["occurrence_count"],
                status="published",
                novelty_note="",
            )
        )
    session.flush()


def script_public(script: Script, variant_count: int = 0, parent: Script | None = None, with_steps: bool = True) -> dict:
    data = {
        "id": script.id,
        "parent_id": script.parent_id,
        "title": script.title,
        "category": script.category,
        "category_label": CATEGORIES.get(script.category, script.category),
        "channel": script.channel,
        "channel_label": CHANNELS.get(script.channel, script.channel),
        "brand": script.brand,
        "summary": script.summary,
        "hooks": script.hooks or [],
        "red_flags": script.red_flags or [],
        "advice": script.advice,
        "sources": script.sources or [],
        "first_seen": script.first_seen.isoformat(),
        "last_seen": script.last_seen.isoformat(),
        "occurrence_count": script.occurrence_count,
        "status": script.status,
        "novelty_note": script.novelty_note or "",
        "has_embedding": bool(script.embedding),
        "variant_count": variant_count,
    }
    if with_steps:
        data["steps"] = script.steps or []
    if parent is not None:
        data["parent"] = {"id": parent.id, "title": parent.title}
    return data


def variant_counts(session) -> dict[str, int]:
    rows = session.execute(
        select(Script.parent_id, func.count()).where(Script.parent_id.is_not(None), Script.status == "published").group_by(Script.parent_id)
    ).all()
    return {parent_id: count for parent_id, count in rows}


def list_scripts(session, q: str = "", category: str = "", channel: str = "", status: str = "published", roots_only: bool = False) -> list[dict]:
    stmt = select(Script)
    if status:
        stmt = stmt.where(Script.status == status)
    if category:
        stmt = stmt.where(Script.category == category)
    if channel:
        stmt = stmt.where(Script.channel == channel)
    if roots_only:
        stmt = stmt.where(Script.parent_id.is_(None))
    rows = list(session.scalars(stmt).all())
    counts = variant_counts(session)
    if q.strip():
        from app.services.matching import keyword_score

        scored = [(keyword_score(q, script_blob(row)) + (0.05 if q.lower() in (row.title or "").lower() else 0), row) for row in rows]
        scored = [item for item in scored if item[0] > 0.08]
        scored.sort(key=lambda item: item[0], reverse=True)
        rows = [row for _, row in scored]
    else:
        rows.sort(key=lambda row: row.last_seen, reverse=True)
    return [script_public(row, counts.get(row.id, 0), with_steps=False) for row in rows]


def get_script(session, script_id: str) -> dict | None:
    script = session.get(Script, script_id)
    if script is None:
        return None
    parent = session.get(Script, script.parent_id) if script.parent_id else None
    counts = variant_counts(session)
    data = script_public(script, counts.get(script.id, 0), parent=parent, with_steps=True)
    children = session.scalars(select(Script).where(Script.parent_id == script.id).order_by(Script.title)).all()
    data["variants"] = [script_public(child, with_steps=False) for child in children]
    return data


def _clean_category(value: str) -> str:
    value = (value or "").strip().lower()
    return value if value in CATEGORIES else "other"


def _clean_channel(value: str) -> str:
    value = (value or "").strip().lower()
    return value if value in CHANNELS else "web"


def backfill_embeddings(session, provider) -> int:
    if provider.is_mock:
        return 0
    rows = list(session.scalars(select(Script).where(Script.embedding.is_(None))).all())
    if not rows:
        return 0
    updated = 0
    for start in range(0, len(rows), 16):
        chunk = rows[start : start + 16]
        vectors = provider.embed([script_blob(script) for script in chunk])
        for script, vector in zip(chunk, vectors):
            _write_embedding(session, script, vector)
            updated += 1
    return updated


def _write_embedding(session, script: Script, vector: list[float]) -> None:
    script.embedding = [float(value) for value in vector]
    session.flush()
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(
            __import__("sqlalchemy").text("UPDATE scripts SET embedding_vec = CAST(:q AS vector) WHERE id = :id"),
            {"q": vector_literal(vector), "id": script.id},
        )


def finish_conversation(session, conversation, provider) -> dict:
    from app.models import Message

    state = AgentState.model_validate(conversation.state)
    messages = list(
        session.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)).all()
    )
    scammer_messages = [message.content for message in messages if message.role == "scammer"]
    if not scammer_messages:
        raise ValueError("Cuộc hội thoại chưa có lời nào của đối phương.")
    published = list(session.scalars(select(Script).where(Script.status == "published")).all())
    by_id = {script.id: script for script in published}
    top = state.match_history[-1] if state.match_history else None
    new_hooks = [event for event in state.branch_events if event.get("kind") == "new"]
    known = [event for event in state.branch_events if event.get("kind") == "known_variant"]
    if new_hooks and top and top.script_id:
        relation = "variant"
        parent_id = new_hooks[-1].get("family_id") or top.family_id or top.script_id
        hook = new_hooks[-1].get("hook") or "nhánh mới"
        title = f"{(by_id.get(parent_id).title if parent_id in by_id else 'Kịch bản')} — nhánh: {hook}"
        novelty = new_hooks[-1].get("description") or ""
    elif top and top.confidence >= 0.62 and not new_hooks:
        relation = "duplicate"
        parent_id = known[-1].get("variant_script_id") if known and known[-1].get("variant_script_id") else top.script_id
        parent = by_id.get(parent_id)
        title = parent.title if parent else "Kịch bản đã biết"
        novelty = "Trùng kịch bản đã có trong thư viện."
    else:
        relation = "new_root"
        parent_id = ""
        title = "Kịch bản mới từ hội thoại"
        novelty = "Chưa khớp chắc một kịch bản đã công bố."
    parent = by_id.get(parent_id)
    context = {
        "scammer_messages": scammer_messages,
        "transcript": [{"role": message.role, "content": message.content} for message in messages],
        "facts": state.extracted_facts,
        "hooks": [event.get("hook") for event in state.branch_events if event.get("hook")],
        "suggested_relation": relation,
        "suggested_parent": parent_id,
        "suggested_title": title,
        "suggested_category": parent.category if parent else "other",
        "suggested_brand": parent.brand if parent else "",
        "channel": conversation.channel,
        "summary": parent.summary if parent else "Cuộc hội thoại vừa được trích.",
        "red_flags": (parent.red_flags if parent else [])[:4],
        "advice": parent.advice if parent else "Không chuyển tiền, không đọc OTP, không cài phần mềm theo yêu cầu của người lạ.",
        "novelty_reason": novelty,
        "candidates": [
            {"id": script.id, "title": script.title, "category": script.category}
            for script in published
            if top and script.id in {top.script_id, top.family_id}
        ],
    }
    from app.agent.orchestrator import pack

    extracted = provider.complete(ExtractionOutput, EXTRACT_SYSTEM, pack("Trích kịch bản từ hội thoại.", context), 0.3, thinking=True)
    # The server, not the model, decides duplicate versus a new branch.
    extracted.relation = relation
    extracted.parent_id = parent_id
    if not extracted.title:
        extracted.title = title
    extracted.category = _clean_category(extracted.category or (parent.category if parent else "other"))
    extracted.channel = _clean_channel(extracted.channel or conversation.channel)

    if relation == "duplicate" and parent is not None:
        _merge_into(parent, extracted, conversation.id)
        conversation.status = "ended"
        conversation.extracted_script_id = parent.id
        conversation.updated_at = utcnow()
        session.flush()
        return {"action": "merged", "script": get_script(session, parent.id), "relation": relation}

    script_id = "hs-" + uuid.uuid4().hex[:12]
    created = Script(
        id=script_id,
        parent_id=parent.id if relation == "variant" and parent is not None else None,
        title=extracted.title[:200],
        category=extracted.category,
        channel=extracted.channel,
        brand=(extracted.brand or (parent.brand if parent else ""))[:80],
        summary=extracted.summary,
        steps=[step.model_dump() for step in extracted.steps] or [
            {"actor": "scammer", "intent": "Lời đối phương", "phrases": scammer_messages[:4]}
        ],
        hooks=extracted.hooks or [event.get("hook") for event in new_hooks if event.get("hook")],
        red_flags=extracted.red_flags or ["Cần duyệt trước khi công bố."],
        advice=extracted.advice,
        sources=[{"type": "conversation", "ref": conversation.id}],
        first_seen=utcnow(),
        last_seen=utcnow(),
        occurrence_count=1,
        status="pending",
        novelty_note=extracted.novelty_reason or novelty,
    )
    session.add(created)
    if parent is not None and relation == "variant":
        parent.occurrence_count += 1
        parent.last_seen = utcnow()
    if not provider.is_mock:
        try:
            vector = provider.embed([script_blob(created)])[0]
            _write_embedding(session, created, vector)
        except Exception:
            log.warning("Chưa gắn embedding cho bản chờ duyệt.", exc_info=True)
    conversation.status = "ended"
    conversation.extracted_script_id = created.id
    conversation.updated_at = utcnow()
    session.flush()
    return {"action": "queued", "script": get_script(session, created.id), "relation": relation}


def _merge_into(script: Script, extracted: ExtractionOutput, conversation_id: str) -> None:
    script.occurrence_count += 1
    script.last_seen = utcnow()
    known = set()
    for step in script.steps or []:
        for phrase in step.get("phrases") or []:
            known.add(phrase.strip().lower())
    extra = []
    for step in extracted.steps:
        for phrase in step.phrases:
            cleaned = phrase.strip()
            if cleaned and cleaned.lower() not in known:
                extra.append(cleaned)
                known.add(cleaned.lower())
    steps = list(script.steps or [])
    if extra:
        steps.append({"actor": "scammer", "intent": "Câu bổ sung từ hội thoại", "phrases": extra[:6]})
        script.steps = steps
    sources = list(script.sources or [])
    sources.append({"type": "conversation", "ref": conversation_id})
    script.sources = sources
    script.updated_at = utcnow()


def set_status(session, script_id: str, status: str) -> dict | None:
    script = session.get(Script, script_id)
    if script is None:
        return None
    script.status = status
    script.updated_at = utcnow()
    if status == "published":
        script.last_seen = utcnow()
    session.flush()
    return get_script(session, script.id)


# Imported lazily above; keep the name available for type checkers and tests.
store_embedding_ready = _write_embedding
