"""Tables. Embeddings live in JSON everywhere and in a pgvector column on Postgres."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str] = mapped_column(String(80))
    age: Mapped[int] = mapped_column(Integer)
    job: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(16))
    texting_style: Mapped[str] = mapped_column(Text)
    bio: Mapped[str] = mapped_column(Text)
    hooks: Mapped[list] = mapped_column(JSON)
    hook_tokens: Mapped[list] = mapped_column(JSON)
    fake_profile: Mapped[dict] = mapped_column(JSON)
    examples: Mapped[list] = mapped_column(JSON)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="persona")


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("scripts.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32), index=True)
    channel: Mapped[str] = mapped_column(String(24), index=True)
    brand: Mapped[str] = mapped_column(String(80), default="")
    summary: Mapped[str] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSON)
    hooks: Mapped[list] = mapped_column(JSON)
    red_flags: Mapped[list] = mapped_column(JSON)
    advice: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default="published")
    novelty_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    parent: Mapped["Script | None"] = relationship(remote_side="Script.id")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    channel: Mapped[str] = mapped_column(String(24), index=True)
    persona_id: Mapped[str] = mapped_column(ForeignKey("personas.id"))
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    state: Mapped[dict] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str] = mapped_column(String(32), default="")
    extracted_script_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    persona: Mapped[Persona] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class TurnLog(Base):
    """One row per victim reply, so a judge or an operator can audit the pipeline."""

    __tablename__ = "turn_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(32), index=True)
    victim_message_id: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))
    mock: Mapped[bool] = mapped_column(Boolean, default=False)
    analyst: Mapped[dict] = mapped_column(JSON)
    planner: Mapped[dict] = mapped_column(JSON)
    safety: Mapped[dict] = mapped_column(JSON)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
