"""Explainable risk score.

Deterministic weights over surface cues and harvested indicators, so the panel can say
*why* a message is risky without another model call. The score explains; the checker's
verdict logic still decides, and only uses the score to promote clear cases.
"""

from __future__ import annotations

import re

from app.agent.casefile import harvest_indicators
from app.agent.textutil import fold

_AUTHORITY = (
    "cong an", "canh sat", "dieu tra", "vien kiem sat", "toa an", "can bo", "nhan vien ngan hang", "dien luc",
    "nha mang", "tong dai", "bhxh", "bao hiem xa hoi", "co quan thue", "buu dien", "phuong", "canh sat khu vuc", "luat su",
)
_URGENT = (
    "ngay lap tuc", "trong 15 phut", "trong hom nay", "truoc 17h", "khan cap", "gap", "sau 2 gio", "toi nay cat",
    "bi khoa", "tam khoa", "phong toa", "bi bat", "dong pham", "het han",
)
_ISOLATE = ("khong duoc ke", "dung goi cho ai", "dung noi voi ai", "giu bi mat", "khong noi voi ai", "cam ke")
_MONEY = (
    "chuyen khoan", "chuyen tien", "chuyen gap", "nap ", "nap tien", "dong phi", "phi ho so", "phi phat", "tien coc",
    "chuyen coc", "coc ", "dat coc", "phi bao hiem", "phi giai ngan", "tai khoan giam dinh", "nop phat", "phi ",
)
_OTP = ("otp", "ma xac thuc", "ma 6 so", "ma dang nhap", "doc ma", "ma kich hoat")
_INSTALL = (
    ".apk", "cai dat", "cai app", "cai ung dung", "tai ung dung", "tai app", "ho tro truy cap", "tro nang",
    "ultraviewer", "anydesk", "teamviewer", "rustdesk", "chia se man hinh",
)
_BIOMETRIC = ("sinh trac", "quet khuon mat", "quet mat", "goi video de", "bat video", "nhin vao man hinh")
_ADVANCE = ("hoa hong", "hoan goc", "hoan ca von", "lai moi ngay", "lai %", "cam ket", "nhiem vu", "combo", "lay lai tien", "thu hoi")
_GROUP = ("t.me/", "telegram", "zalo.me/", "nhom zalo", "room vip")

LEVELS = ((85, "rat_cao", "Rất cao"), (50, "cao", "Cao"), (25, "trung_binh", "Trung bình"), (0, "thap", "Thấp"))

_OFFICIAL_HOSTS = (
    "evn.com.vn", "evnhanoi.vn", "evnhcmc.vn", "cskh.evnspc.vn", "vietcombank.com.vn", "bidv.com.vn",
    "momo.vn", "shopee.vn", "ghn.vn", "viettel.vn", "vnpost.vn",
)


def band_for(score: int, strong: int) -> tuple[str, str]:
    """The visible band comes only from the score. Rất cao needs two strong factors."""
    if score >= 85 and strong >= 2:
        return "rat_cao", "Rất cao"
    if score >= 50:
        return "cao", "Cao"
    if score >= 25:
        return "trung_binh", "Trung bình"
    return "thap", "Thấp"


def _phrase_negated(folded: str, needle: str) -> bool:
    """True when every occurrence of the cue sits after không/chưa yêu cầu or không gọi."""
    if not needle:
        return False
    start = 0
    seen = False
    while True:
        index = folded.find(needle, start)
        if index < 0:
            break
        seen = True
        window = folded[max(0, index - 48) : index]
        if not re.search(r"(khong|chua)\s.{0,32}(goi|yeu cau|bat|bao gio)|khong bao gio|khong yeu cau|khong goi", window):
            return False
        start = index + len(needle)
    return seen


def safe_advisory(text: str) -> bool:
    """Bank warnings, successful top-ups, and in-person instructions. Not a demand."""
    folded = fold(text or "")
    found = harvest_indicators(text or "")
    if found.get("lookalikes") or found.get("apk") or found.get("crypto_wallets"):
        return False
    if any(len(account) >= 8 for account in found.get("bank_accounts") or []):
        return False
    if "http" in folded or ".apk" in folded:
        return False
    if re.search(r"khong (goi|yeu cau|bao gio|bat)", folded) and not re.search(r"(stk|chuyen khoan|chuyen tien|chuyen vao|\.apk)", folded):
        return True
    if re.search(r"(da|vua)\s+nap thanh cong|nap thanh cong|giao dich thanh cong", folded):
        return True
    if re.search(r"(den tru so|ra quay|mang cccd|mang can cuoc|den cong an)", folded) and "chuyen" not in folded and "stk" not in folded:
        return True
    return False


def payee_demand(text: str) -> bool:
    """Utility or authority, a sum of money, a payee account, and a cut-off threat."""
    folded = fold(text or "")
    found = harvest_indicators(text or "")
    utility = any(word in folded for word in ("dien luc", "evn", "tien dien", "cong an", "ngan hang"))
    threat = any(word in folded for word in ("cat dien", "ngat dien", "qua han", "het han", "truoc ", "trong hom nay"))
    return bool(utility and threat and found.get("bank_accounts") and _find(folded, _MONEY))


def official_notice(text: str) -> bool:
    """Real bank, utility, delivery, and wallet notices. They mention OTP or money without asking the reader to comply with a stranger."""
    folded = fold(text or "")
    if any(word in folded for word in (".apk", "ho tro truy cap", "tro nang", "ultraviewer", "anydesk", "doc ma", "doc otp", "chuyen vao stk", "tai khoan giam dinh")):
        return False
    # A real notice never carries a payee, a non-official link, or a request to send the code back.
    found = harvest_indicators(text or "")
    if any(len(account) >= 8 for account in found.get("bank_accounts") or []) or found.get("crypto_wallets") or found.get("lookalikes") or found.get("apk") or found.get("telegram"):
        return False
    if any(word in folded for word in ("nhan lai", "gui lai ma", "doc lai", "gui lai 6 so", "nhan 6 so", "kich hoat vao", "vao vi", "vao stk", "vao so tai khoan", "hoan don", "luu kho")):
        return False
    hosts = [url.split("/")[0].lower() for url in found.get("urls") or []]
    if any(host and not any(host == domain or host.endswith("." + domain) for domain in _OFFICIAL_HOSTS) for host in hosts):
        return False
    refuses_share = any(word in folded for word in ("khong chia se", "khong cung cap", "dung cung cap", "khong doc ma"))
    if "otp" in folded and refuses_share and not any(word in folded for word in ("doc cho", "doc giup", "gui ma cho")):
        return True
    if any(word in folded for word in ("tien dien", "hoa don tien dien", "evn")) and "apk" not in folded:
        if any(word in folded for word in ("thong bao", "ky thanh toan", "evn.com.vn", "tra cuu")):
            return True
    if any(word in folded for word in ("don hang", "dang giao", "giao hang", "shipper")) and "http" not in folded and "phi ship" not in folded and "phi phat" not in folded:
        if "chuyen khoan" not in folded or "khong can chuyen" in folded or "khong chuyen" in folded:
            return True
    if "momo" in folded and any(word in folded for word in ("uu dai", "khuyen mai", "trong app momo")) and "otp" not in folded and "http" not in folded:
        return True
    return False


def _find(folded: str, words) -> str:
    for word in words:
        if word in folded:
            return word.strip()
    return ""


def _snippet(text: str, needle: str) -> str:
    folded = fold(text)
    i = folded.find(needle)
    if i < 0:
        return ""
    start = max(0, i - 25)
    return ("…" if start else "") + text[start : i + len(needle) + 35].strip() + "…"


def score_text(text: str, indicators: dict | None = None, match: dict | None = None) -> dict:
    """Return {score, level, label, factors[]} for one message or a joined transcript."""
    if official_notice(text) or safe_advisory(text):
        return {"score": 0, "level": "thap", "label": "Thấp", "factors": []}
    folded = fold(text or "")
    found = indicators if indicators is not None else harvest_indicators(text or "")
    factors: list[dict] = []

    def add(code: str, label: str, weight: int, evidence: str = "") -> None:
        if not any(item["code"] == code for item in factors):
            factors.append({"code": code, "label": label, "weight": weight, "evidence": evidence[:140]})

    if found.get("lookalikes"):
        add("lookalike", "Tên miền giả thương hiệu", 22, found["lookalikes"][0])
    install_hit = _find(folded, _INSTALL)
    if found.get("apk") or found.get("remote_ids") or (install_hit and not _phrase_negated(folded, install_hit)):
        ev = (found.get("apk") or found.get("remote_ids") or [""])[0] or _snippet(text, install_hit)
        add("install", "Bắt cài ứng dụng / điều khiển máy", 25, ev)
    if found.get("techniques"):
        add("technique", "Thủ thuật chiếm quyền", 10, ", ".join(found["techniques"][:2]))
    if (w := _find(folded, _OTP)):
        add("otp", "Đòi mã OTP / mã đăng nhập", 30, _snippet(text, w))
    if found.get("crypto_wallets"):
        add("crypto", "Ví tiền ảo do người lạ đưa", 18, found["crypto_wallets"][0])
    if (w := _find(folded, _BIOMETRIC)) and not _phrase_negated(folded, w):
        add("biometric", "Đòi khuôn mặt / sinh trắc học", 15, _snippet(text, w))
    if (w := _find(folded, _MONEY)) and "nap thanh cong" not in folded and "giao dich thanh cong" not in folded:
        add("money", "Đòi chuyển tiền / nạp / đóng phí", 15, _snippet(text, w))
    if found.get("bank_accounts"):
        add("account", "Đưa số tài khoản lạ", 10, found["bank_accounts"][0])
    if (w := _find(folded, _AUTHORITY)):
        add("authority", "Tự xưng cơ quan, tổ chức", 12, _snippet(text, w))
    if (w := _find(folded, _ISOLATE)):
        add("isolate", "Cấm nói với người thân", 15, _snippet(text, w))
    if (w := _find(folded, _URGENT)) or found.get("pressure"):
        add("urgency", "Giục gấp / đe dọa", 10, (found.get("pressure") or [""])[0] or _snippet(text, w))
    if (w := _find(folded, _ADVANCE)):
        add("advance", "Hứa lãi, hoa hồng, thu hồi tiền", 12, _snippet(text, w))
    if found.get("telegram") or found.get("zalo") or _find(folded, _GROUP):
        add("group", "Kéo vào nhóm kín / kênh riêng", 6, (found.get("telegram") or found.get("zalo") or [""])[0])
    if not found.get("lookalikes"):
        if found.get("urls"):
            add("link", "Có đường dẫn", 6, found["urls"][0])
        elif "link" in folded or "duong dan" in folded:
            add("link", "Nhắc bấm đường dẫn", 12, _snippet(text, "link" if "link" in folded else "duong dan"))
    if payee_demand(text):
        add("payee", "Bắt chuyển vào tài khoản kèm hạn cắt", 18, (found.get("bank_accounts") or [""])[0])
        add("cutoff", "Hạn chót hoặc đe cắt dịch vụ", 14, "")
    if match and float(match.get("confidence") or 0) >= 0.45:
        add("known", f"Giống kịch bản đã biết: {match.get('title', '')}", int(round(20 * min(1.0, float(match["confidence"])))), match.get("id", ""))
    score = min(100, sum(item["weight"] for item in factors))
    strong_here = [item for item in factors if item["code"] in STRONG]
    if len(factors) == 1 and factors[0]["code"] in {"money", "link", "authority", "group", "urgency", "account"}:
        score = min(score, 20)
    if len(strong_here) < 2:
        score = min(score, 74)
    factors.sort(key=lambda item: item["weight"], reverse=True)
    level, label = band_for(score, len(strong_here))
    return {"score": score, "level": level, "label": label, "factors": factors}


STRONG = {"lookalike", "install", "otp", "crypto", "biometric", "payee", "cutoff"}


def merge_factors(previous: list[dict] | None, current: list[dict]) -> dict:
    """Live risk over a conversation: the union of factors seen so far."""
    seen = {item["code"]: item for item in previous or []}
    for item in current:
        if item["code"] not in seen or item["weight"] > seen[item["code"]]["weight"]:
            seen[item["code"]] = item
    factors = sorted(seen.values(), key=lambda item: item["weight"], reverse=True)
    score = min(100, sum(item["weight"] for item in factors))
    strong_here = [item for item in factors if item["code"] in STRONG]
    if len(strong_here) < 2:
        score = min(score, 74)
    level, label = band_for(score, len(strong_here))
    return {"score": score, "level": level, "label": label, "factors": factors}


def strong_count(result: dict) -> int:
    return sum(1 for item in result.get("factors", []) if item["code"] in STRONG)


_ = re
