"""A readable first draft of a new scam's title, summary, red flags and advice, built
from the transcript with rules. The extraction model gets it as a suggestion and
usually writes its own; without a model (mock, or the router down) this draft is
what a reviewer sees and what users read once it is published."""

from __future__ import annotations

import re

from app.agent.state import AgentState

# "Tôi gọi từ phòng CSGT", "em bên trung tâm tiêm chủng", "con là trợ lý của giáo sư"
_INTRO = re.compile(
    r"\b(?:tôi|em|con|cháu|mình|bên em|bên con|bên mình|chúng tôi)\s+"
    r"(?:là|gọi từ|gọi bên|bên|thuộc|ở)\s+(?P<who>[^,.!?;]{3,60})",
    re.IGNORECASE,
)
_TRIM = re.compile(r"\s+(?:đây|ạ|nhé|nha|đó|của anh|của chị|của chú|của cô)\b.*$", re.IGNORECASE)
_PRETEXTS = [
    ("nộp phạt", r"nộp phạt|phạt nguội|biên bản phạt"),
    ("lệ phí đổi giấy tờ", r"lệ phí|phí đổi|đổi gấp"),
    ("đặt cọc giữ suất", r"đặt cọc|\bcọc\b|giữ suất"),
    ("phí hồ sơ", r"phí hồ sơ"),
    ("hoàn tiền", r"hoàn tiền|hoàn vé|hoàn phí|đền bù"),
    ("bình chọn", r"bình chọn"),
    ("trúng thưởng", r"trúng thưởng|quà tặng"),
    ("nạp tiền", r"\bnạp\b"),
]
_FLAG_SKIP = ("Giống kịch bản đã biết",)
_NO_WHO = {"bình chọn": "Nhờ bình chọn", "trúng thưởng": "Báo trúng thưởng", "hoàn tiền": "Báo hoàn tiền"}


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " và " + items[-1]


def _who(messages: list[str]) -> str:
    for text in messages[:3]:
        match = _INTRO.search(text)
        if not match:
            continue
        who = _TRIM.sub("", match.group("who").strip())
        # "trợ lý của giáo sư bác sĩ ở viện" -> drop the place, keep a title-sized phrase.
        who = re.split(r"\s+(?:ở|tại|có|đang|thông báo|báo)\s+", who, maxsplit=1)[0]
        who = " ".join(who.split()[:7])
        if len(who) >= 3:
            return who
    return ""


def _pretext(text: str) -> str:
    for label, pattern in _PRETEXTS:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return ""


def _routes(state: AgentState, text: str) -> list[str]:
    ind = state.indicators or {}
    routes = []
    if ind.get("urls"):
        routes.append("đường dẫn")
    if ind.get("bank_accounts"):
        routes.append("tài khoản")
    if ind.get("ewallets"):
        routes.append("ví điện tử")
    if ind.get("crypto_wallets"):
        routes.append("ví tiền mã hóa")
    if ind.get("apk"):
        routes.append("file cài đặt")
    if re.search(r"\b(?:otp|mã\s*\d|mã xác nhận|mã 6 số|mã gửi về)", text, re.IGNORECASE):
        routes.append("mã xác nhận")
    return routes


def draft_new_scam(state: AgentState, scammer_messages: list[str]) -> dict:
    text = " ".join(scammer_messages)
    who = _who(scammer_messages)
    pretext = _pretext(text)
    routes = _routes(state, text)
    lead = f"Giả {who}" if who else _NO_WHO.get(pretext, pretext.capitalize() if pretext else "Chiêu mới")
    joined = _join(routes[:3])
    if who and pretext:
        title = f"{lead}: {pretext}" + (f" qua {joined}" if joined else "")
    elif joined:
        title = f"{lead} qua {joined}" if (who or pretext) else f"{lead}: {joined}"
    else:
        title = lead
    title = title[:1].upper() + title[1:]

    ind = state.indicators or {}
    pressure = [str(item).lower() for item in ind.get("pressure") or []]
    parts = [f"Đối tượng tự xưng {who}" if who else "Đối tượng chủ động liên hệ"]
    if pretext:
        parts.append(f"lấy cớ {pretext}")
    if pressure:
        parts.append("gây sức ép: " + ", ".join(pressure[:2]))
    if routes:
        parts.append("rồi dẫn nạn nhân tới " + _join(routes))
    summary = ", ".join(parts) + "."
    flags = [f["label"] for f in state.risk_factors or [] if f.get("label") and not f["label"].startswith(_FLAG_SKIP)]
    advice = [
        "Gọi lại số tổng đài chính thức của cơ quan hoặc đơn vị họ tự xưng để kiểm tra."
        if who
        else "Hỏi lại người nhờ bằng một kênh khác, ví dụ gọi điện trực tiếp."
    ]
    if "đường dẫn" in routes:
        advice.append("Không bấm đường dẫn lạ, cơ quan nhà nước không thu tiền qua đường dẫn gửi trong tin nhắn.")
    if any(r in routes for r in ("tài khoản", "ví điện tử", "ví tiền mã hóa")):
        advice.append("Không chuyển tiền vào tài khoản cá nhân, kể cả khi họ đọc đúng tên bạn.")
    if "mã xác nhận" in routes:
        advice.append("Không gửi mã xác nhận cho bất kỳ ai, mã đó là chìa khóa tài khoản của bạn.")
    return {"title": title[:120], "summary": summary, "red_flags": flags[:5], "advice": " ".join(advice)}
