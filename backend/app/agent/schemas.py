"""Structured contracts between agent nodes. The model fills these; the server enforces them."""

from typing import Literal

from pydantic import BaseModel, Field


class MatchOut(BaseModel):
    script_id: str
    title: str = ""
    confidence: float = 0
    current_step_index: int = 0
    current_step_intent: str = ""
    reason: str = ""


class BranchOut(BaseModel):
    detected: bool = False
    kind: Literal["none", "known_variant", "new"] = "none"
    hook: str = ""
    description: str = ""
    variant_script_id: str = ""


class AnalystOutput(BaseModel):
    scammer_intent: str
    step_label: str
    red_flags: list[str] = Field(default_factory=list)
    extracted_fact: str = ""
    scammer_suspicion: float = 0
    matches: list[MatchOut] = Field(default_factory=list)
    branch: BranchOut = Field(default_factory=BranchOut)
    notes: str = ""


class PlannerOutput(BaseModel):
    goal: Literal[
        "ask_identity",
        "ask_purpose",
        "feign_confusion",
        "stall",
        "ask_link",
        "ask_transfer_destination",
        "ask_account_number",
        "read_fake_otp",
        "ask_next_instruction",
        "emotional_hook",
        "probe_hook",
        "close_polite",
    ]
    rationale: str
    tone: str = ""
    must_not: list[str] = Field(default_factory=list)
    facts_to_use: list[str] = Field(default_factory=list)


class PersonaOutput(BaseModel):
    reply: str
    memory_note: str = ""


class SafetyOutput(BaseModel):
    approved: bool = True
    violations: list[str] = Field(default_factory=list)
    action: Literal["allow", "rewrite", "fallback"] = "allow"
    safe_reply: str = ""
    notes: str = ""
    jailbreak: bool = False
    scammer_suspicious: bool = False
    suspicion_level: float = 0


class StepOut(BaseModel):
    actor: Literal["scammer", "victim"] = "scammer"
    intent: str
    phrases: list[str] = Field(default_factory=list)


class IndicatorsOut(BaseModel):
    phones: list[str] = Field(default_factory=list)
    bank_accounts: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    apps: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)
    pressure: list[str] = Field(default_factory=list)


class ExtractionOutput(BaseModel):
    title: str
    category: str = "other"
    channel: str = "web"
    brand: str = ""
    summary: str
    steps: list[StepOut] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    advice: str
    indicators: IndicatorsOut = Field(default_factory=IndicatorsOut)
    parent_id: str = ""
    relation: Literal["new_root", "variant", "duplicate"] = "new_root"
    novelty_reason: str = ""


class ScammerLine(BaseModel):
    message: str
    step_index: int = 0
    intent: str = ""
