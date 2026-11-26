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
    "apk", "html", "php", "jpg", "jpeg", "png", "pdf", "doc", "txt", "js", "css", "json",
}
_BANK_CUE = re.compile(
    r"(số tài khoản|số tk|\bstk\b|ngân hàng|\bbank\b|"
    r"vietcombank|techcombank|bidv|agribank|vpbank|\bacb\b|tpbank|sacombank|vietinbank|"
    r"\bmb\s*bank\b|mbbank|\bmsb\b|hdbank|\bocb\b|\bshb\b)",
    re.IGNORECASE,
)
_CUE = re.compile(r"(?:tôi thấy|tôi biết|chúng tôi biết|bên tôi thấy)\s+([^.]{8,90})", re.IGNORECASE)
_APPS = (
    "ultraviewer", "anydesk", "teamviewer", "rustdesk", "airdroid", "zalo", "telegram", "vneid", "momo",
    "vssid", "etax", "dịch vụ công", "dichvucong", "evn cskh", "evncskh", "sms forwarder",
)
_TECHNIQUES = (
    ("hỗ trợ truy cập", "Bật quyền Hỗ trợ truy cập"),
    ("ho tro truy cap", "Bật quyền Hỗ trợ truy cập"),
    ("trợ năng", "Bật quyền trợ năng"),
    ("accessibility", "Bật quyền Hỗ trợ truy cập"),
    ("quét khuôn mặt", "Đòi quét khuôn mặt"),
    ("sinh trắc học", "Nhắc sinh trắc học"),
    ("chia sẻ màn hình", "Đòi chia sẻ màn hình"),
    ("nguồn không xác định", "Cài từ nguồn không xác định"),
)
_APK = re.compile(r"(?:https?://)?[^\s]*?[\w.-]+\.apk\b(?:\?[^\s]*)?", re.IGNORECASE)
_TELEGRAM = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/(?:joinchat/|\+)?[A-Za-z0-9_+-]{3,64}|(?<![\w.])@[A-Za-z][A-Za-z0-9_]{4,31}\b", re.IGNORECASE)
_ZALO = re.compile(r"(?:https?://)?zalo\.me/(?:g/)?[A-Za-z0-9_-]{3,64}", re.IGNORECASE)
_EWALLET = re.compile(
    r"(?:ví\s*)?(momo|zalopay|viettel\s*pay|vnpay)\s*(?:số)?\s*((?:\+84|0)[35789]\d{8})",
    re.IGNORECASE,
)
_TRON = re.compile(r"(?<![A-Za-z0-9])T[1-9A-HJ-NP-Za-km-z]{33}(?![A-Za-z0-9])")
_ETH = re.compile(r"(?<![A-Za-z0-9])0x[a-fA-F0-9]{40}(?![A-Za-z0-9])")
_BTC_BECH32 = re.compile(r"(?<![A-Za-z0-9])bc1[ac-hj-np-z02-9]{25,62}(?![A-Za-z0-9])")
_BTC_BASE58 = re.compile(r"(?<![A-Za-z0-9])[13][1-9A-HJ-NP-Za-km-z]{25,33}(?![A-Za-z0-9])")
_WALLET_CUE = re.compile(r"(?:ví|vi|wallet|địa chỉ ví|dia chi vi)\s*(?:usdt|trc20|erc20|bep20)?\s*[:：]?\s*([A-Za-z0-9]{20,64})", re.IGNORECASE)
_REMOTE_ID = re.compile(r"(ultraviewer|anydesk|teamviewer|rustdesk)[^\d]{0,30}?((?:\d[\s-]?){8,11}\d)", re.IGNORECASE)
_B58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
OFFICIAL_DOMAINS = (
    "gov.vn", "vietcombank.com.vn", "techcombank.com.vn", "techcombank.com", "bidv.com.vn", "agribank.com.vn", "vpbank.com.vn",
    "mbbank.com.vn", "momo.vn", "evn.com.vn", "evnspc.vn", "evnhanoi.vn", "napas.com.vn", "viettel.vn", "vinaphone.com.vn",
    "mobifone.vn", "vnpost.vn", "shopee.vn", "zalo.me", "t.me", "ssi.com.vn", "baohiemxahoi.gov.vn", "vneid.gov.vn", "moet.gov.vn",
)
BRAND_TOKENS = (
    "vcb", "vietcombank", "techcombank", "tcb", "bidv", "agribank", "vpbank", "mbbank", "momo", "evn", "napas", "viettel",
    "vnpost", "shopee", "vneid", "bocongan", "bca", "congan", "dichvucong", "dvc", "vssid", "bhxh", "thue", "ssi", "sinhtrachoc",
)
SUSPECT_TLDS = ("top", "vip", "xyz", "cc", "icu", "shop", "online", "site", "club", "live", "info", "io", "app", "click", "link", "buzz", "cyou", "sbs")
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
    ("napas", "NAPAS"),
    ("vssid", "BHXH"),
    ("bưu điện", "Bưu điện"),
    ("vnpost", "Bưu điện"),
    ("techcombank", "Techcombank"),
    ("điện lực", "EVN"),
    ("nhà mạng", "Nhà mạng"),
    ("telegram", "Telegram"),
)
_PRESSURE = (
    ("15 phút", "Giục trong vài phút"),
    ("ngay lập tức", "Đòi làm ngay"),
    ("đồng phạm", "Dọa đồng phạm"),
    ("không được kể", "Cấm nói với người thân"),
    ("bị bắt", "Dọa bắt"),
    ("khóa tài khoản", "Dọa khóa tài khoản"),
    ("phong tỏa", "Dọa phong tỏa"),
    ("khóa 2 chiều", "Dọa khóa thuê bao"),
    ("khóa hai chiều", "Dọa khóa thuê bao"),
    ("cắt điện", "Dọa cắt điện"),
    ("trong hôm nay", "Hạn chót trong ngày"),
    ("đừng gọi cho ai", "Cấm nói với người thân"),
    ("đừng nói với ai", "Cấm nói với người thân"),
    ("2 giờ", "Hạn chót tính bằng giờ"),
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
    return {
        "phones": [], "bank_accounts": [], "urls": [], "apps": [], "brands": [], "pressure": [], "hotlines": [],
        "apk": [], "telegram": [], "zalo": [], "crypto_wallets": [], "ewallets": [], "remote_ids": [], "techniques": [], "lookalikes": [],
    }


def _host(url: str) -> str:
    text = re.sub(r"^[a-z]+://", "", (url or "").lower())
    return text.split("/", 1)[0].split("?", 1)[0]


def lookalike_reason(url: str) -> str:
    """Why a domain looks like it borrows a brand. Empty when it is official or carries no brand word."""
    host = _host(url)
    if not host or "." not in host:
        return ""
    if any(host == dom or host.endswith("." + dom) for dom in OFFICIAL_DOMAINS):
        return ""
    label = host.rsplit(".", 1)[0]
    tld = host.rsplit(".", 1)[-1]
    flat = re.sub(r"[^a-z0-9]", "", label)
    brand = next((tok for tok in BRAND_TOKENS if tok in flat), "")
    if brand:
        return f"Tên miền mượn chữ «{brand}» nhưng không phải trang chính thức"
    if tld in SUSPECT_TLDS and "-" in label:
        return f"Tên miền đuôi .{tld} ghép gạch nối, hay gặp ở trang lừa"
    return ""


def valid_crypto_wallet(value: str) -> bool:
    """TRC20 is T plus 33 base58 chars. ERC20 is 0x plus 40 hex. BTC is bech32 or a 26–35 char base58 address."""
    text = (value or "").strip()
    if re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", text):
        return all(ch in _B58 for ch in text)
    if re.fullmatch(r"0x[a-fA-F0-9]{40}", text):
        return True
    if text.lower().startswith("bc1"):
        rest = text[3:].lower()
        return 25 <= len(rest) <= 62 and all(ch in "023456789acdefghjklmnpqrstuvwxyz" for ch in rest)
    if text[:1] in {"1", "3"} and 26 <= len(text) <= 35 and all(ch in _B58 for ch in text):
        return True
    return False


def normalize_indicator(kind: str, value: str) -> str:
    text = " ".join(str(value or "").split()).strip(".,);]")
    if kind in {"phones", "bank_accounts", "hotlines"}:
        return re.sub(r"\D", "", text)
    if kind == "apps":
        return text.casefold()
    if kind in {"urls", "apk", "zalo"}:
        return text.lower().rstrip("/")
    if kind == "telegram":
        return re.sub(r"^https?://", "", text.lower()).rstrip("/")
    if kind == "remote_ids":
        return re.sub(r"\D", "", text)
    return text[:120]


def _add(bucket: list[str], value: str, kind: str = "") -> None:
    cleaned = normalize_indicator(kind, value) if kind else " ".join(str(value or "").split())
    if not cleaned:
        return
    key = fold(cleaned) if kind == "apps" else cleaned
    existing = {fold(item) if kind == "apps" else item for item in bucket}
    if key not in existing:
        bucket.append(cleaned[:120])


_STRONG_ACCOUNT = re.compile(r"(số tài khoản|số tk|\bstk\b)", re.IGNORECASE)
_OTP_BEFORE = re.compile(r"(otp|mã\s*xác\s*thực|mã\s*otp|\bcode)\s*$", re.IGNORECASE)


def _near_bank(body: str, start: int, end: int) -> bool:
    window = body[max(0, start - 40) : min(len(body), end + 24)]
    return bool(_BANK_CUE.search(window))


def _strong_account(body: str, start: int, end: int) -> bool:
    window = body[max(0, start - 40) : min(len(body), end + 24)]
    return bool(_STRONG_ACCOUNT.search(window))


def _otp_number(body: str, start: int) -> bool:
    return bool(_OTP_BEFORE.search(body[max(0, start - 28) : start]))


def _inside_lettered_token(body: str, start: int, end: int) -> bool:
    """Digits inside an alphanumeric wallet-like token are not a bank account."""
    left = start
    while left > 0 and body[left - 1].isalnum():
        left -= 1
    right = end
    while right < len(body) and body[right].isalnum():
        right += 1
    token = body[left:right]
    return any(ch.isalpha() for ch in token)


_PHONE_CTX = re.compile(
    r"(số điện thoại|số đt|\bsđt\b|\bsdt\b|điện thoại|dien thoai|phone|gọi cho|goi cho)",
    re.IGNORECASE,
)


def _mobile_number(digits: str) -> bool:
    """Vietnamese mobile: 0[35789] plus 8 digits, or 84 in front of the same."""
    number = digits[2:] if digits.startswith("84") and len(digits) == 11 else digits
    return bool(re.fullmatch(r"0[35789]\d{8}", number))


def _phone_context(body: str, start: int, end: int) -> bool:
    window = body[max(0, start - 40) : min(len(body), end + 12)]
    return bool(_PHONE_CTX.search(window))


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
        if _mobile_number(digits) and _phone_context(body, match.start(), match.end()) and not _strong_account(body, match.start(), match.end()):
            _add(found["phones"], digits, "phones")
            continue
        if _near_bank(body, match.start(), match.end()) and not (
            _mobile_number(digits) and _phone_context(body, match.start(), match.end())
        ):
            _add(found["bank_accounts"], digits, "bank_accounts")
            continue
        _add(found["phones"], digits, "phones")
    for match in _EWALLET.finditer(body):
        wallet = match.group(1).lower().replace(" ", "")
        number = match.group(2)
        _add(found["ewallets"], f"{wallet}:{number}")
        _add(found["phones"], number, "phones")
    for match in re.finditer(r"\d[\d\s.]{4,}\d", body):
        digits = re.sub(r"\D", "", match.group(0))
        if _inside_lettered_token(body, match.start(), match.end()) or _otp_number(body, match.start()):
            continue
        if _hotline(digits):
            _add(found["hotlines"], digits, "hotlines")
            _add(found["phones"], digits, "phones")
            continue
        strong = _strong_account(body, match.start(), match.end())
        if _mobile_number(digits) and _phone_context(body, match.start(), match.end()) and not strong:
            _add(found["phones"], digits, "phones")
            continue
        if strong and 6 <= len(digits) <= 19:
            _add(found["bank_accounts"], digits, "bank_accounts")
            continue
        if len(digits) < 8:
            continue
        if _near_bank(body, match.start(), match.end()) and len(digits) <= 19:
            _add(found["bank_accounts"], digits, "bank_accounts")
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
    for match in _APK.finditer(body):
        _add(found["apk"], match.group(0), "apk")
    for match in _TELEGRAM.finditer(body):
        raw = match.group(0)
        if raw.startswith("@") and "telegram" not in body.lower() and "tele" not in body.lower():
            continue
        _add(found["telegram"], raw, "telegram")
    for match in _ZALO.finditer(body):
        _add(found["zalo"], match.group(0), "zalo")
    for rx in (_TRON, _ETH, _BTC_BECH32, _BTC_BASE58):
        for match in rx.finditer(body):
            if valid_crypto_wallet(match.group(0)):
                _add(found["crypto_wallets"], match.group(0))
    for match in _WALLET_CUE.finditer(body):
        value = match.group(1)
        if valid_crypto_wallet(value) and value not in found["crypto_wallets"]:
            _add(found["crypto_wallets"], value)
    if found["crypto_wallets"]:
        joined = " ".join(found["crypto_wallets"])
        found["bank_accounts"] = [item for item in found["bank_accounts"] if item not in joined]
        found["phones"] = [item for item in found["phones"] if item not in joined]
    for match in _REMOTE_ID.finditer(body):
        digits = re.sub(r"\D", "", match.group(2))
        _add(found["remote_ids"], digits, "remote_ids")
        found["phones"] = [item for item in found["phones"] if item != digits]
        found["bank_accounts"] = [item for item in found["bank_accounts"] if item != digits]
    found["urls"] = [url for url in found["urls"] if not re.match(r"^(?:https?://)?(?:t\.me|telegram\.me|zalo\.me)/", url)]
    for url in found["urls"] + [item for item in found["apk"] if "/" in item]:
        reason = lookalike_reason(url)
        if reason:
            _add(found["lookalikes"], f"{_host(url)} — {reason}")
    lowered = body.lower()
    for needle, label in _TECHNIQUES:
        if needle in lowered:
            _add(found["techniques"], label)
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
    if harvested["apps"] or harvested["apk"] or harvested["remote_ids"]:
        by_key["app"]["done"] = True
        by_key["app"]["detail"] = ", ".join(harvested["apk"][-1:] + harvested["apps"] + harvested["remote_ids"][-1:])
    if harvested["crypto_wallets"]:
        by_key["account"]["done"] = True
        by_key["account"]["detail"] = harvested["crypto_wallets"][-1]
    if (harvested["telegram"] or harvested["zalo"] or harvested["apk"]) and not by_key["link"]["done"]:
        by_key["link"]["done"] = True
        by_key["link"]["detail"] = (harvested["telegram"] + harvested["zalo"] + harvested["apk"])[-1]
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
