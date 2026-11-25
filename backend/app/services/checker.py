"""One-shot reading of a suspicious message or a short transcript."""

import re

from app.agent.orchestrator import pack
from app.agent.prompts import ANALYST_SYSTEM
from app.agent.schemas import AnalystOutput
from app.services.matching import branch_hint, candidate_payload, search_scripts


_BENIGN = re.compile(
    r"(chúc mừng sinh nhật|sinh nhật vui|happy birthday|chúc mừng năm mới|chúc ngủ ngon|cuối tuần cafe)",
    re.IGNORECASE,
)
_SCAM_CUE = re.compile(
    r"(otp|chuyển khoản|chuyển tiền|tài khoản|stk|http|cài app|cài phần mềm|phí |công an|giám định|mã xác|bấm link|bấm vào)",
    re.IGNORECASE,
)


def _looks_benign(text: str) -> bool:
    return bool(_BENIGN.search(text or "")) and not _SCAM_CUE.search(text or "")


def check_text(session, text: str, provider, persona=None) -> dict:
    ranked = search_scripts(session, text, provider, k=4)
    from sqlalchemy import select
    from app.models import Script

    scripts = list(session.scalars(select(Script).where(Script.status == "published")).all())
    hint = {"detected": False, "kind": "none", "hook": "", "description": "", "variant_script_id": ""}
    if persona is not None and ranked:
        hint = branch_hint(text, persona, ranked, scripts)
    candidates = candidate_payload(ranked)
    analyst = provider.complete(
        AnalystOutput,
        ANALYST_SYSTEM,
        pack(
            "Đây là một tin nhắn hoặc đoạn hội thoại nghi lừa đảo, chưa có nạn nhân đóng vai.",
            {"message": text, "history": [], "persona_hooks": [], "candidates": candidates, "branch_hint": hint, "inbound": {}, "turn_index": 0},
        ),
        0.2,
        thinking=False,
        model=None,
        role="analyst",
        max_tokens=420,
    )
    top_rank = ranked[0] if ranked else None
    confidence = float(top_rank["score"]) if top_rank else 0.0
    if analyst.matches:
        confidence = max(confidence, float(analyst.matches[0].confidence or 0))
    intent = (analyst.scammer_intent or "").lower()
    hot = any(word in intent for word in ("otp", "chuyển", "cài", "giám định", "link"))
    if confidence >= 0.82 or (hot and confidence >= 0.55):
        level, label = "rat_cao", "Rất cao"
    elif confidence >= 0.62 or hot:
        level, label = "cao", "Cao"
    elif confidence >= 0.34 or analyst.red_flags:
        level, label = "trung_binh", "Trung bình"
    else:
        level, label = "thap", "Thấp"
    scam_cues = bool(_SCAM_CUE.search(text)) or hot
    if _looks_benign(text):
        level, label = "thap", "Thấp"
        is_scam = False
        verdict = "benign"
    elif level in {"cao", "rat_cao"} or (scam_cues and confidence >= 0.55):
        is_scam = True
        verdict = "scam"
    elif level == "thap" and not scam_cues:
        is_scam = False
        verdict = "benign"
    else:
        is_scam = False
        verdict = "unclear"

    next_step = None
    advice = "Không chuyển tiền, không đọc mã OTP, không bấm đường dẫn trong tin nhắn. Kiểm tra lại trên ứng dụng chính thức mà bạn tự mở."
    matched = None
    if top_rank is not None:
        script = top_rank["script"]
        matched = {"id": script.id, "title": script.title, "category": script.category, "confidence": round(confidence, 3)}
        advice = script.advice or advice
        index = int(top_rank["step_index"])
        steps = script.steps or []
        current = steps[index] if 0 <= index < len(steps) else None
        nxt = next((step for step in steps[index + 1 :] if step.get("actor") == "scammer"), None)
        if nxt:
            next_step = {"intent": nxt.get("intent"), "phrases": (nxt.get("phrases") or [])[:2]}
        elif current and current.get("actor") == "scammer":
            next_step = {
                "intent": f"Đây đã là bước cuối thường gặp: {current.get('intent')}",
                "phrases": (current.get("phrases") or [])[:1],
            }
    benign = verdict == "benign" and _looks_benign(text)
    if benign:
        matched = None
        next_step = None
        advice = "Tin này giống lời chúc hoặc trò chuyện thường. Không cần làm gì thêm."
    return {
        "risk": level,
        "risk_label": label,
        "is_scam": is_scam,
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "intent": "Lời nhắn thông thường." if benign else analyst.scammer_intent,
        "red_flags": [] if benign else analyst.red_flags,
        "matched_script": matched,
        "next_step": next_step,
        "advice": advice,
        "branch": hint,
        "mock": provider.is_mock,
    }
