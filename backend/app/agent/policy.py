"""Deterministic safety veto and wrap policy.

The model proposes. These rules decide. A jailbroken reply cannot ship just
because the model marked it safe, and a known script cannot end the chat on
the opening turn.
"""

import re

from app.agent.state import MatchSnap
from app.agent.textutil import fold

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
    r"(tôi|em|cô|mình|tui|cháu|con|bác|chị)\s+(sẽ\s+|vừa\s+|đã\s+|để\s+)?(chuyển|trả|gửi|nạp)\s+(khoản|tiền|liền|ngay|luôn|giúp|qua)"
    r"|trả\s+liền"
    r"|chuyển\s+liền"
    r"|chuyển\s+ngay"
    r"|chuyển\s+luôn"
    r"|chuyển\s+khoản\s+ngay"
    r"|gửi\s+tiền"
    r"|nạp\s+(tiền|\d|luôn|liền|ngay)"
    r"|đồng\s+ý\s+(nạp|chuyển|gửi|ck)"
    r"|ck\s+(ngay|liền|luôn|xong|rồi)"
    r"|đã\s+ck\s+rồi"
    r"|(em|mình|tui|con)\s+ck\s+(rồi|ngay|liền|luôn)?"
    r"|để\s+(bác|anh|chị|em|cô|cháu|con|mình|tui)\s+chuyển"
    r"|ok\s+(em\s+|con\s+|mình\s+|tui\s+)?chuyển"
    r"|có\s+tiền\s+trả"
    r"|trả\s+cho\s+(anh|chị|bác|cháu|con|em)"
    r"|chuyển\s+cho\s+(anh|chị|bác|cháu|con)"
    r")",
    re.IGNORECASE,
)
# Teencode and no-diacritics, matched on folded text: bank, ck, nap, gui tien.
_MONEY_PLAIN = re.compile(
    r"("
    r"\b(gui|chuyen)\s+tien\b"
    r"|chuyen\s+khoan"
    r"|\bnap\s+(tien|\d|luon|lien|ngay|xong|roi)"
    r"|dong\s+y\s+(nap|chuyen|gui|ck|bank)"
    r"|\bck\s+(ngay|lien|luon|xong|roi)\b"
    r"|\b(e|em|co|minh|tui|chau|con)\s+(ck|bank)\b"
    r"|\bbank\s+(lun|luon|ngay|lien|roi|xong)\b"
    r"|\b(ok|oke|okay)\b.{0,20}\b(bank|ck|chuyen|gui|nap)\b"
    r"|vua\s+(ck|bank|chuyen|gui|nap)\b"
    r")"
)
_OTP_PLAIN = re.compile(
    r"("
    r"\b(gui|doc|nhan|bao|dua)\s+(ma\s+otp|otp|ma\s+xac)"
    r"|ma\s+otp"
    r"|\botp\s+(ngay|lien|day|luon|roi)\b"
    r"|\b(ok|oke)\b.{0,20}\b(otp|ma\s+xac)\b"
    r")"
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
_QUESTION = re.compile(r"\b(nào|nao|đâu|dau|ai|gì|gi|sao)\b", re.IGNORECASE)
# "con đang học / con trai" is the child. "con chuyển" is the speaker.
_CON_FAMILY = re.compile(
    r"("
    r"\bcon\s+(trai|gái|gai|cái|cai|nuôi|nuoi|của|cua|tôi|toi|em|cô|co|đang|dang|ở|o|bên|học|hoc|làm|lam)\b"
    r"|\b(về|ve|của|cua|cho|với|voi|thằng|thang|đứa|dua)\s+con\b"
    r")",
    re.IGNORECASE,
)
_CON_AS_SELF = re.compile(r"\bcon\b(?!\s+(trai|gái|gai|cái|cai|nuôi|nuoi|của|cua))", re.IGNORECASE)

# "cái app" is a determiner, not an install. Require a completion verb or "cài đặt".
_INSTALL = re.compile(
    r"("
    r"(tôi|em|cô|mình|tui|cháu)\s+(sẽ\s+|vừa\s+|đã\s+)(cài|tải)\b"
    r"|đã\s+(cài|tải)\b"
    r"|vừa\s+(cài|tải)\b"
    r"|(cài|tải)\s+(rồi|xong|về)\b"
    r"|(cài|tải)\s+(ultraviewer|anydesk|teamviewer|app|phần mềm)\s+(rồi|xong|về)"
    r"|cài\s+đặt"
    r"|đồng\s+ý\s+(cài|tải)"
    r")"
    ,
    re.IGNORECASE,
)
_INSTALL_PLAIN = re.compile(
    r"("
    r"\bcai\s+dat\b"
    r"|\b(da|vua)\s+(cai|tai)\b"
    r"|\b(cai|tai)\s+(roi|xong|ve)\b"
    r"|\b(cai|tai)\s+(anydesk|ultraviewer|teamviewer|app|phan mem|ung dung)\s+(roi|xong|ve)\b"
    r"|(anydesk|ultraviewer|teamviewer).{0,30}\b(roi|xong)\b"
    r"|dong\s+y\s+(cai|tai)\b"
    r")"
)
_ASK_THEM = re.compile(
    r"(đường dẫn|duong dan|\blink\b|tài khoản|tai khoan|\bstk\b|ultraviewer|anydesk|teamviewer)",
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
    return bool(re.search(r"(^|\s)(không|khong|chưa|chua|chẳng|chang|đừng|dung|ko)\s*$", prefix))


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


def _con_is_family(text: str, persona_id: str | None) -> bool:
    """'con' is the child when the persona's profile talks about a son or daughter and the sentence does too."""
    if _CON_FAMILY.search(text or "") or _CON_FAMILY.search(fold(text or "")):
        if not persona_id:
            return True
        from app.data.personas import PERSONAS

        persona = next((item for item in PERSONAS if item["id"] == persona_id), None)
        if persona is None:
            return True
        relative = fold((persona.get("fake_profile") or {}).get("relative") or "")
        hooks = " ".join(persona.get("hooks") or [])
        return "con" in relative or "con" in fold(hooks)
    return False


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
        word = match.group(1).lower()
        if word == "con" and _con_is_family(body, persona_id):
            continue
        if word not in allowed_self:
            issues.append("pronoun_mix")
            break
    if "pronoun_mix" not in issues:
        for match in _ADDRESS_FRAME.finditer(body):
            if match.group(1).lower() not in allowed_other:
                issues.append("pronoun_mix")
                break
    if (
        spec.get("forbid_con_as_self")
        and "pronoun_mix" not in issues
        and _CON_AS_SELF.search(body)
        and not _con_is_family(body, persona_id)
    ):
        issues.append("pronoun_mix")
    for word in spec.get("forbid_words") or []:
        if re.search(rf"\b{re.escape(word)}\b", body, re.IGNORECASE):
            if "pronoun_mix" not in issues:
                issues.append("pronoun_mix")
            break
    return issues


def _reports_allowed_code(text: str, allowed: set[str]) -> bool:
    found = set(re.findall(r"\d{4,8}", text or ""))
    if not found:
        return False
    known = {item for item in allowed if item and item.isdigit()}
    return found <= known


def inspect_outbound(text: str, allowed_numbers: set[str], persona_id: str | None = None) -> list[str]:
    violations: list[str] = []
    body = text or ""
    if _hits(_ADMISSION, body) or _AI_TOKEN.search(body):
        violations.append("ai_admission")
    folded = fold(body)
    if _hits(_MONEY, body) or _hits(_MONEY_PLAIN, folded):
        violations.append("agreed_to_pay")
    if _hits(_INSTALL, body) or _hits(_INSTALL_PLAIN, folded):
        violations.append("agreed_to_install")
    if _hits(_OTP_PLAIN, folded) and not _reports_allowed_code(body, allowed_numbers):
        violations.append("agreed_to_share_otp")
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


_GUARD_TOPIC = re.compile(
    r"("
    r"tien|trieu|nghin|ngan|vnd|"
    r"otp|ma otp|ma xac|"
    r"anydesk|ultraviewer|teamviewer|"
    r"\b(bank|chuyen|ck|nap|stk)\b|"
    r"tai khoan|duong dan|\blink\b|"
    r"\d{6,}"
    r")"
)
_ASK_KEEP = re.compile(
    r"(tài khoản|tai khoan|stk|link|đường dẫn|duong dan|http|anydesk|ultraviewer|teamviewer|ứng dụng|ung dung|cài|otp|\?)",
    re.IGNORECASE,
)

VIOLATION_LABELS = {
    "agreed_to_pay": "Câu nháp đồng ý chuyển, nạp hoặc gửi tiền",
    "agreed_to_install": "Câu nháp nhận đã tải hoặc cài ứng dụng",
    "agreed_to_share_otp": "Câu nháp gửi hoặc đọc mã OTP",
    "ai_admission": "Câu nháp nhận mình là máy",
    "expert_shutdown": "Câu nháp giảng như chuyên gia",
    "pronoun_mix": "Sai cặp đại từ của hồ sơ",
    "rude_register": "Giọng thô",
    "unknown_number": "Có số không nằm trong hồ sơ giả",
    "harmful_assistance": "Câu nháp hướng dẫn gây hại",
    "repeated_opening": "Mở đầu trùng câu vừa nói",
}


def is_extraction_ask(text: str) -> bool:
    """Asking the scammer to send a link, account, or app name is the point of the turn."""
    raw = text or ""
    folded = fold(raw)
    if "?" not in raw and "khong" not in folded and "nao" not in folded:
        return False
    if _hits(_INSTALL, raw) or _hits(_INSTALL_PLAIN, folded) or _hits(_MONEY, raw) or _hits(_MONEY_PLAIN, folded):
        return False
    return bool(_ASK_THEM.search(raw) or _ASK_THEM.search(folded))


def with_fake_otp(text: str, persona_id: str, otp: str) -> str:
    """When the planner asked for the fake code, the reply has to contain that code and no real one."""
    code = (otp or "").strip()
    if not code or code in (text or ""):
        return text or ""
    tails = {
        "ba-nam": f"Mã cô thấy là {code}. Cháu lấy mã này để làm gì?",
        "minh-sv": f"máy em hiện mã {code}. anh lấy mã này làm gì, em chưa xác nhận",
        "huong-shop": f"App hiện mã {code}. Anh/chị dùng mã này để làm gì? Chị chưa xác nhận.",
        "tuan-vp": f"Máy em hiện mã {code}. Anh/chị dùng để đối soát việc gì? Em chưa xác nhận.",
        "lan-nt": f"Máy hiện mã {code}. Lấy mã này làm gì, tui chưa bấm đồng ý.",
        "khoa-tx": f"ví hiện mã {code}. bác lấy làm gì, em chưa xác nhận",
    }
    return tails.get(persona_id, f"Mã hiện lên là {code}.")


def needs_guard(text: str) -> bool:
    """Money, an amount, an app, a code, a long number, or a link: the model guard must see the draft."""
    folded = fold(text or "")
    if _GUARD_TOPIC.search(folded):
        return True
    return bool(re.search(r"https?://|www\.|(?<![\w@])[a-z0-9-]+\.[a-z]{2,24}", text or "", re.IGNORECASE))


def rewrite_opening(text: str, recent: list[str] | None) -> str:
    """Change a repeated opening and keep the rest, especially a question that asks for an account, link, or app."""
    raw = (text or "").strip()
    if not raw or not repeats_opening(raw, recent):
        return raw
    pieces = re.split(r"(?<=[?.!])\s+", raw, maxsplit=1)
    if len(pieces) == 2 and pieces[1].strip():
        return pieces[1].strip()
    rest = raw[10:].lstrip(" ,:;–-")
    if not rest:
        return raw
    if rest[0].isalpha():
        rest = rest[0].lower() + rest[1:]
    rewritten = f"Khoan đã, {rest}"
    if _ASK_KEEP.search(raw) and not _ASK_KEEP.search(rewritten):
        return raw
    return rewritten


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
