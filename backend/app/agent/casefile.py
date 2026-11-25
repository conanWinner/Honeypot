"""Scam-stage memory, extraction checklist, and indicators of compromise.

These are deterministic so a small chat model can stay fast. The planner reads the
open checklist; the end-of-conversation extractor merges the indicators the
regex already pulled out of the scammer's words.
"""

import re

from app.agent.policy import inspect_outbound, repeats_opening
from app.agent.state import AgentState
from app.agent.textutil import fold

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
_DOMAIN = re.compile(
    r"(?<![\w@])((?:[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\.)+([a-z]{2,24}))(?:/[^\s]*)?",
    re.IGNORECASE,
)
# Syllables that show up after a dot in ordinary Vietnamese, not as a public suffix.
_NOT_TLD = {
    "anh", "chi", "em", "oi", "nhe", "nha", "nay", "mai", "sao", "dau", "gi",
    "html", "php", "jpg", "jpeg", "png", "pdf", "doc", "txt", "js", "css", "json",
}
_BANK_CUE = re.compile(
    r"(số tài khoản|số tk|\bstk\b|ngân hàng|\bbank\b|"
    r"vietcombank|techcombank|bidv|agribank|vpbank|\bacb\b|tpbank|sacombank|vietinbank|"
    r"\bmb\s*bank\b|mbbank|\bmsb\b|hdbank|\bocb\b|\bshb\b)",
    re.IGNORECASE,
)
_CUE = re.compile(r"(?:tôi thấy|tôi biết|chúng tôi biết|bên tôi thấy)\s+([^.]{8,90})", re.IGNORECASE)
_APPS = ("ultraviewer", "anydesk", "teamviewer", "zalo", "telegram", "vneid", "momo")
_BRANDS = (
    ("công an", "Công an"),
    ("cong an", "Công an"),
    ("cảnh sát", "Công an"),
    ("vietcombank", "Vietcombank"),
    ("techcombank", "Techcombank"),
    ("bidv", "BIDV"),
    ("mb bank", "MB Bank"),
    ("mbbank", "MB Bank"),
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
    return {"phones": [], "bank_accounts": [], "urls": [], "apps": [], "brands": [], "pressure": [], "hotlines": []}


def normalize_indicator(kind: str, value: str) -> str:
    text = " ".join(str(value or "").split()).strip(".,);]")
    if kind in {"phones", "bank_accounts", "hotlines"}:
        return re.sub(r"\D", "", text)
    if kind == "apps":
        return text.casefold()
    if kind == "urls":
        return text.lower().rstrip("/")
    return text[:120]


def _add(bucket: list[str], value: str, kind: str = "") -> None:
    cleaned = normalize_indicator(kind, value) if kind else " ".join(str(value or "").split())
    if not cleaned:
        return
    key = fold(cleaned) if kind == "apps" else cleaned
    existing = {fold(item) if kind == "apps" else item for item in bucket}
    if key not in existing:
        bucket.append(cleaned[:120])


def _near_bank(body: str, start: int, end: int) -> bool:
    window = body[max(0, start - 40) : min(len(body), end + 24)]
    return bool(_BANK_CUE.search(window))


def _hotline(digits: str) -> bool:
    return bool(re.fullmatch(r"1[89]00\d{4,8}", digits))


def _remember_url(found: dict, raw: str) -> None:
    _add(found["urls"], raw, "urls")


def harvest_indicators(text: str) -> dict:
    found = empty_indicators()
    body = text or ""
    for match in _PHONE.finditer(body):
        if match.start() > 0 and body[match.start() - 1].isdigit():
            continue
        if match.end() < len(body) and body[match.end()].isdigit():
            continue
        digits = re.sub(r"\D", "", match.group(0))
        if not (9 <= len(digits) <= 12):
            continue
        if _near_bank(body, match.start(), match.end()):
            _add(found["bank_accounts"], digits, "bank_accounts")
            continue
        _add(found["phones"], digits, "phones")
    for match in re.finditer(r"\d[\d\s.]{4,}\d", body):
        digits = re.sub(r"\D", "", match.group(0))
        if _hotline(digits):
            _add(found["hotlines"], digits, "hotlines")
            _add(found["phones"], digits, "phones")
            continue
        if _near_bank(body, match.start(), match.end()) and 6 <= len(digits) <= 19:
            _add(found["bank_accounts"], digits, "bank_accounts")
            continue
        if len(digits) < 10:
            continue
        phone_shaped = digits.startswith("0") and len(digits) <= 11
        if phone_shaped:
            continue
        if len(digits) <= 19:
            _add(found["bank_accounts"], digits, "bank_accounts")
    for match in _URL.findall(body):
        _remember_url(found, match)
    for match in _DOMAIN.finditer(body):
        tld = match.group(2).lower()
        label = match.group(1).split(".")[-2]
        if tld in _NOT_TLD or len(label) < 2:
            continue
        _remember_url(found, match.group(0))
    lowered = body.lower()
    for app in _APPS:
        if app in lowered:
            _add(found["apps"], app, "apps")
    for needle, label in _BRANDS:
        if needle in lowered:
            _add(found["brands"], label, "brands")
    for needle, label in _PRESSURE:
        if needle in lowered:
            _add(found["pressure"], label, "pressure")
    who = _WHO.search(body)
    if who:
        found["who"] = who.group(0)[:80]
    return found


def merge_indicators(base: dict | None, extra: dict) -> dict:
    merged = empty_indicators()
    source = base or {}
    for key in merged:
        for item in list(source.get(key) or []) + list(extra.get(key) or []):
            _add(merged[key], str(item), key)
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


def checklist_signature(state: AgentState) -> tuple:
    if not state.checklist:
        return tuple()
    return tuple((item["key"], bool(item["done"]), item.get("detail") or "") for item in state.checklist)


def note_progress(state: AgentState, before: tuple) -> None:
    """Count turns that added nothing to the checklist. Turn 0 never counts as stale."""
    after = checklist_signature(state)
    if state.turn_index > 0 and before == after:
        state.stale_turns += 1
    else:
        state.stale_turns = 0


def priority_gap(state: AgentState) -> str:
    """The next fact worth asking for once the chat has stopped producing new ones."""
    ensure_checklist(state)
    by_key = {item["key"]: item for item in state.checklist}
    for key in ("account", "link", "app", "payment"):
        if key in by_key and not by_key[key]["done"]:
            return key
    return ""


def forced_ask(state: AgentState, suspicion: float, jailbreak: bool, branch_kind: str) -> str:
    """After two quiet turns, ask for the top missing checklist item. Stall only on real suspicion."""
    if jailbreak or suspicion >= 0.7 or branch_kind == "new":
        return ""
    if state.stale_turns < 2:
        return ""
    return GAP_GOAL.get(priority_gap(state), "")


def stabilize_family(state: AgentState, family_id: str) -> str:
    """Stay on the current script family until another one wins two turns in a row."""
    family_id = family_id or ""
    current = state.stable_family or ""
    if not family_id:
        return current
    if not current or family_id == current:
        state.stable_family = family_id
        state.pending_family = ""
        state.pending_family_hits = 0
        return family_id
    if state.pending_family == family_id:
        state.pending_family_hits += 1
    else:
        state.pending_family = family_id
        state.pending_family_hits = 1
    if state.pending_family_hits >= 2:
        state.stable_family = family_id
        state.pending_family = ""
        state.pending_family_hits = 0
        return family_id
    return current


def stabilize_branch(state: AgentState, kind: str, variant_id: str = "") -> tuple[str, str]:
    """Keep the branch label until a different one wins two turns in a row.

    The first real label is shown immediately. A one-turn flicker back to none,
    or from a known variant to new, does not change what the cockpit shows.
    """
    kind = kind or "none"
    current = state.stable_branch or "none"
    if current == "none" or kind == current:
        state.stable_branch = kind
        if kind == "known_variant":
            state.stable_variant = variant_id or state.stable_variant
        elif kind == "none":
            state.stable_variant = ""
        state.pending_branch = ""
        state.pending_branch_hits = 0
        return state.stable_branch, state.stable_variant or ""
    if state.pending_branch == kind:
        state.pending_branch_hits += 1
    else:
        state.pending_branch = kind
        state.pending_branch_hits = 1
    if state.pending_branch_hits >= 2:
        state.stable_branch = kind
        state.stable_variant = variant_id if kind == "known_variant" else ""
        state.pending_branch = ""
        state.pending_branch_hits = 0
        return kind, state.stable_variant
    return current, state.stable_variant or ""


def clamp_new_branch(kind: str, detected: bool, turn_index: int) -> tuple[str, bool]:
    """A first or second turn is not a new branch. The opening line always looks 'new'."""
    if kind == "new" and turn_index < 2:
        return "none", False
    return kind, detected


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


def critique_reply(
    text: str,
    persona_id: str,
    goal: str,
    allowed: set[str],
    aggressiveness: str,
    recent: list[str] | None = None,
) -> list[str]:
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
    if repeats_opening(text or "", recent):
        notes.append("Đừng mở đầu giống câu vừa rồi. Hỏi một chi tiết mới, đừng lặp 'cháu là ai'.")
    return notes
