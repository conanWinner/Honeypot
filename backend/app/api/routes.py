"""HTTP API. The UI speaks Vietnamese; these payloads are what it renders."""

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.agent.orchestrator import handle_turn
from app.agent.state import AgentState
from app.channels import get_adapter
from app.llm.base import LLMError
from app.models import Conversation, Message, Persona, Script
from app.services.checker import check_text
from app.services.demo import DEMO
from app.services.library import embed_script, finish_conversation, get_script, list_scripts, script_public, set_status, variant_counts
from app.services.trends import build_trends
from app.taxonomy import CATEGORIES, CHANNELS, GOALS

router = APIRouter()


def get_db(request: Request):
    session = request.app.state.Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def require_admin(request: Request, x_admin_token: str = Header(default="")):
    expected = request.app.state.settings.admin_token
    if not expected:
        return
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai mã quản trị.")


class ConversationIn(BaseModel):
    persona_id: str
    channel: str = "web"
    aggressiveness: str = ""


class MessageIn(BaseModel):
    text: str = ""
    external_id: str = ""
    message_id: str = ""
    chat_id: str = ""


class CheckIn(BaseModel):
    text: str


class HandoffIn(BaseModel):
    text: str
    persona_id: str
    channel: str = "web"


def _otp(conversation_id: str) -> str:
    digest = hashlib.sha256(f"gianan-fake:{conversation_id}".encode()).hexdigest()
    return f"{int(digest[:8], 16) % 1_000_000:06d}"


def _persona_public(persona: Persona) -> dict:
    return {
        "id": persona.id,
        "label": persona.label,
        "display_name": persona.display_name,
        "age": persona.age,
        "job": persona.job,
        "city": persona.city,
        "region": persona.region,
        "texting_style": persona.texting_style,
        "bio": persona.bio,
        "hooks": persona.hooks,
        "fake_profile": persona.fake_profile,
        "examples": persona.examples,
    }


def _message_public(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "reasoning": message.reasoning,
        "created_at": message.created_at.isoformat(),
    }


def _conversation_public(conversation: Conversation) -> dict:
    state = AgentState.model_validate(conversation.state)
    return {
        "id": conversation.id,
        "channel": conversation.channel,
        "channel_label": CHANNELS.get(conversation.channel, conversation.channel),
        "status": conversation.status,
        "is_demo": conversation.is_demo,
        "provider": conversation.provider,
        "persona": _persona_public(conversation.persona),
        "messages": [_message_public(message) for message in conversation.messages],
        "demo_lines": state.demo_lines,
        "turn_index": state.turn_index,
        "wrap_recommended": state.wrap_recommended,
        "wrap_reason": state.wrap_reason,
        "fake_otp": state.fake_otp,
        "extracted_script_id": conversation.extracted_script_id,
        "created_at": conversation.created_at.isoformat(),
    }


def _load_conversation(session, conversation_id: str) -> Conversation:
    conversation = session.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.persona), selectinload(Conversation.messages))
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không thấy cuộc hội thoại.")
    conversation.messages.sort(key=lambda message: message.created_at)
    return conversation


@router.get("/health")
def health(request: Request, session=Depends(get_db)):
    provider = request.app.state.provider
    published = session.scalar(select(func.count()).select_from(Script).where(Script.status == "published")) or 0
    embedded = session.scalar(
        select(func.count()).select_from(Script).where(Script.status == "published", Script.embedding.is_not(None))
    ) or 0
    return {
        "ok": True,
        "llm": {"provider": provider.name, "model": provider.model, "mock": provider.is_mock},
        "embeddings": {
            "model": provider.embed_model,
            "mock": getattr(provider, "embeddings_mock", provider.is_mock),
            "ready": embedded,
            "published": published,
        },
        "database": request.app.state.engine.dialect.name,
        "admin_open": not bool(request.app.state.settings.admin_token),
    }


@router.get("/health/llm")
def health_llm(request: Request):
    report = getattr(request.app.state, "llm_health", None) or {
        "ok": False,
        "mock": True,
        "latency_ms": None,
        "model": "",
        "error": "Chưa có ping.",
        "warming": False,
    }
    return report


@router.get("/meta")
def meta():
    return {
        "categories": [{"id": key, "label": label} for key, label in CATEGORIES.items()],
        "channels": [{"id": key, "label": label} for key, label in CHANNELS.items() if key != "multi"],
        "agent_channels": [
            {"id": "web", "label": "Web", "live": True, "note": "Kênh đang chạy."},
            {"id": "telegram", "label": "Telegram", "live": False, "note": "Cùng agent. Telethon gắn ở pha 2."},
            {"id": "voice", "label": "Thoại", "live": False, "note": "Cùng agent. Nhận bản ghi. Gọi điện là pha 2."},
        ],
        "goals": [{"id": key, "label": label} for key, label in GOALS.items()],
    }


@router.get("/personas")
def personas(session=Depends(get_db)):
    rows = session.scalars(select(Persona).order_by(Persona.age.desc())).all()
    return [_persona_public(row) for row in rows]


@router.get("/stats")
def stats(session=Depends(get_db)):
    published = session.scalar(select(func.count()).select_from(Script).where(Script.status == "published")) or 0
    pending = session.scalar(select(func.count()).select_from(Script).where(Script.status == "pending")) or 0
    conversations = session.scalar(select(func.count()).select_from(Conversation)) or 0
    return {"published_scripts": published, "pending_scripts": pending, "conversations": conversations}


@router.post("/conversations")
def create_conversation(body: ConversationIn, request: Request, session=Depends(get_db)):
    persona = session.get(Persona, body.persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Không thấy hồ sơ đóng vai.")
    try:
        get_adapter(body.channel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    conversation_id = uuid.uuid4().hex[:16]
    provider = request.app.state.provider
    pace = body.aggressiveness if body.aggressiveness in {"cautious", "normal", "persistent"} else request.app.state.settings.agent_aggressiveness
    if pace not in {"cautious", "normal", "persistent"}:
        pace = "normal"
    state = AgentState(
        persona_slug=persona.id,
        channel=body.channel,
        fake_otp=_otp(conversation_id),
        provider=provider.name,
        aggressiveness=pace,
    )
    conversation = Conversation(
        id=conversation_id,
        channel=body.channel,
        persona_id=persona.id,
        status="active",
        state=state.model_dump(),
        is_demo=False,
        provider=provider.name,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(conversation)
    session.flush()
    return _conversation_public(_load_conversation(session, conversation.id))


@router.get("/conversations")
def list_conversations(session=Depends(get_db)):
    rows = session.scalars(
        select(Conversation).options(selectinload(Conversation.persona)).order_by(Conversation.updated_at.desc()).limit(12)
    ).all()
    items = []
    for row in rows:
        state = AgentState.model_validate(row.state)
        items.append(
            {
                "id": row.id,
                "status": row.status,
                "channel": row.channel,
                "channel_label": CHANNELS.get(row.channel, row.channel),
                "is_demo": row.is_demo,
                "persona_label": row.persona.label,
                "persona_name": row.persona.display_name,
                "updated_at": row.updated_at.isoformat(),
                "turn_index": state.turn_index,
            }
        )
    return items


@router.get("/conversations/{conversation_id}")
def read_conversation(conversation_id: str, session=Depends(get_db)):
    return _conversation_public(_load_conversation(session, conversation_id))


@router.post("/conversations/{conversation_id}/messages")
def post_message(conversation_id: str, body: MessageIn, request: Request, session=Depends(get_db)):
    conversation = _load_conversation(session, conversation_id)
    if conversation.status != "active":
        raise HTTPException(status_code=409, detail="Cuộc hội thoại đã kết thúc.")
    adapter = get_adapter(conversation.channel)
    try:
        inbound = adapter.parse(
            {
                "text": body.text,
                "message": body.text,
                "transcript": body.text,
                "external_id": body.external_id,
                "message_id": body.message_id,
                "chat_id": body.chat_id,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        result = handle_turn(session, conversation, inbound.text, request.app.state.provider)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"Mô hình không phản hồi. {exc}") from exc
    result["rendered"] = adapter.render(result["victim_message"]["content"])
    result["conversation_id"] = conversation.id
    return result


@router.post("/conversations/{conversation_id}/extract")
def extract(conversation_id: str, request: Request, session=Depends(get_db)):
    conversation = _load_conversation(session, conversation_id)
    try:
        outcome = finish_conversation(session, conversation, request.app.state.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"Mô hình không trích được kịch bản. {exc}") from exc
    return outcome


@router.get("/scripts")
def scripts(
    q: str = "",
    category: str = "",
    channel: str = "",
    status: str = "published",
    roots_only: bool = False,
    session=Depends(get_db),
):
    if q.strip():
        roots_only = False
    return {
        "items": list_scripts(session, q=q, category=category, channel=channel, status=status, roots_only=roots_only)
    }


@router.get("/scripts/{script_id}")
def script_detail(script_id: str, session=Depends(get_db)):
    data = get_script(session, script_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Không thấy kịch bản.")
    return data


@router.post("/check")
def check(body: CheckIn, request: Request, session=Depends(get_db)):
    text = body.text.strip()
    if len(text) < 8:
        raise HTTPException(status_code=400, detail="Dán một tin nhắn hoặc đoạn hội thoại dài hơn.")
    try:
        return check_text(session, text, request.app.state.provider)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"Mô hình không phản hồi. {exc}") from exc


@router.post("/check/handoff")
def handoff(body: HandoffIn, request: Request, session=Depends(get_db)):
    created = create_conversation(ConversationIn(persona_id=body.persona_id, channel=body.channel), request, session)
    result = post_message(created["id"], MessageIn(text=body.text), request, session)
    result["conversation"] = _conversation_public(_load_conversation(session, created["id"]))
    return result


@router.get("/trends")
def trends(session=Depends(get_db)):
    return build_trends(session)


@router.get("/moderation")
def moderation(session=Depends(get_db), _: None = Depends(require_admin)):
    rows = session.scalars(select(Script).where(Script.status == "pending").order_by(Script.created_at.desc())).all()
    counts = variant_counts(session)
    return [script_public(row, counts.get(row.id, 0)) for row in rows]


@router.post("/moderation/{script_id}/approve")
def approve(script_id: str, request: Request, session=Depends(get_db), _: None = Depends(require_admin)):
    data = set_status(session, script_id, "published")
    if data is None:
        raise HTTPException(status_code=404, detail="Không thấy bản chờ duyệt.")
    embed_script(session, script_id, request.app.state.provider)
    return get_script(session, script_id) or data


@router.post("/moderation/{script_id}/reject")
def reject(script_id: str, session=Depends(get_db), _: None = Depends(require_admin)):
    data = set_status(session, script_id, "rejected")
    if data is None:
        raise HTTPException(status_code=404, detail="Không thấy bản chờ duyệt.")
    return data


@router.post("/demo/start")
def start_demo(request: Request, session=Depends(get_db)):
    created = create_conversation(ConversationIn(persona_id=DEMO["persona_id"], channel=DEMO["channel"]), request, session)
    conversation = _load_conversation(session, created["id"])
    state = AgentState.model_validate(conversation.state)
    state.demo_lines = list(DEMO["lines"])
    conversation.state = state.model_dump()
    conversation.is_demo = True
    session.flush()
    payload = _conversation_public(_load_conversation(session, conversation.id))
    payload["demo"] = {"id": DEMO["id"], "title": DEMO["title"], "blurb": DEMO["blurb"], "expected_script": DEMO["expected_script"]}
    return payload


@router.get("/demo")
def demo_meta():
    return {"id": DEMO["id"], "title": DEMO["title"], "blurb": DEMO["blurb"], "lines": DEMO["lines"], "persona_id": DEMO["persona_id"]}
