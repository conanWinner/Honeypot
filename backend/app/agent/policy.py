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
    r"\bcon\s+(trai|gái|gai|cái|cai|nuôi|nuoi|của|cua|tôi|toi|tui|mình|minh|nhà|nha|em|cô|co|đang|dang|ở|o|bên|học|hoc|làm|lam)\b"
    r"|\b(về|ve|của|cua|cho|với|voi|thằng|thang|đứa|dua|đón|don|trông|trong|đưa|dua|nuôi|nuoi|chăm|cham|dỗ|do)\s+con\b"
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


# Clear commitments. A question mark later in the sentence does not cancel them.
# "chuyển cho ai, rồi sau đó" is not a commitment; the guard model decides that.
_COMMITMENT = re.compile(
    r"("
    r"\b(cai|cài)\s+xong\b"
    r"|\b(da|đã|vua|vừa)\s+(cai|cài|tai|tải)\b"
    r"|\b(tai|tải|cai|cài)\b.{0,40}\bve\b.{0,12}\broi\b"
    r"|\b(cai|tai)\s+\S+\s+(roi|xong)\b"
    r"|\b(da|đã|vua|vừa)\s+(bam|bấm|click|nhap|nhập|quet|quét)\b"
    r"|\b(bam|bấm|click)\s+vao\s+link\b.{0,40}\broi\b"
    r"|\bquet\s+ma\b.{0,30}\b(tra|roi|xong)\b"
    r"|\bgui\s+(tien\s+)?qua\b.{0,30}\b(luon|lun)\b"
    r"|\b(ck|bank)\s+(lun|luon|xong|ngay|lien)\b"
    r"|\b(ok|oke|okay)\b.{0,24}\b(bank|ck)\b"
    r"|\b(chuyen|chuyển)\s+\d+\s*(trieu|triệu|nghin|nghìn|k)\b"
    r"|\b(nap|nạp)\s+\d+"
    r"|\bdong\s*y\s+(chuyen|chuyển|nap|nạp|cai|cài|tai|tải|ck|gui)\b"
    r"|\bcai\s+dat\b"
    r"|\b(da|đã)\s+(nhap|nhập|chia\s+se|chia\s+sẻ)\s+(otp|ma)\b"
    r"|\b(doc|gui|nhan)\s+ma\s+(otp|xac)\b"
    r"|\botp\s+(ngay|lien|day)\b"
    r"|\b(chuyen|ck|nap|gui tien|tra)\s+(qua\s+)?(luon|lun|lien|ngay|xong|roi)\b"
    r"|\bchuyen\s+khoan\s+(ngay|lien|luon|xong)\b"
    r"|\b(ok|oke|okay)\b.{0,20}\b(chuyen|nap)\b"
    r"|\bnap\s+tien\b"
    r"|\bde\s+\S+\s+chuyen\s+khoan\b"
    r")",
    re.IGNORECASE,
)


def _clarifying_question(text: str) -> bool:
    """Asking who, why, whether, or what happens next is not a claim that the act already happened."""
    folded = fold(text or "")
    if re.search(r"(bao lau|cho ai|luon a\b|chuyen luon a|sao lai|xong thi)", folded):
        return True
    return bool(re.search(r"luôn à|cho ai|sao lại|xong thì", text or "", re.IGNORECASE))


def _completed_act(text: str) -> bool:
    folded = fold(text or "")
    return bool(
        re.search(
            r"(cai xong|da cai|da tai|vua tai|ve roi|da bam|da click|click vao link|quet ma|gui qua|bank lun|ck luon|ck xong|da nhap|chia se ma|dong y)",
            folded,
        )
    )


def hard_commitment(text: str) -> str:
    """Fast hard-block for a completed act. A clarifying question is left to the guard."""
    if _clarifying_question(text) and not _completed_act(text):
        return ""
    for source in ((text or ""), fold(text or "")):
        for match in _COMMITMENT.finditer(source):
            if _negated(source, match.start()):
                continue
            snippet = fold(match.group(0))
            if re.search(r"(cai|tai|bam|click|quet)", snippet):
                if re.search(r"(bam|click|quet)", snippet) and not re.search(r"(cai|tai)", snippet):
                    return "committed_act"
                return "agreed_to_install"
            if re.search(r"(otp|ma xac)", snippet) and re.search(r"(nhap|chia|doc|gui|nhan)", snippet):
                return "agreed_to_share_otp"
            return "agreed_to_pay"
    return ""


# "Are you a machine?" in any address form: chú có phải máy không, em là bot à,
# người thật không đấy, sao trả lời lạ vậy. Ignoring this is the fastest way to
# get caught, so it must reach the planner as suspicion.
_BOT_PROBE = re.compile(
    r"((có\s+)?phải\s+(là\s+)?|\blà\s+)(máy|bot|robot|người máy|chatbot|trí tuệ nhân tạo|tự động)\b"
    r"|\b(máy|bot|robot)\s+(à|hả|hở|phải không|không đấy|không vậy|ko|k)\b"
    r"|người\s+thật\s+(không|ko|k|à|hả|chứ|hay)"
    r"|trả\s+lời\s+(lạ|như máy|tự động|y hệt|giống máy|nhanh quá)",
    re.IGNORECASE,
)
# "AI" only in capitals: lowercase "ai" means "who".
_AI_PROBE = re.compile(r"\b(?:là|phải)\s+(?:là\s+)?(?:AI|A\.I)\b|\bAI\s+(?:à|hả|phải không)")


# Words a scammer uses when they start to doubt the victim. The analyst's
# scammer_suspicion only counts when the message itself shows one of these: models
# often score "how scammy is this" there instead, which would stall every turn.
_DOUBT = re.compile(
    r"(?i:(?:là|phải)\s+(?:máy|bot|robot|người máy)\b|\b(?:bot|robot|chatbot)\b|người\s+thật"
    r"|trả\s+lời\s+(?:lạ|như\s+máy|tự\s+động)|tự\s+động\s+trả\s+lời"
    r"|sao\s+(?:hỏi|nói)\s+(?:nhiều|lắm|kỹ)|hỏi\s+(?:nhiều|lắm)\s+(?:thế|vậy|quá)"
    r"|(?:không|ko|chẳng)\s+(?:tin|làm)\s+thì\s+thôi|thôi\s+(?:không|ko)\s+nói\s+nữa"
    r"|(?:gài|thử|test)\s+(?:tôi|tao|em|anh|chị)|có\s+vẻ\s+(?:lạ|không\s+bình\s+thường))"
    # "AI" only in capitals: "ai" is the everyday "who".
    r"|\bAI\b"
)


def doubt_cue(text: str) -> bool:
    return bool(_DOUBT.search(text or ""))


def assess_inbound(text: str) -> dict:
    folded = (text or "").lower()
    jail_cues = [cue for cue in _JAILBREAK if cue in folded]
    sus_cues = [cue for cue in _SUSPICION if cue in folded]
    probe = _BOT_PROBE.search(text or "") or _AI_PROBE.search(text or "")
    if probe and not sus_cues:
        sus_cues.append(probe.group(0).strip().lower())
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
        # "Cháu đang ở bệnh viện nào" addresses the scammer. Only a wrong word for THIS persona is a mix.
        if word in allowed_self or word in allowed_other:
            continue
        issues.append("pronoun_mix")
        break
    if "pronoun_mix" not in issues and len(_self_kin_used(body, spec)) > 1:
        # "Bác nói con trai cô…": two ways of saying "I" in one message.
        issues.append("pronoun_mix")
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


_DOTTED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")


def _amount_digits(text: str) -> set[str]:
    """'350.000 đồng' is a sum of money, not a phone or an account."""
    return {re.sub(r"\D", "", match.group(0)) for match in _DOTTED_AMOUNT.finditer(text or "")}


def _reports_allowed_code(text: str, allowed: set[str]) -> bool:
    found = set(re.findall(r"\d{4,8}", text or ""))
    if not found:
        return False
    known = {item for item in allowed if item and item.isdigit()}
    return found <= known


def soft_hints(text: str) -> list[str]:
    """Regex guesses for the guard. They do not block a line by themselves."""
    body = text or ""
    folded = fold(body)
    hints: list[str] = []
    if _hits(_ADMISSION, body) or _AI_TOKEN.search(body):
        hints.append("ai_admission")
    if _hits(_MONEY, body) or _hits(_MONEY_PLAIN, folded):
        hints.append("agreed_to_pay")
    if _hits(_INSTALL, body) or _hits(_INSTALL_PLAIN, folded):
        hints.append("agreed_to_install")
    if _hits(_OTP_PLAIN, folded):
        hints.append("agreed_to_share_otp")
    if _EXPERT.search(body):
        hints.append("expert_shutdown")
    return hints


def inspect_outbound(text: str, allowed_numbers: set[str], persona_id: str | None = None) -> list[str]:
    violations: list[str] = []
    body = text or ""
    folded = fold(body)
    if (_hits(_ADMISSION, body) or _AI_TOKEN.search(body)) and "?" not in body and not re.search(r"\bmà\b", body, re.IGNORECASE):
        violations.append("ai_admission")
    commitment = hard_commitment(body)
    if commitment == "agreed_to_pay":
        violations.append("agreed_to_pay")
    elif commitment == "agreed_to_install":
        violations.append("agreed_to_install")
    elif commitment == "committed_act":
        violations.append("committed_act")
    elif commitment == "agreed_to_share_otp" and not _reports_allowed_code(body, allowed_numbers):
        violations.append("agreed_to_share_otp")
    if _HARMFUL.search(body):
        violations.append("harmful_assistance")
    if _EXPERT.search(body) and "?" not in body:
        violations.append("expert_shutdown")
    violations.extend(voice_issues(body, persona_id))
    from app.agent.textutil import digit_runs

    amounts = _amount_digits(body)
    for number in digit_runs(body):
        if number in amounts:
            continue
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


_AGREE_IN_QUESTION = re.compile(
    r"("
    r"\b(chuyen|chuyển)\s+\d+\s*(trieu|triệu|nghin|nghìn|ngan|ngàn|k)\b"
    r"|\b(chuyen|chuyển)\s+.{0,24}(trieu|triệu)\s+vao\b"
    r"|\b(vua|vừa|da|đã)\s+(tai|tải|cai|cài)\b.{0,48}(ve\s*roi|về\s*rồi|\broi\b|\brồi\b|\bxong\b)"
    r"|\b(tai|tải|cai|cài)\b.{0,32}(ve\s*roi|về\s*rồi)"
    r"|\b(chuyen|chuyển|ck|nap|nạp)\b.{0,40}\b(nhe|nhé|lien|liền|ngay|luon|luôn|roi|rồi|xong)\b"
    r"|\b(ok|oke|okay)\b.{0,24}\b(bank|ck|chuyen|chuyển|nap|nạp)\b"
    r"|\bbank\s+(lun|luon|ngay|lien|liền)\b"
    r"|\b(nap|nạp)\s+\d+"
    r"|dong\s*y\s+(chuyen|chuyển|nap|nạp|cai|cài|tai|tải)"
    r")",
    re.IGNORECASE,
)


def agreement_in_question(text: str) -> str:
    """Retired as an exemption and as a broad matcher.

    "Phí 350k này chuyển cho ai, rồi sau đó…?" is a question. The guard model decides.
    Only a verb-adjacent commitment, from hard_commitment, is a hard block.
    """
    return hard_commitment(text)


def contains_guard_subject(text: str) -> bool:
    """Money, an app, a code, or a completion marker: the guard model must see the draft."""
    folded = fold(text or "")
    if re.search(r"\b(trieu|nghin|ngan|vnd)\b", folded):
        return True
    if re.search(r"(anydesk|ultraviewer|teamviewer)", folded):
        return True
    if re.search(r"\b(otp|ma otp|ma xac)\b", folded):
        return True
    if re.search(r"\b(chuyen|ck|nap|bank|gui tien)\b", folded) and re.search(r"\b(roi|xong|lien|ngay|nhe|ok\b|oke|dong y)\b", folded):
        return True
    return bool(agreement_in_question(text))


def is_extraction_ask(text: str) -> bool:
    """Asking the scammer to send a link, account, or app name is the point of the turn."""
    raw = text or ""
    folded = fold(raw)
    if agreement_in_question(raw) or contains_guard_subject(raw):
        return False
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
    from app.data.personas import PRONOUNS

    spec = PRONOUNS.get(persona_id) or {}
    other = ((spec.get("other") or ["anh"])[0]).lower()
    self_word = ((spec.get("self") or ["em"])[0]).lower()
    return f"Mã {self_word} thấy là {code}. {other[:1].upper()}{other[1:]} lấy mã này để làm gì? {self_word[:1].upper()}{self_word[1:]} chưa xác nhận."


_ADDRESS_WORDS = ("bác", "cháu", "anh", "chị", "cô", "em", "bạn")


def remember_address(text: str, persona_id: str, current: str) -> str:
    """Keep the word this persona uses for the scammer once it has been chosen."""
    if current:
        return current
    from app.data.personas import PRONOUNS

    spec = PRONOUNS.get(persona_id) or {}
    self_words = {word.lower() for word in spec.get("self") or []}
    for word in spec.get("other") or []:
        if word.lower() in self_words:
            continue
        if re.search(rf"\b{re.escape(word)}\b", text or "", re.IGNORECASE):
            return word
    return ""


def pin_address(text: str, persona_id: str, term: str) -> str:
    if not term:
        return text or ""
    from app.data.personas import PRONOUNS

    spec = PRONOUNS.get(persona_id) or {}
    self_words = {word.lower() for word in spec.get("self") or []}
    body = text or ""
    for word in _ADDRESS_WORDS:
        if word.lower() in self_words or word.lower() == term.lower():
            continue
        body = re.sub(rf"\b{re.escape(word)}\b", term, body, flags=re.IGNORECASE)
    return body


def _self_kin_used(text: str, spec: dict) -> list[str]:
    """Kinship words for "I" this persona may use, in the order they appear."""
    kin = [w.lower() for w in spec.get("self") or [] if w.lower() not in {"tôi", "mình", "tui", "em"}]
    if len(kin) < 2:
        return []
    found: list[str] = []
    for match in re.finditer(r"(?<!\w)(" + "|".join(map(re.escape, kin)) + r")(?!\w)", text or "", flags=re.IGNORECASE):
        word = match.group(1).lower()
        if word not in found:
            found.append(word)
    return found


def repair_pronouns(text: str, persona_id: str, self_term: str = "") -> str:
    """Swap a forbidden address word for this persona's own, keep one word for "I",
    and keep the question."""
    from app.data.personas import PRONOUNS

    spec = PRONOUNS.get(persona_id) or {}
    other = (spec.get("other") or ["anh"])[0]
    body = text or ""
    used = _self_kin_used(body, spec)
    if len(used) > 1:
        keep = self_term if self_term in used else used[0]
        for word in used:
            if word == keep:
                continue
            body = re.sub(
                rf"(?<!\w){re.escape(word)}(?!\w)",
                lambda m: keep.capitalize() if m.group(0)[0].isupper() else keep,
                body,
                flags=re.IGNORECASE,
            )
    for word in spec.get("forbid_words") or []:
        if word.lower() in {"tao", "mày", "tụi bây", "chúng mày"}:
            continue
        body = re.sub(rf"\b{re.escape(word)}\b", other, body, flags=re.IGNORECASE)
    return body


# Everyday interruptions, said once each. "Nói lại được không" three times in one
# chat is the loudest tell, so most of these do not ask them to repeat anything.
_HOLD_TEMPLATES = [
    "Đợi {me} xíu, {me} đang bận tay. {You} nói lại được không?",
    "Khoan, {me} nghe không rõ. {You} nói lại một câu thôi.",
    "{You} chờ {me} tí, {me} đi lấy cái kính đã.",
    "Ơ máy {me} vừa đơ, {you} chờ {me} chút.",
    "Có người gọi cửa, {you} đợi {me} tí nhé.",
    "Từ từ đã {you}, {me} đang ghi lại.",
    "Để {me} ngồi xuống đã, nãy giờ {me} đứng ngoài đường.",
]
_HOLD_YOUNG = [
    "đợi {me} xíu, {me} đang bận tay. {you} nói lại được không?",
    "khoan, {me} nghe không rõ. {you} nói lại một câu.",
    "{you} chờ {me} tí, đang dở tay.",
    "máy {me} lag quá, đợi chút",
    "ơ từ từ, {me} đang đọc lại",
]


def _norm_line(text: str) -> str:
    return re.sub(r"[^\w]+", " ", fold(text or "")).strip()


def holding_line(persona_id: str, recent: list[str] | None = None, self_term: str = "") -> str:
    from app.data.personas import PRONOUNS, STYLES

    spec = PRONOUNS.get(persona_id) or {}
    young = (STYLES.get(persona_id) or {}).get("case") == "lower"
    templates = _HOLD_YOUNG if young else _HOLD_TEMPLATES
    options = [_voiced(line, persona_id) for line in templates]
    default_self = (spec.get("self") or [""])[0]
    if self_term and default_self and self_term != default_self:
        options = [
            re.sub(
                rf"(?<!\w){re.escape(default_self)}(?!\w)",
                lambda m: self_term.capitalize() if m.group(0)[0].isupper() else self_term,
                line,
                flags=re.IGNORECASE,
            )
            for line in options
        ]
    seen = {_norm_line(item) for item in (recent or [])}
    fresh = [line for line in options if _norm_line(line) not in seen]
    if not fresh:
        return options[len(recent or []) % len(options)]
    # Rotate through the unused ones so two degraded turns never match.
    return fresh[len(recent or []) % len(fresh)]


def needs_guard(text: str) -> bool:
    """Money, an amount, an app, a code, a long number, or a link: the model guard must see the draft."""
    folded = fold(text or "")
    if _GUARD_TOPIC.search(folded):
        return True
    return bool(re.search(r"https?://|www\.|(?<![\w@])[a-z0-9-]+\.[a-z]{2,24}", text or "", re.IGNORECASE))


# Words that put a draft in the guard model's territory: acting, paying, codes,
# papers, apps, or the bot question. Matched on the text with diacritics, so
# "cái" (a determiner) is not "cài" (install).
_GUARD_ACTION = re.compile(
    r"(?<!\w)(cài|tải|bấm|nhấn|ấn|mở|quét|nhập|điền|đọc|gửi|làm theo|làm đúng|xong|sẵn sàng|chờ lệnh|bảo gì|"
    r"thanh toán|đóng|nộp|trả|chuyển|ck|nạp|rút|xác nhận|xác thực|đăng nhập|mật khẩu|mã|căn cước|cccd|"
    r"địa chỉ|số điện thoại|sđt|ảnh|chụp|video|ứng dụng|app|phần mềm|link|đường dẫn|ví|thẻ|"
    r"máy|bot|người thật|trí tuệ|tiền|phí|khoản|đưa|triệu|nghìn|ngàn|đồng|vnd|otp|stk|tk|tài khoản|ngân hàng|bank|momo|zalopay|viettel ?pay|vnpay|usdt|id|"
    r"anydesk|ultraviewer|teamviewer)(?!\w)",
    re.IGNORECASE,
)
_GUARD_LINK = re.compile(r"https?://|www\.|(?<![\w@])[a-z0-9-]+\.[a-z]{2,24}\b", re.IGNORECASE)
SKIP_GUARD_MAX_CHARS = 120


# Turns where the guard always runs, whatever the wording.
GUARD_ALWAYS_GOALS = {"read_fake_otp", "ask_alternative", "ask_remote_id"}


def guard_skippable(text: str, rule_violations: list[str], allowed_numbers: set[str] | None = None, goal: str = "") -> bool:
    """True only for a short, plain line the rules found clean and that touches nothing risky.

    The guard model costs 3 to 5 seconds a turn. A line like "Ôi, cháu tên gì, ở
    phường nào?" cannot claim a payment, an install or a code, so the model has
    nothing to judge. Anything about money, codes, apps, links, papers, acting on
    instructions, or being a machine still goes to the guard.
    """
    body = (text or "").strip()
    if goal in GUARD_ALWAYS_GOALS:
        return False
    if not body or rule_violations or len(body) > SKIP_GUARD_MAX_CHARS:
        return False
    # Not needs_guard(): it folds diacritics, so "chuyện" (matter) reads as "chuyển" (transfer).
    if _GUARD_ACTION.search(body) or _GUARD_LINK.search(body) or _AI_TOKEN.search(body):
        return False
    from app.agent.textutil import digit_runs

    return all(number in (allowed_numbers or set()) for number in digit_runs(body))


def rewrite_opening(text: str, recent: list[str] | None) -> str:
    """Change a repeated opening and keep the rest, especially a question that asks for an account, link, or app."""
    raw = (text or "").strip()
    if not raw or not repeats_opening(raw, recent):
        return raw
    pieces = re.split(r"(?<=[?.!])\s+", raw, maxsplit=1)
    # Never drop a sentence that carries a long number: it is a read-back of the
    # scammer's own account, the one thing this turn exists to say.
    if len(pieces) == 2 and pieces[1].strip() and not re.search(r"\d{6,}", pieces[0]):
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


_INTERJECTIONS = {"oi", "o", "u", "ui", "ua", "chet", "troi", "the", "a", "ay", "chet that", "chet roi", "troi oi", "the a"}


def _opening(text: str, words: int = 2) -> list[str]:
    return re.sub(r"[^\w\s]", " ", fold(text or "")).split()[:words]


def drop_repeated_interjection(text: str, recent: list[str] | None, reactions: list[str] | None = None) -> str:
    """'Chết thật…', 'Chết thật…', 'Chết thật…': the same exclamation opening reply
    after reply is a tell. Drop it when one of the last two replies opened with it.
    Compared without diacritics, since sent messages may have been typed without them.
    'Dạ' stays: it is register, not a reaction."""
    phrases = sorted({fold(p) for p in (reactions or [])} | _INTERJECTIONS, key=lambda p: -len(p.split()))
    head = " ".join(_opening(text, 3))
    hit = next((p for p in phrases if p != "da" and (head == p or head.startswith(p + " "))), None)
    if hit is None:
        return text
    size = len(hit.split())
    if not any(_opening(old, size) == hit.split() for old in (recent or [])[-2:]):
        return text
    rest = re.sub(r"^\s*" + r"[\s,.!…]*".join([r"[^\W\d_]+"] * size) + r"[\s,.!…]*", "", text, count=1)
    if len(rest) < 4:
        return text
    return rest[0].upper() + rest[1:]


def _trigrams(text: str) -> set[tuple[str, ...]]:
    words = fold(re.sub(r"[^\w\s]", " ", text or "")).split()
    return {tuple(words[index : index + 3]) for index in range(len(words) - 2)}


def reply_novelty(text: str, recent: list[str] | None) -> float:
    """Share of this reply's word trigrams not already used in the last few replies.

    Repetitive, template-like asks are what scammers learn to spot; a reply that
    mostly repeats earlier ones also adds nothing to the case.
    """
    mine = _trigrams(text)
    if not mine:
        return 1.0
    seen: set[tuple[str, ...]] = set()
    for old in (recent or [])[-4:]:
        seen |= _trigrams(old)
    if not seen:
        return 1.0
    return round(len(mine - seen) / len(mine), 3)


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


_GENERIC_FALLBACKS = [
    "Khoan, {me} chưa hiểu. {You} nói lại từ đầu được không?",
    "{Me} chưa làm gì. Rồi sao nữa?",
    "{You} là ai vậy, {me} đang nghe.",
]


def _pair(persona_slug: str) -> tuple[str, str]:
    from app.data.personas import PRONOUNS

    pair = PRONOUNS.get(persona_slug) or PRONOUNS["tuan-vp"]
    return (pair.get("self") or ["em"])[0], (pair.get("other") or ["anh"])[0]


def _voiced(template: str, persona_slug: str) -> str:
    me, you = _pair(persona_slug)
    return template.format(me=me, Me=me.capitalize(), you=you, You=you.capitalize())


def fallback_reply(persona_slug: str, recent: list[str] | None = None) -> str:
    # A persona without hand-written lines gets generic ones in its own pronouns,
    # not another persona's: borrowing "em/anh" made a 72-year-old call himself "cháu".
    options = _FALLBACKS.get(persona_slug) or [_voiced(line, persona_slug) for line in _GENERIC_FALLBACKS]
    # Sent messages are stored as typed (maybe without diacritics), so compare folded.
    recent_norm = {_norm_line(item) for item in (recent or [])}
    for line in options:
        if _norm_line(line) in recent_norm or repeats_opening(line, recent):
            continue
        return line
    return options[len(recent or []) % len(options)]


def readback_line(persona_slug: str, account: str, kind: str = "bank_accounts") -> str:
    """A plain in-voice read-back, for when the drafted one had to be replaced."""
    if kind == "bank_accounts":
        line = "{Me} ghi lại là số ACCOUNT, đúng chưa {you}? Ai đứng tên số này, ngân hàng nào? {Me} chưa chuyển đâu."
    else:
        # A wallet has an owner, not a bank.
        line = "{Me} ghi lại là ví ACCOUNT, đúng chưa {you}? Ví này đứng tên ai? {Me} chưa chuyển đâu."
    return _voiced(line, persona_slug).replace("ACCOUNT", account)


def alternative_line(persona_slug: str, same_bank: bool = False) -> str:
    """A harmless obstacle plus a request for another way to pay. Claims nothing was tried.

    When the scammer's bank is the persona's own, "I don't use that bank" would
    contradict the profile, so the obstacle is not knowing how to transfer.
    """
    if same_bank:
        line = "{Me} không rành chuyển khoản trên điện thoại, phải nhờ người nhà làm hộ. {You} có cách nào khác không, ví hay số khác?"
    else:
        line = "{Me} không dùng ngân hàng đó, cũng không rành chuyển khoản. {You} còn số nào khác hay người nhận khác không?"
    return _voiced(line, persona_slug)


def denial_line(persona_slug: str) -> str:
    """Answer "are you a bot?" the way a confused person would, instead of ignoring it."""
    return _voiced("Máy gì cơ, {me} là người chứ máy gì. {You} nói gì {me} chẳng hiểu.", persona_slug)


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
