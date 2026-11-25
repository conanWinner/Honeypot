"""Structured contracts between agent nodes. The model fills these; the server enforces them.

Small models often return a string where a list is required, or an enum in the wrong case.
Validators coerce those shapes so one bad field does not burn a second analyst call.
"""

import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_GOALS = {
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
}


def _text(value, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item is not None)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _str_list(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [json.dumps(value, ensure_ascii=False)]
    if isinstance(value, list):
        items = []
        for item in value:
            if item is None or item == "":
                continue
            if isinstance(item, str):
                items.append(item)
            elif isinstance(item, dict):
                items.append(json.dumps(item, ensure_ascii=False))
            else:
                items.append(str(item))
        return items
    return [str(value)]


def _object_list(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _enum(value, allowed: set[str], default: str) -> str:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        lowered = value.strip().lower().replace(" ", "_").replace("-", "_")
        return lowered if lowered in allowed else default
    return default


class MatchOut(BaseModel):
    script_id: str = ""
    title: str = ""
    confidence: float = 0
    current_step_index: int = 0
    current_step_intent: str = ""
    reason: str = ""

    @field_validator("script_id", "title", "current_step_intent", "reason", mode="before")
    @classmethod
    def _strings(cls, value):
        return _text(value)


class BranchOut(BaseModel):
    detected: bool = False
    kind: Literal["none", "known_variant", "new"] = "none"
    hook: str = ""
    description: str = ""
    variant_script_id: str = ""

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value):
        return _enum(value, {"none", "known_variant", "new"}, "none")

    @field_validator("hook", "description", "variant_script_id", mode="before")
    @classmethod
    def _strings(cls, value):
        return _text(value)


class AnalystOutput(BaseModel):
    scammer_intent: str = ""
    step_label: str = ""
    red_flags: list[str] = Field(default_factory=list)
    extracted_fact: str = ""
    scammer_suspicion: float = 0
    matches: list[MatchOut] = Field(default_factory=list)
    branch: BranchOut = Field(default_factory=BranchOut)
    notes: str = ""

    @field_validator("scammer_intent", "step_label", "extracted_fact", "notes", mode="before")
    @classmethod
    def _strings(cls, value):
        return _text(value)

    @field_validator("red_flags", mode="before")
    @classmethod
    def _flags(cls, value):
        return _str_list(value)

    @field_validator("matches", mode="before")
    @classmethod
    def _matches(cls, value):
        return _object_list(value)


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
    ] = "ask_next_instruction"
    rationale: str = ""
    tone: str = ""
    must_not: list[str] = Field(default_factory=list)
    facts_to_use: list[str] = Field(default_factory=list)

    @field_validator("goal", mode="before")
    @classmethod
    def _goal(cls, value):
        return _enum(value, _GOALS, "ask_next_instruction")

    @field_validator("rationale", "tone", mode="before")
    @classmethod
    def _strings(cls, value):
        return _text(value)

    @field_validator("must_not", "facts_to_use", mode="before")
    @classmethod
    def _lists(cls, value):
        return _str_list(value)


class PersonaOutput(BaseModel):
    reply: str = ""
    memory_note: str = ""

    @field_validator("reply", "memory_note", mode="before")
    @classmethod
    def _strings(cls, value):
        return _text(value)


class SafetyOutput(BaseModel):
    approved: bool = True
    violations: list[str] = Field(default_factory=list)
    action: Literal["allow", "rewrite", "fallback"] = "allow"
    safe_reply: str = ""
    notes: str = ""
    jailbreak: bool = False
    scammer_suspicious: bool = False
    suspicion_level: float = 0

    @field_validator("action", mode="before")
    @classmethod
    def _action(cls, value):
        return _enum(value, {"allow", "rewrite", "fallback"}, "fallback")

    @field_validator("violations", mode="before")
    @classmethod
    def _violations(cls, value):
        return _str_list(value)

    @field_validator("safe_reply", "notes", mode="before")
    @classmethod
    def _strings(cls, value):
        return _text(value)


class StepOut(BaseModel):
    actor: Literal["scammer", "victim"] = "scammer"
    intent: str = ""
    phrases: list[str] = Field(default_factory=list)

    @field_validator("actor", mode="before")
    @classmethod
    def _actor(cls, value):
        return _enum(value, {"scammer", "victim"}, "scammer")

    @field_validator("intent", mode="before")
    @classmethod
    def _intent(cls, value):
        return _text(value)

    @field_validator("phrases", mode="before")
    @classmethod
    def _phrases(cls, value):
        return _str_list(value)


class IndicatorsOut(BaseModel):
    phones: list[str] = Field(default_factory=list)
    bank_accounts: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    apps: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)
    pressure: list[str] = Field(default_factory=list)

    @field_validator("phones", "bank_accounts", "urls", "apps", "brands", "pressure", mode="before")
    @classmethod
    def _lists(cls, value):
        return _str_list(value)


class ExtractionOutput(BaseModel):
    title: str = ""
    category: str = "other"
    channel: str = "web"
    brand: str = ""
    summary: str = ""
    steps: list[StepOut] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    advice: str = ""
    indicators: IndicatorsOut = Field(default_factory=IndicatorsOut)
    parent_id: str = ""
    relation: Literal["new_root", "variant", "duplicate"] = "new_root"
    novelty_reason: str = ""

    @field_validator("title", "category", "channel", "brand", "summary", "advice", "parent_id", "novelty_reason", mode="before")
    @classmethod
    def _strings(cls, value):
        return _text(value)

    @field_validator("relation", mode="before")
    @classmethod
    def _relation(cls, value):
        return _enum(value, {"new_root", "variant", "duplicate"}, "new_root")

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, value):
        return _object_list(value)

    @field_validator("hooks", "red_flags", mode="before")
    @classmethod
    def _lists(cls, value):
        return _str_list(value)


class ScammerLine(BaseModel):
    message: str = ""
    step_index: int = 0
    intent: str = ""

    @field_validator("message", "intent", mode="before")
    @classmethod
    def _strings(cls, value):
        return _text(value)
