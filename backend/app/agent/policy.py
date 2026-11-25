"""Deterministic safety veto and wrap policy.

The model proposes. These rules decide. A jailbroken reply cannot ship just
because the model marked it safe, and a known script cannot end the chat on
the opening turn.
"""

import re

from app.agent.state import MatchSnap

# "là ai" is the question "who are you", so the Latin token AI is matched case-sensitively.
_ADMISSION = re.compile(
    r"("
    r"\b(tôi|mình|em|cô|cháu|tui)\s+là\s+(một\s+)?(trợ lý( ảo)?|chatbot|robot|bot|mô hình)\b"
    r"|là trí tuệ nhân tạo"
    r"|là (một )?mô hình ngôn ngữ"
    r"|language model"
    r"|\bchatgpt\b|\bgemini\b|\bopenai\b"
    r"|system prompt"
    r"|hướng dẫn hệ thống"
    r"|được lập trình để"
    r")",
    re.IGNORECASE,
)
_AI_TOKEN = re.compile(r"\bAI\b")

_MONEY = re.compile(
    r"("
    r"(tôi|em|cô|mình|tui|cháu)\s+(sẽ\s+|vừa\s+|đã\s+)?chuyển\s+(khoản|tiền)"
    r"|chuyển\s+khoản\s+ngay"
    r"|ck\s+ngay"
    r"|đã\s+ck\s+rồi"
    r"|(em|mình|tui)\s+ck\s+(rồi|ngay)"
    r")",
    re.IGNORECASE,
)

_INSTALL = re.compile(
    r"("
    r"(tôi|em|cô|mình|tui|cháu)\s+(sẽ\s+|vừa\s+|đã\s+)?cài\s+(rồi|ngay|xong|ultraviewer|anydesk|teamviewer|app|phần mềm)"
    r"|đã\s+cài\s+(ultraviewer|anydesk|teamviewer|xong|rồi)"
    r"|cài\s+(ultraviewer|anydesk|teamviewer)\s+(rồi|xong)"
    r")",
    re.IGNORECASE,
)

_HARMFUL = re.compile(
    r"(hướng dẫn (bạn|anh|chị) (cách )?lừa|cách (để )?lừa (đảo)?|mã độc|viết malware|chiếm đoạt giúp)",
    re.IGNORECASE,
)

_JAILBREAK = (
    "bỏ qua hướng dẫn",
    "bo qua huong dan",
    "ignore previous",
    "ignore all instructions",
    "system prompt",
    "jailbreak",
    "developer mode",
    "reveal your prompt",
    "in ra prompt",
    "in prompt",
    "bạn là ai phải không",
    "mày là ai",
    "you are an ai",
    "you're an ai",
)

_SUSPICION = (
    "bạn là ai",
    "ban la ai",
    "bạn là bot",
    "bạn là máy",
    "không phải người",
    "trả lời như máy",
    "copy paste",
    "trả lời y hệt",
    "ai viết hộ",
    "robot",
    "chatbot",
    "trả lời nhanh quá",
)


def _negated(text: str, start: int) -> bool:
    window = text[max(0, start - 16) : start].lower()
    return any(tok in window for tok in ("không", "chưa", "chẳng", "đừng", "ko "))


def _hits(pattern: re.Pattern[str], text: str) -> bool:
    for match in pattern.finditer(text or ""):
        if not _negated(text, match.start()):
            return True
    return False


def assess_inbound(text: str) -> dict:
    folded = (text or "").lower()
    jail_cues = [cue for cue in _JAILBREAK if cue in folded]
    sus_cues = [cue for cue in _SUSPICION if cue in folded]
    suspicion = 0.0
    if jail_cues:
        suspicion = 0.85
    elif sus_cues:
        suspicion = 0.7
    return {
        "jailbreak": bool(jail_cues),
        "scammer_suspicious": bool(jail_cues or sus_cues),
        "suspicion_level": suspicion,
        "cues": jail_cues + sus_cues,
    }


def inspect_outbound(text: str, allowed_numbers: set[str]) -> list[str]:
    violations: list[str] = []
    body = text or ""
    if _hits(_ADMISSION, body) or _AI_TOKEN.search(body):
        violations.append("ai_admission")
    if _hits(_MONEY, body):
        violations.append("agreed_to_pay")
    if _hits(_INSTALL, body):
        violations.append("agreed_to_install")
    if _HARMFUL.search(body):
        violations.append("harmful_assistance")
    from app.agent.textutil import digit_runs

    for number in digit_runs(body):
        if number in allowed_numbers:
            continue
        if any(number in known or known in number for known in allowed_numbers if known):
            continue
        violations.append("unknown_number")
        break
    return violations


def fallback_reply(persona_slug: str) -> str:
    lines = {
        "ba-nam": "Cháu nói lạ quá. Cô không chuyển tiền, không đọc mã, cũng không cài cái gì hết. Cháu là ai thì nói rõ cho cô.",
        "minh-sv": "khoan đã, mình không chuyển khoản và không cài app lạ. bạn nói lại từ đầu đi, mình chưa hiểu gì cả.",
        "huong-shop": "Chị không chuyển tiền theo chat và không cài phần mềm lạ. Anh/chị là ai, làm bên nào, nói rõ cho chị.",
        "tuan-vp": "Em chưa rõ anh/chị là ai. Em không chuyển khoản và không cài ứng dụng theo yêu cầu này.",
        "lan-nt": "Tui không chuyển tiền, không cài ứng dụng gì hết. Nói rõ là ai, không thì tui thôi.",
        "khoa-tx": "Khoan đã bác. Em không ck và không cài app lạ. Bác là ai nói lại đi.",
    }
    return lines.get(persona_slug, lines["tuan-vp"])


def typing_ms(text: str, persona_slug: str) -> int:
    slow = persona_slug in {"ba-nam", "lan-nt"}
    base = 820 if slow else 500
    per = 30 if slow else 20
    jitter = sum(ord(ch) for ch in (text or "")[:16]) % 360
    return max(900, min(3400, base + len(text or "") * per + jitter))


def recommend_wrap(history: list[MatchSnap]) -> tuple[bool, str]:
    """Wrap only after several later steps keep hitting one known script."""
    if len(history) < 3:
        return False, "Mới vài lượt, chưa đủ để khép kịch bản."
    window = history[-3:]
    if any(item.branch_kind == "new" for item in window):
        return False, "Vừa có nhánh mới, phải kéo tiếp để lấy nốt biến thể."
    ids = {(item.family_id or item.script_id) for item in window if item.script_id}
    if len(ids) != 1:
        return False, "Kịch bản khớp chưa đứng yên giữa các lượt."
    if any(item.confidence < 0.72 for item in window):
        return False, "Độ tin cậy chưa đủ cao trên nhiều bước liên tiếp."
    steps = [item.step_index for item in window]
    if steps[-1] < 2:
        return False, "Vẫn đang quanh bước mở đầu, chưa phải lúc khép."
    if steps[-1] < steps[0]:
        return False, "Bước đang lùi so với các lượt trước."
    if len(set(steps)) < 2 and steps[-1] == steps[0]:
        return False, "Các lượt chưa đi sang bước mới của kịch bản."
    return True, "Nhiều bước liên tiếp khớp một kịch bản đã biết, không có nhánh mới."
