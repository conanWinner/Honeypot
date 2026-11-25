"""Per-conversation memory. Persisted as JSON on the conversation row."""

from pydantic import BaseModel, Field


class MatchSnap(BaseModel):
    script_id: str
    family_id: str = ""
    title: str = ""
    confidence: float = 0
    step_index: int = 0
    step_intent: str = ""
    branch_kind: str = "none"


class AgentState(BaseModel):
    persona_slug: str
    channel: str = "web"
    turn_index: int = 0
    memory: list[str] = Field(default_factory=list)
    goals_used: list[str] = Field(default_factory=list)
    extracted_facts: list[str] = Field(default_factory=list)
    match_history: list[MatchSnap] = Field(default_factory=list)
    branch_events: list[dict] = Field(default_factory=list)
    fake_otp: str
    otp_reads: int = 0
    otp_prompts: int = 0
    wrap_recommended: bool = False
    wrap_reason: str = ""
    suspicion: float = 0
    provider: str = ""
    demo_lines: list[str] = Field(default_factory=list)
    known_numbers: list[str] = Field(default_factory=list)
