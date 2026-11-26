"""One-shot reading of a suspicious message or a short transcript."""

import re

from app.agent.orchestrator import pack
from app.agent.prompts import ANALYST_SYSTEM
from app.agent.schemas import AnalystOutput
from app.services.matching import branch_hint, candidate_payload, search_scripts


_BENIGN = (
    "chuc mung sinh nhat",
    "sinh nhat vui",
    "happy birthday",
    "chuc ngu ngon",
    "chuc mung nam moi",
    "cuoi tuan cafe",
    "me oi",
    "toi nay con ve",
    "con ve muon",
)
_PRIZE = ("trung thuong", "trung giai", "trung iphone", "qua tri an", "nhan thuong", "qua tang", "iphone")
_MONEY_WORD = ("chuyen khoan", "chuyen tien", "nap tien", "hoc phi", "tien coc", "trieu", "stk", "tien dien", "tien nuoc")
_HOUSEHOLD = ("tien dien", "tien nuoc", "tien nha", "hoc phi", "tien hoc", "cho truong")
_IMPERSONATION = ("cong an", "canh sat", "thieu ta", "dieu tra", "ngan hang goi")
_STRANGER = ("chuyen cho anh", "chuyen cho chi", "vao so", "so tai khoan", "nguoi la", "chuyen vao stk")
_URGENCY = ("khan cap", "ngay lap tuc", "trong 15 phut", "trong vai phut", "bi bat ngay", "het han ngay")
_OTP_CUE = ("otp", "ma xac thuc", "ma otp", "ma dang nhap", "ma 6 so")
_INSTALL_CUE = (
    ".apk", "ho tro truy cap", "tro nang", "ultraviewer", "anydesk", "teamviewer", "rustdesk",
    "cai ung dung", "tai ung dung", "cai app", "tai app", "file cai",
)
_CRYPTO_CUE = ("usdt", "trc20", "erc20", "bep20", "vi tien ao", "tien ma hoa")
_ADVANCE_CUE = (
    "hoa hong", "hoan goc", "lai moi ngay", "phi thu hoi", "lay lai tien", "phi phong toa", "phi giai ngan",
    "combo", "nap toi thieu", "phi bao hiem khoan vay", "giu suat", "giu phong",
)
_THREAT_CUE = ("khoa 2 chieu", "khoa hai chieu", "sau 2 gio", "cat dien", "dung giao dich", "bi tam giu", "tam dung chuyen tien")


def _surface(text: str) -> set[str]:
    from app.agent.casefile import harvest_indicators
    from app.agent.textutil import fold

    folded = fold(text or "")
    found = harvest_indicators(text or "")
    cues: set[str] = set()
    if found["phones"] or found["hotlines"] or re.search(r"(?<!\d)0\d{8,10}", folded):
        cues.add("phone")
    if found["urls"] or "http" in folded or "www." in folded or ("zalo" in folded and re.search(r"\d{8,}", folded)):
        cues.add("link")
    if any(word in folded for word in _MONEY_WORD) or found["bank_accounts"]:
        cues.add("money")
    if any(word in folded for word in _PRIZE):
        cues.add("prize")
    if any(word in folded for word in _URGENCY):
        cues.add("urgency")
    if any(word in folded for word in _OTP_CUE):
        cues.add("otp")
    if found["bank_accounts"]:
        cues.add("account")
    if any(word in folded for word in _IMPERSONATION):
        cues.add("impersonation")
    if any(word in folded for word in _STRANGER):
        cues.add("stranger")
    if any(word in folded for word in _HOUSEHOLD):
        cues.add("household")
    if found.get("apk") or found.get("remote_ids") or any(word in folded for word in _INSTALL_CUE):
        cues.add("install")
    if found.get("crypto_wallets") or any(word in folded for word in _CRYPTO_CUE):
        cues.add("crypto")
    if found.get("lookalikes"):
        cues.add("lookalike")
    if any(word in folded for word in _ADVANCE_CUE):
        cues.add("advance")
    if any(word in folded for word in _THREAT_CUE):
        cues.add("urgency")
    if found.get("telegram") or found.get("zalo"):
        cues.add("link")
    return cues


def _model_says_benign(analyst, hot: bool) -> bool:
    from app.agent.textutil import fold

    if hot or float(analyst.scammer_suspicion or 0) >= 0.4:
        return False
    raw = (analyst.scammer_intent or "").lower()
    folded = fold(raw)
    # "chuyện" and "chuyển" fold to the same letters, so keep the diacritics for single words.
    if any(word in raw for word in ("otp", "chuyển", "cài", "trúng", "thưởng", "lừa", "phí", "giám định", "nạp", "link")):
        return False
    return not any(phrase in folded for phrase in ("chuyen khoan", "chuyen tien", "nap tien", "gui tien", "trung thuong", "cai app"))


def _everyday(text: str) -> bool:
    """A meeting time or a small household amount, with no scam second-signal."""
    from app.agent.textutil import fold

    folded = fold(text or "")
    if not re.search(
        r"(hop phong|hop luc|hop online|google meet|lich hop|chuyen sang\s+\d|tien com|tien an|tien ca phe|\d+\s*k\s+tien)",
        folded,
    ):
        return False
    found = _surface(text)
    return not (found & {"prize", "phone", "link", "urgency", "otp", "account", "impersonation", "stranger"})


def _plain_note(text: str) -> bool:
    from app.agent.textutil import fold

    folded = fold(text or "")
    return any(phrase in folded for phrase in _BENIGN)


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
    from app.services.risk import official_notice

    if official_notice(text):
        return {
            "risk_score": 0,
            "risk_factors": [],
            "indicators": {},
            "ioc_links": [],
            "warnings": [],
            "risk": "thap",
            "risk_label": "Thấp",
            "is_scam": False,
            "verdict": "benign",
            "confidence": 0,
            "intent": "Thông báo từ kênh quen, không đòi làm theo người lạ.",
            "red_flags": [],
            "matched_script": None,
            "next_step": None,
            "advice": "Tin này giống thông báo của ngân hàng, điện lực, giao hàng hoặc ví. Không đọc mã cho ai, không bấm đường dẫn lạ.",
            "branch": hint,
            "mock": provider.is_mock,
        }
    surface = _surface(text)
    model_benign = _model_says_benign(analyst, hot)
    plain = _plain_note(text) or _everyday(text)
    # A clock time (8h) or a room number (302) is not a phone or an account.
    # Money alone (tiền điện, học phí cho trường) is not a scam. It needs a second signal.
    second = surface & {"prize", "phone", "link", "urgency", "otp", "account", "impersonation", "stranger", "install", "crypto", "lookalike", "advance"}
    hard = set(second)
    if "money" in surface and second and "household" not in surface:
        hard.add("money")
    if hard:
        if "prize" in surface or ("phone" in surface and "link" in surface):
            level, label = ("cao", "Cao") if level == "thap" else (level, label)
            is_scam = True
            verdict = "scam"
        elif level in {"cao", "rat_cao"} or confidence >= 0.45:
            is_scam = True
            verdict = "scam"
        else:
            level, label = "trung_binh", "Trung bình"
            is_scam = True
            verdict = "scam"
    elif plain or model_benign or "household" in surface:
        level, label = "thap", "Thấp"
        is_scam = False
        verdict = "benign"
    elif "money" in surface and not second:
        level, label = "trung_binh", "Trung bình"
        is_scam = False
        verdict = "unclear"
    elif level in {"cao", "rat_cao"} or (hot and confidence >= 0.55):
        is_scam = True
        verdict = "scam"
    elif level == "thap":
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
    benign = verdict == "benign" and not hard
    if benign:
        matched = None
        next_step = None
        advice = "Tin này giống lời chúc hoặc trò chuyện thường. Không cần làm gì thêm."
    from app.agent.casefile import harvest_indicators
    from app.data.warnings import cards_for_category
    from app.services.intel import lookup
    from app.services.risk import score_text, strong_count

    found = harvest_indicators(text)
    explained = score_text(text, found, matched if not benign else None)
    if not benign and verdict != "scam" and strong_count(explained) >= 2 and explained["score"] >= 50:
        verdict, is_scam = "scam", True
        if level in {"thap", "trung_binh"}:
            level, label = "cao", "Cao"
    if verdict == "scam" and explained["score"] >= 85 and strong_count(explained) >= 2 and level != "rat_cao":
        level, label = "rat_cao", "Rất cao"
    try:
        links = lookup(session, found)
    except Exception:
        links = []
    cards = []
    if not benign and matched:
        cards = [
            {"id": card["id"], "title": card["title"], "rising": card["rising"], "do": card["do"], "sources": card["sources"][:2]}
            for card in cards_for_category(matched["category"])[:2]
        ]
    return {
        "risk_score": 0 if benign else explained["score"],
        "risk_factors": [] if benign else explained["factors"],
        "indicators": {key: value for key, value in found.items() if value and key not in ("brands", "pressure")} if not benign else {},
        "ioc_links": links,
        "warnings": cards,
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
