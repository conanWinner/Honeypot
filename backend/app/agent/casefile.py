"""Scam-stage memory, extraction checklist, and indicators of compromise.

These are deterministic so a small chat model can stay fast. The planner reads the
open checklist; the end-of-conversation extractor merges the indicators the
regex already pulled out of the scammer's words.
"""

import re

from app.agent.policy import inspect_outbound
from app.agent.state import AgentState

STAGES: list[tuple[str, str]] = [
    ("mo_dau", "Mở đầu"),
    ("danh_tinh", "Họ tự xưng"),
    ("ly_do", "Lý do gọi"),
    ("co_lap", "Cô lập"),
    ("tien", "Đòi tiền"),
    ("kenh_nhan", "Kênh nhận"),
    ("ep", "Gây sức ép"),
    ("nhanh", "Nhánh mới"),
    ("phuc_hoi", "Họ đang nghi"),
    ("kep", "Có thể khép"),
]

STAGE_LABELS = dict(STAGES)

CHECKLIST = [
    ("who", "Họ tự xưng là ai"),
    ("channel", "Kênh và lý do liên hệ"),
    ("payment", "Họ muốn nạn nhân trả gì"),
    ("account", "Số tài khoản hoặc ví"),
    ("link", "Đường dẫn"),
    ("app", "Ứng dụng hoặc phần mềm"),
    ("pressure", "Cách gây sức ép"),
    ("brand", "Thương hiệu bị mạo danh"),
]

_PHONE = re.compile(r"(?:\+84|0)(?:\d[\s.]?){8,10}\d")
_URL = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)
_CUE = re.compile(r"(?:tôi thấy|tôi biết|chúng tôi biết|bên tôi thấy)\s+([^.]{8,90})", re.IGNORECASE)
_APPS = ("ultraviewer", "anydesk", "teamviewer", "zalo", "telegram", "vneid", "momo")
_BRANDS = (
    ("công an", "Công an"),
    ("cong an", "Công an"),
    ("cảnh sát", "Công an"),
    ("vietcombank", "Vietcombank"),
    ("techcombank", "Techcombank"),
    ("bidv", "BIDV"),
    ("momo", "MoMo"),
    ("viettel", "Viettel"),
    ("shopee", "Shopee"),
    ("evn", "EVN"),
    ("bhxh", "BHXH"),
    ("vneid", "VNeID"),
)
_PRESSURE = (
    ("15 phút", "Giục trong vài phút"),
    ("ngay lập tức", "Đòi làm ngay"),
    ("đồng phạm", "Dọa đồng phạm"),
    ("không được kể", "Cấm nói với người thân"),
    ("bị bắt", "Dọa bắt"),
    ("khóa tài khoản", "Dọa khóa tài khoản"),
    ("phong tỏa", "Dọa phong tỏa"),
)
_WHO = re.compile(
    r"(thiếu tá|trung tá|cán bộ|nhân viên|tôi là [^.]{0,40}(?:công an|ngân hàng|viettel|momo|shopee|bảo hiểm))",
    re.IGNORECASE,
)

GAP_GOAL = {
    "who": "ask_identity",
    "channel": "ask_purpose",
    "payment": "ask_purpose",
    "account": "ask_account_number",
    "link": "ask_link",
    "app": "ask_next_instruction",
    "pressure": "emotional_hook",
    "brand": "ask_identity",
}


def empty_checklist() -> list[dict]:
    return [{"key": key, "label": label, "done": False, "detail": ""} for key, label in CHECKLIST]


def empty_indicators() -> dict:
    return {"phones": [], "bank_accounts": [], "urls": [], "apps": [], "brands": [], "pressure": []}


def _add(bucket: list[str], value: str) -> None:
    cleaned = " ".join(value.split())
    if cleaned and cleaned not in bucket:
        bucket.append(cleaned[:120])


def harvest_indicators(text: str) -> dict:
    found = empty_indicators()
    body = text or ""
    for match in _PHONE.findall(body):
        digits = re.sub(r"\D", "", match)
        if 9 <= len(digits) <= 12:
            _add(found["phones"], digits)
    for match in re.findall(r"\d[\d\s.]{8,}\d", body):
        digits = re.sub(r"\D", "", match)
        if len(digits) >= 10 and not (digits.startswith("0") and len(digits) <= 11):
            _add(found["bank_accounts"], digits)
    for match in _URL.findall(body):
        _add(found["urls"], match.strip(".,)"))
    lowered = body.lower()
    for app in _APPS:
        if app in lowered:
            _add(found["apps"], app)
    for needle, label in _BRANDS:
        if needle in lowered:
            _add(found["brands"], label)
    for needle, label in _PRESSURE:
        if needle in lowered:
            _add(found["pressure"], label)
    who = _WHO.search(body)
    if who:
        found["who"] = who.group(0)[:80]
    return found


def merge_indicators(base: dict | None, extra: dict) -> dict:
    merged = empty_indicators()
    source = base or {}
    for key in merged:
        for item in list(source.get(key) or []) + list(extra.get(key) or []):
            _add(merged[key], str(item))
    return merged


def ensure_checklist(state: AgentState) -> None:
    if not state.checklist:
        state.checklist = empty_checklist()


def update_casefile(state: AgentState, message: str) -> None:
    ensure_checklist(state)
    if not state.indicators:
        state.indicators = empty_indicators()
    harvested = harvest_indicators(message)
    state.indicators = merge_indicators(state.indicators, harvested)
    by_key = {item["key"]: item for item in state.checklist}
    if harvested.get("who"):
        by_key["who"]["done"] = True
        by_key["who"]["detail"] = harvested["who"]
    if harvested["phones"] or "zalo" in message.lower() or "điện thoại" in message.lower():
        by_key["channel"]["done"] = True
        by_key["channel"]["detail"] = harvested["phones"][0] if harvested["phones"] else "điện thoại hoặc tin nhắn"
    if any(word in message.lower() for word in ("chuyển", "phí", "otp", "nạp", "đóng")):
        by_key["payment"]["done"] = True
        by_key["payment"]["detail"] = "Họ đang đòi một thao tác với tiền hoặc mã"
    if harvested["bank_accounts"]:
        by_key["account"]["done"] = True
        by_key["account"]["detail"] = harvested["bank_accounts"][-1]
    if harvested["urls"]:
        by_key["link"]["done"] = True
        by_key["link"]["detail"] = harvested["urls"][-1]
    if harvested["apps"]:
        by_key["app"]["done"] = True
        by_key["app"]["detail"] = ", ".join(harvested["apps"])
    if harvested["pressure"]:
        by_key["pressure"]["done"] = True
        by_key["pressure"]["detail"] = harvested["pressure"][-1]
    if harvested["brands"]:
        by_key["brand"]["done"] = True
        by_key["brand"]["detail"] = harvested["brands"][-1]
    state.checklist = [by_key[key] for key, _label in CHECKLIST]


def next_gap(state: AgentState) -> str:
    ensure_checklist(state)
    for item in state.checklist:
        if not item["done"]:
            return item["key"]
    return ""


def cue_branch(message: str, known_text: str) -> dict | None:
    match = _CUE.search(message or "")
    if not match:
        return None
    snippet = " ".join(match.group(1).split())
    if snippet.lower() in (known_text or "").lower():
        return None
    return {
        "detected": True,
        "kind": "new",
        "hook": snippet[:80],
        "description": f"Họ vừa nhắc một hoàn cảnh chưa có trong kịch bản đang khớp: {snippet[:80]}",
        "variant_script_id": "",
    }


def choose_stage(state: AgentState, branch_kind: str, wrap: bool, suspicion: float) -> str:
    if suspicion >= 0.7:
        return "phuc_hoi"
    if branch_kind == "new":
        return "nhanh"
    if wrap:
        return "kep"
    ensure_checklist(state)
    done = {item["key"] for item in state.checklist if item["done"]}
    if "pressure" in done and "account" in done:
        return "ep"
    if "account" in done or "link" in done or "app" in done:
        return "kenh_nhan"
    if "payment" in done:
        return "tien"
    if "pressure" in done:
        return "co_lap"
    if "who" in done:
        return "danh_tinh"
    if state.turn_index > 0:
        return "ly_do"
    return "mo_dau"


def critique_reply(text: str, persona_id: str, goal: str, allowed: set[str], aggressiveness: str) -> list[str]:
    """Notes for one rewrite. Empty means the line can go to the safety gate as-is."""
    issues = inspect_outbound(text or "", allowed, persona_id)
    notes: list[str] = []
    if "agreed_to_pay" in issues:
        notes.append("Đừng nhận trả hay chuyển. Hỏi tiền đi đâu và nói bạn chưa chuyển.")
    if "agreed_to_install" in issues:
        notes.append("Đừng nhận đã cài ứng dụng. Hỏi họ muốn cài để làm gì.")
    if "ai_admission" in issues:
        notes.append("Đừng nhận là máy. Hỏi lại họ là ai, như người thật đang bối rối.")
    if "expert_shutdown" in issues:
        notes.append("Đừng dạy họ cách làm đúng và đừng kết luận là lừa đảo. Hỏi một chi tiết để họ nói tiếp.")
    if "pronoun_mix" in issues or "rude_register" in issues:
        notes.append("Giữ đúng cặp đại từ của hồ sơ, lịch sự, không tao/mày.")
    if aggressiveness == "persistent" and goal.startswith("ask_") and "?" not in (text or "") and not notes:
        notes.append("Kết bằng một câu hỏi để họ phải nói bước tiếp theo.")
    return notes
