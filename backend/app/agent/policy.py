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
    r"(tôi|em|cô|mình|tui|cháu|con|bác|chị)\s+(sẽ\s+|vừa\s+|đã\s+|để\s+)?(chuyển|trả)\s+(khoản|tiền|liền|ngay|luôn|giúp)"
    r"|trả\s+liền"
    r"|chuyển\s+liền"
    r"|chuyển\s+ngay"
    r"|chuyển\s+luôn"
    r"|chuyển\s+khoản\s+ngay"
    r"|ck\s+(ngay|liền)"
    r"|đã\s+ck\s+rồi"
    r"|(em|mình|tui|con)\s+ck\s+(rồi|ngay|liền)"
    r"|để\s+(bác|anh|chị|em|cô|cháu|con|mình|tui)\s+chuyển"
    r"|ok\s+(em\s+|con\s+|mình\s+|tui\s+)?chuyển"
    r"|có\s+tiền\s+trả"
    r"|trả\s+cho\s+(anh|chị|bác|cháu|con|em)"
    r"|chuyển\s+cho\s+(anh|chị|bác|cháu|con)"
    r")",
    re.IGNORECASE,
)

_RUDE = re.compile(r"\b(tao|mày|tụi bây|chúng mày)\b", re.IGNORECASE)
_SELF_FRAME = re.compile(
    r"\b(cô|bà|em|chị|tui|mình|con|tao|bác|cháu)\s+(không|sẽ|đã|chưa|đang|trả|chuyển|đi|nghe|ck)\b",
    re.IGNORECASE,
)
_EXPERT = re.compile(
    r"(đây là (chiêu |vụ )?lừa|không bao giờ (gọi|nhắn|hỏi)|ứng dụng chính thức|tổng đài chính thức|mã vận đơn qua ứng dụng)",
    re.IGNORECASE,
)
# Only a vocative ("cháu ơi") is an address. "cô có" and "anh nói" are ordinary words.
_ADDRESS_FRAME = re.compile(
    r"\b(bác|cháu|anh|chị|cô|em|mày)\s+ơi\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(r"\b(nào|đâu|ai|gì|sao)\b", re.IGNORECASE)
_CON_AS_SELF = re.compile(r"\bcon\b(?!\s+(trai|gái|cái|nuôi|của))", re.IGNORECASE)

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


def _clause_bounds(text: str, start: int) -> tuple[int, int]:
    left = -1
    for mark in ".,!?;\n":
        left = max(left, text.rfind(mark, 0, start))
    end = len(text)
    for mark in ".!\n":
        found = text.find(mark, start)
        if found >= 0:
            end = min(end, found)
    question = text.find("?", start)
    if question >= 0:
        end = min(end, question + 1)
    return left + 1, end


def _negated(text: str, start: int) -> bool:
    """A negator counts only when it sits at the end of the same clause, right before the verb.

    "Không sao, cô chuyển liền" is an agreement: the "không" belongs to the previous clause.
    "Cô không trả liền" is a refusal.
    """
    left, _end = _clause_bounds(text, start)
    prefix = text[left:start].lower()
    return bool(re.search(r"(^|\s)(không|chưa|chẳng|đừng|ko)\s*$", prefix))


def _is_question(text: str, start: int) -> bool:
    _left, end = _clause_bounds(text, start)
    clause = text[start:end]
    if "?" in clause:
        return True
    return bool(_QUESTION.search(clause))


def _hits(pattern: re.Pattern[str], text: str) -> bool:
    for match in pattern.finditer(text or ""):
        if _negated(text, match.start()) or _is_question(text, match.start()):
            continue
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


def voice_issues(text: str, persona_id: str | None) -> list[str]:
    """Light check: rude register, or a pronoun pair that is not this persona's."""
    from app.data.personas import PRONOUNS

    issues: list[str] = []
    body = text or ""
    if _RUDE.search(body):
        issues.append("rude_register")
    spec = PRONOUNS.get(persona_id or "")
    if not spec:
        return issues
    allowed_self = {word.lower() for word in spec.get("self") or []}
    allowed_other = {word.lower() for word in spec.get("other") or []}
    for match in _SELF_FRAME.finditer(body):
        if match.group(1).lower() not in allowed_self:
            issues.append("pronoun_mix")
            break
    if "pronoun_mix" not in issues:
        for match in _ADDRESS_FRAME.finditer(body):
            if match.group(1).lower() not in allowed_other:
                issues.append("pronoun_mix")
                break
    if spec.get("forbid_con_as_self") and "pronoun_mix" not in issues and _CON_AS_SELF.search(body):
        issues.append("pronoun_mix")
    for word in spec.get("forbid_words") or []:
        if re.search(rf"\b{re.escape(word)}\b", body, re.IGNORECASE):
            if "pronoun_mix" not in issues:
                issues.append("pronoun_mix")
            break
    return issues


def inspect_outbound(text: str, allowed_numbers: set[str], persona_id: str | None = None) -> list[str]:
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
    if _EXPERT.search(body):
        violations.append("expert_shutdown")
    violations.extend(voice_issues(body, persona_id))
    from app.agent.textutil import digit_runs

    for number in digit_runs(body):
        if number in allowed_numbers:
            continue
        if any(number in known or known in number for known in allowed_numbers if known):
            continue
        violations.append("unknown_number")
        break
    return violations


_FALLBACKS = {
    "ba-nam": [
        "Cháu nói lại được không? Cô chưa hiểu gì cả.",
        "Khoan đã cháu, cô đang nghe. Rồi sao nữa?",
        "Cô chưa làm gì đâu. Cháu muốn cô làm bước nào?",
    ],
    "minh-sv": [
        "Khoan, em chưa hiểu. Anh nói lại được không?",
        "Em chưa làm gì. Rồi sao nữa?",
        "Anh là ai vậy, em đang nghe đây.",
    ],
    "huong-shop": [
        "Khoan đã, chị chưa hiểu. Anh nói lại được không?",
        "Chị chưa làm gì hết. Rồi sao nữa?",
        "Anh là ai, chị đang nghe.",
    ],
    "tuan-vp": [
        "Khoan, em chưa hiểu. Anh nói lại từ đầu được không?",
        "Em chưa làm gì. Rồi sao nữa?",
        "Anh là ai vậy, em đang nghe.",
    ],
    "lan-nt": [
        "Khoan, tui chưa hiểu. Bạn nói lại được không?",
        "Tui chưa làm gì hết. Rồi sao nữa?",
        "Bạn là ai, tui đang nghe.",
    ],
    "khoa-tx": [
        "Khoan đã bác, em chưa hiểu. Bác nói lại được không?",
        "Em chưa làm gì. Rồi sao nữa?",
        "Bác là ai, em đang nghe.",
    ],
}


def repeats_opening(text: str, recent: list[str] | None, width: int = 10) -> bool:
    """True when this reply opens like one of the last few victim lines."""
    opening = (text or "").strip().lower()
    if len(opening) < width:
        return False
    head = opening[:width]
    for old in (recent or [])[-4:]:
        previous = (old or "").strip().lower()
        if len(previous) >= width and previous[:width] == head:
            return True
    return False


def fallback_reply(persona_slug: str, recent: list[str] | None = None) -> str:
    options = _FALLBACKS.get(persona_slug) or _FALLBACKS["tuan-vp"]
    recent_norm = [(item or "").strip().lower() for item in (recent or [])]
    for line in options:
        folded = line.strip().lower()
        if folded in recent_norm or repeats_opening(line, recent):
            continue
        return line
    return options[len(recent_norm) % len(options)]


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
