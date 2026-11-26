"""Scam-simulation practice. Deterministic scoring, masked secrets, sanitized scammer lines.

The scammer voice uses the `sim` role and the reply judge uses `analyst`. Both are
small models already configured on the router. The mock provider covers both schemas
so a session is playable with no API key. Nothing here writes a Script or an IOC.
"""

from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agent.casefile import valid_crypto_wallet
from app.data.quiz_safe import SAFE_MESSAGES
from app.data.warnings import cards_for_category
from app.models import Script, TrainingMessage, TrainingSession, utcnow
from app.taxonomy import CATEGORIES, CHANNELS

TRAINING_GROUPS: dict[str, list[str]] = {
    "cong-an": ["police", "vneid", "tax"],
    "ngan-hang-vi": ["bank", "momo", "telco", "utility"],
    "giao-hang": ["shipper", "ecommerce"],
    "viec-lam": ["job", "course"],
    "dau-tu": ["investment", "romance", "recovery"],
    "qr": ["qr"],
    "deepfake-nguoi-than": ["deepfake", "relative", "hijack"],
    "cai-app": ["rat"],
    "khac": ["prize", "loan", "charity", "rental", "travel", "other"],
}

GROUP_LABELS: dict[str, str] = {
    "cong-an": "Công an / cơ quan giả",
    "ngan-hang-vi": "Ngân hàng & ví giả",
    "giao-hang": "Giao hàng / sàn TMĐT",
    "viec-lam": "Việc làm online",
    "dau-tu": "Đầu tư & tình cảm",
    "qr": "Mã QR",
    "deepfake-nguoi-than": "Deepfake / người thân",
    "cai-app": "Cài app chiếm quyền",
    "khac": "Khác",
}

LABELS = ("refuse", "verify", "suspicious", "comply", "leak", "fell", "neutral")
GOOD_LABELS = {"refuse", "verify", "suspicious"}
PASSIVE_LABELS = {"comply", "neutral"}
MAX_USER_MESSAGES = 30

_AMOUNT = re.compile(
    r"(?i)\d+(?:[.,]\d+)?\s*(?:đồng|triệu|nghìn|ngàn|tỷ|phút|giây|giờ|ngày|vnd|đ|k\b|%)"
)
_URL = re.compile(r"(?i)https?://\S+|www\.\S+")
_EMAIL = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
_MESSENGER = re.compile(r"(?i)\b(?:t\.me|zalo\.me)/\S+")
_DOMAIN = re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+(?:vn|com|net|xyz|top|info|io|app|me|cc|org)\b")
_APK = re.compile(r"(?i)\b[a-z0-9][\w.-]*\.apk\b")
_REMOTE = re.compile(
    r"(?i)(?:\bid\s*)?(?:ultraview(?:er)?|anydesk|teamviewer)\s*\d[\d\s]{4,18}\d"
)
_SPACED_ID = re.compile(r"\b\d{3}\s+\d{3}\s+\d{3}\b")
_ACCOUNT_NAME = re.compile(r"(?i)((?:chủ|tên)\s+tài\s+khoản(?:\s+là)?)\s+[^\n,.]{2,80}")
_LONG_DIGITS = re.compile(r"\d{7,}")
_WALLET = re.compile(r"\b[A-Za-z0-9]{26,64}\b")

_FELL = re.compile(
    r"(?i)("
    r"(otp|mã\s*otp|mã\s*xác\s*thực).{0,40}\d{4,8}"
    r"|\d{4,8}.{0,24}(otp|mã\s*otp)"
    r"|mã\s+(của\s+)?(tôi|em)\s+là\s+\d{4,8}"
    r"|(đã|vừa)\s+(chuyển|ck|cài|tải)"
    r"|(chuyển|ck|cài|tải)\s+(rồi|xong)"
    r"|mật\s*khẩu\s+(là|:)\s+\S+"
    r")"
)
_VERIFY = re.compile(
    r"(?i)(tôi\s+sẽ\s+gọi|em\s+sẽ\s+gọi|gọi\s+(lên\s+|lại\s+)?(tổng\s*đài|công\s*an|ngân\s*hàng)"
    r"|xác\s*minh|hỏi\s+con|ra\s+phường|số\s+chính\s*thức|ứng\s*dụng\s+chính\s*thức|app\s+chính\s*thức)"
)
_REFUSE = re.compile(
    r"(?i)(không\s+(chuyển|ck|gửi|cung\s*cấp|làm\s+theo|nghe|đọc|cài|tin)"
    r"|gác\s*máy|cúp\s*máy|từ\s*chối|đừng\s+(gọi|nhắn)|không\s+theo|\bchặn\b)"
)
_SUSPICIOUS = re.compile(
    r"(?i)(lừa\s*đảo|lừa\s+à|giả\s*mạo|nghi\s*(ngờ|là)|có\s+phải\s+lừa|không\s+thật)"
)
_COMPLY = re.compile(
    r"(?i)(đồng\s*ý|để\s+tôi\s+chuyển|gửi\s+link|em\s+làm\s+theo|tôi\s+làm\s+theo|vâng\s+em\s+chuyển)"
)
_LEAK_NAME = re.compile(r"(?i)(?:tên\s+(?:tôi|em|mình)|tôi\s+tên|họ\s*(?:và\s*)?tên)\s*(?:là|:)\s+\S+")
_LEAK_ADDRESS = re.compile(r"(?i)địa\s*chỉ\s*(?:của\s*(?:tôi|em|mình))?\s*(?:là|:)\s+\S+")
_REPORT = re.compile(r"(?i)báo\s+công\s*an")
_BLOCK = re.compile(r"(?i)\bchặn\b")


class TrainingError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class SimJudgeOutput(BaseModel):
    label: Literal["refuse", "verify", "suspicious", "comply", "leak", "fell", "neutral"]
    caught_flag_ids: list[int] = Field(default_factory=list)
    rationale: str = ""


class SimScammerOutput(BaseModel):
    text: str = ""
    stage_index: int = 0


def group_for(category: str) -> str:
    for gid, cats in TRAINING_GROUPS.items():
        if category in cats:
            return gid
    return "khac"


def max_turns_for(difficulty: str) -> int:
    return {"de": 10, "vua": 12, "kho": 14}.get(difficulty, 12)


def reassure_budget(difficulty: str) -> int:
    return {"de": 0, "vua": 1, "kho": 2}.get(difficulty, 1)


def scammer_steps(script: Script) -> list[dict]:
    return [step for step in (script.steps or []) if (step or {}).get("actor") == "scammer"]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[0-9a-zà-ỹ]{4,}", (text or "").lower())
    stop = {
        "không", "được", "trong", "những", "nhưng", "hoặc", "người", "thông", "nhắn",
        "bạn", "anh", "chị", "em", "của", "cho", "với", "một", "các", "này", "kia",
    }
    return {word for word in words if word not in stop}


def stage_flags(script: Script) -> dict[int, list[int]]:
    """Map each red-flag index onto scammer stages by keyword overlap."""
    steps = scammer_steps(script)
    flags = list(script.red_flags or [])
    mapping = {index: [] for index in range(len(steps))}
    flag_tokens = [(index, _tokens(text)) for index, text in enumerate(flags)]
    for stage, step in enumerate(steps):
        blob = _tokens(" ".join([step.get("intent") or "", " ".join(step.get("phrases") or [])]))
        for flag_id, tokens in flag_tokens:
            if tokens and blob and (tokens & blob):
                mapping[stage].append(flag_id)
    assigned = {flag_id for ids in mapping.values() for flag_id in ids}
    if mapping:
        for flag_id, _tokenset in flag_tokens:
            if flag_id not in assigned:
                mapping[0].append(flag_id)
    return mapping


def sanitize_scammer_text(text: str) -> str:
    """Strip real-looking payment data, links, wallets, and account-holder names."""
    raw = text or ""
    kept: list[str] = []

    def _keep(match: re.Match) -> str:
        kept.append(match.group(0))
        return f"«KEEP{len(kept) - 1}»"

    cleaned = _AMOUNT.sub(_keep, raw)
    cleaned = _URL.sub("[LINK_GIẢ]", cleaned)
    cleaned = _EMAIL.sub("[LINK_GIẢ]", cleaned)
    cleaned = _MESSENGER.sub("[LINK_GIẢ]", cleaned)
    cleaned = _DOMAIN.sub("[LINK_GIẢ]", cleaned)
    cleaned = _APK.sub("[APP_GIẢ]", cleaned)
    cleaned = _REMOTE.sub("[ID_GIẢ]", cleaned)
    cleaned = _SPACED_ID.sub("[ID_GIẢ]", cleaned)
    cleaned = _ACCOUNT_NAME.sub(r"\1 [TÊN_GIẢ]", cleaned)

    def _wallet(match: re.Match) -> str:
        token = match.group(0)
        if token.startswith("«KEEP"):
            return token
        return "[VÍ_GIẢ]" if valid_crypto_wallet(token) else token

    cleaned = _WALLET.sub(_wallet, cleaned)
    cleaned = _LONG_DIGITS.sub("[STK_GIẢ]", cleaned)
    for index, value in enumerate(kept):
        cleaned = cleaned.replace(f"«KEEP{index}»", value)
    cleaned = re.sub(r"(?:\[(?:LINK_GIẢ|STK_GIẢ|APP_GIẢ|ID_GIẢ|VÍ_GIẢ|TÊN_GIẢ)\]\s*){2,}", lambda match: match.group(0).split()[0] + " ", cleaned)
    return " ".join(cleaned.split()).strip()


def scammer_text_safe(text: str) -> bool:
    """True when a stored scammer line has no payment secret, link, or wallet."""
    body = text or ""
    stripped = _AMOUNT.sub("", body)
    if _LONG_DIGITS.search(stripped):
        return False
    if _URL.search(body) or _EMAIL.search(body) or _MESSENGER.search(body) or _DOMAIN.search(body):
        return False
    if _APK.search(body) or _REMOTE.search(body) or _SPACED_ID.search(body):
        return False
    named = re.search(r"(?i)(?:chủ|tên)\s+tài\s+khoản(.{0,48})", body)
    if named and "[TÊN_GIẢ]" not in named.group(0) and re.search(r"[a-zà-ỹ]{3,}\s+[a-zà-ỹ]{3,}", named.group(1), re.I):
        return False
    for token in _WALLET.findall(body):
        if valid_crypto_wallet(token):
            return False
    return True


def mask_user_text(text: str) -> tuple[str, list[str]]:
    """Replace OTP, card, CCCD, and password-looking strings before storage."""
    leaked: list[str] = []

    def add(kind: str) -> None:
        if kind not in leaked:
            leaked.append(kind)

    def _password(match: re.Match) -> str:
        add("password")
        return match.group(1) + "[ĐÃ CHE]"

    masked = re.sub(r"(?i)(mật\s*khẩu\s*(?:là|:|của tôi là)?\s*)(\S+)", _password, text or "")

    def _sub(pattern: str, kind: str, source: str) -> str:
        def repl(_match: re.Match) -> str:
            add(kind)
            return "[ĐÃ CHE]"

        return re.sub(pattern, repl, source)

    masked = _sub(r"(?<!\d)\d{13,19}(?!\d)", "account", masked)
    masked = _sub(r"(?<!\d)\d{12}(?!\d)", "cccd", masked)
    masked = _sub(r"(?<!\d)\d{4,8}(?!\d)", "otp", masked)

    name = re.search(
        r"(?i)((?:tên\s+(?:tôi|em|mình)|tôi\s+tên|họ\s*(?:và\s*)?tên)\s*(?:là|:)\s*)(\S+(?:\s+\S+){0,3})",
        masked,
    )
    if name:
        add("name")
        masked = masked[: name.start(2)] + "[ĐÃ CHE]" + masked[name.end(2) :]
    address = re.search(r"(?i)((?:địa\s*chỉ)\s*(?:của\s*(?:tôi|em|mình))?\s*(?:là|:)\s*)([^\n.]{4,80})", masked)
    if address:
        add("address")
        masked = masked[: address.start(2)] + "[ĐÃ CHE]" + masked[address.end(2) :]
    return masked, leaked


def judge_rules(text: str) -> str:
    """One label from the user's original words. Rules win over the model for a fall."""
    raw = text or ""
    if _FELL.search(raw):
        return "fell"
    if re.search(r"(?<!\d)\d{12}(?!\d)", raw) or _LEAK_NAME.search(raw) or _LEAK_ADDRESS.search(raw):
        return "leak"
    if re.search(r"(?i)(số\s+tài\s+khoản|stk|số\s+thẻ).{0,24}\d{6,}", raw):
        return "leak"
    if _REPORT.search(raw) or _BLOCK.search(raw):
        return "refuse"
    if _VERIFY.search(raw):
        return "verify"
    if _REFUSE.search(raw):
        return "refuse"
    if _SUSPICIOUS.search(raw):
        return "suspicious"
    if _COMPLY.search(raw):
        return "comply"
    return "neutral"


def fell_reason(text: str) -> str:
    raw = text or ""
    folded = raw.lower()
    if re.search(r"mật\s*khẩu", folded):
        return "credentials"
    if re.search(r"(đã|vừa)\s+(cài|tải)|(cài|tải)\s+(rồi|xong)", folded):
        return "install"
    if re.search(r"otp|mã", folded) and re.search(r"\d{4,8}", raw):
        return "otp"
    if re.search(r"chuyển|ck", folded):
        return "transfer"
    return "otp"


def merge_label(rule: str, model_label: str) -> str:
    if rule == "fell":
        return "fell"
    if rule == "leak" and model_label not in {"fell", "leak"}:
        return "leak"
    if model_label in LABELS:
        return model_label
    return rule if rule in LABELS else "neutral"


def score_label(score: int) -> str:
    if score >= 80:
        return "Tỉnh táo"
    if score >= 50:
        return "Cần cẩn thận"
    return "Đã sập bẫy"


def _events(row: TrainingSession) -> list[dict]:
    return list(row.events or [])


def _stage_outcomes(row: TrainingSession, script: Script) -> list[dict]:
    steps = scammer_steps(script)
    events = _events(row)
    user_by_stage: dict[int, str] = {}
    for message in row.messages:
        if message.role == "user":
            user_by_stage[message.stage_index] = message.text
    outcomes = []
    for index, step in enumerate(steps):
        if index > row.stage_index:
            outcome = "not_reached"
        else:
            faced = [event for event in events if int(event.get("stage_index") or 0) <= index]
            labels = [event.get("label") or "" for event in faced]
            here = [event for event in events if int(event.get("stage_index") or 0) == index]
            if any(event.get("label") == "fell" for event in here):
                outcome = "fell"
            elif any(label in GOOD_LABELS for label in labels):
                outcome = "caught"
            elif row.status == "safe" and not labels:
                outcome = "caught"
            elif any(label in PASSIVE_LABELS for label in labels) or any(label == "leak" for label in labels):
                outcome = "missed"
            elif row.status == "safe":
                outcome = "caught"
            elif labels:
                outcome = "missed"
            else:
                outcome = "not_reached"
        item = {"index": index, "intent": step.get("intent") or "", "outcome": outcome}
        if index in user_by_stage:
            item["user_quote"] = user_by_stage[index][:180]
        outcomes.append(item)
    return outcomes


def _missed_flag_count(row: TrainingSession, script: Script) -> int:
    mapping = stage_flags(script)
    count = 0
    for item in _stage_outcomes(row, script):
        if item["outcome"] != "missed":
            continue
        count += len(mapping.get(item["index"]) or [])
    return count


def _leak_kinds(row: TrainingSession) -> list[str]:
    found: list[str] = []
    for event in _events(row):
        for kind in event.get("leaked") or []:
            if kind not in found:
                found.append(kind)
    return found


def score_session(row: TrainingSession, script: Script) -> int:
    steps = scammer_steps(script)
    missed = _missed_flag_count(row, script)
    leaks = _leak_kinds(row)
    reached = row.stage_index + 1 if steps else 0
    unreached = max(0, len(steps) - reached)
    score = 100 - 8 * missed
    if row.status == "safe":
        score += 2 * unreached
    if row.status == "scammed":
        score = min(score, 30)
    score -= 10 * len(leaks)
    score = max(0, min(100, score))
    score -= 5 * int(row.hints_used or 0)
    score = max(0, score)
    if row.status == "timeout":
        score = min(score, 70)
    return score


def scammer_alias(script: Script) -> str:
    if script.category in {"police", "vneid", "tax"}:
        return "Thiếu tá Hùng – Công an quận"
    if script.category in {"bank", "momo", "telco", "utility"}:
        return "CSKH [NGÂN_HÀNG]"
    if script.category in {"shipper", "ecommerce"}:
        return "Bên giao hàng"
    if script.category in {"relative", "deepfake", "hijack"}:
        return "Người thân (giả)"
    brand = (script.brand or "").strip()
    if brand and not re.search(r"\d{6,}", brand):
        return brand[:40]
    return "Người lạ"


def _phrase(step: dict) -> str:
    phrases = [item for item in (step.get("phrases") or []) if str(item).strip()]
    return str(phrases[0] if phrases else step.get("intent") or "")


def _fallback_line(script: Script, stage_index: int) -> str:
    steps = scammer_steps(script)
    if not steps:
        return "Alô, anh nghe máy giúp tôi, có việc gấp."
    step = steps[min(stage_index, len(steps) - 1)]
    cleaned = sanitize_scammer_text(_phrase(step))
    if cleaned and scammer_text_safe(cleaned):
        return cleaned[:350]
    return "Alô, anh nghe máy giúp tôi, có việc gấp cần xác nhận."


def _pack(instruction: str, payload: dict) -> str:
    return instruction.strip() + "\n\n<<<CONTEXT>>>\n" + json.dumps(payload, ensure_ascii=False) + "\n<<<END>>>"


def _complete(provider, schema, system: str, user: str, role: str):
    try:
        return provider.complete(
            schema,
            system,
            user,
            0.2 if role == "analyst" else 0.5,
            role=role,
            max_tokens=320,
        )
    except Exception:
        return None


def _judge(provider, rule: str, script: Script, stage_index: int, flag_ids: list[int], recent: list[dict], user_text: str) -> tuple[str, list[int]]:
    steps = scammer_steps(script)
    step = steps[min(stage_index, len(steps) - 1)] if steps else {}
    flags = [{"id": flag_id, "text": script.red_flags[flag_id]} for flag_id in flag_ids if flag_id < len(script.red_flags or [])]
    payload = {
        "rule_label": rule,
        "user_text": user_text,
        "stage_index": stage_index,
        "stage_intent": step.get("intent") or "",
        "flag_ids": flag_ids,
        "flags": flags,
        "recent": recent[-4:],
    }
    system = (
        "Bạn phân loại câu của người đang luyện nhận diện lừa đảo. "
        "Chỉ trả JSON với label thuộc refuse, verify, suspicious, comply, leak, fell, neutral. "
        "Không bịa số điện thoại, tài khoản, đường dẫn."
    )
    result = _complete(provider, SimJudgeOutput, system, _pack("Phân loại câu người chơi.", payload), "analyst")
    if result is None:
        return rule, []
    return merge_label(rule, result.label), list(result.caught_flag_ids or [])


def _scammer_reply(provider, script: Script, stage_index: int, recent: list[dict], difficulty: str) -> str:
    steps = scammer_steps(script)
    step = steps[min(stage_index, len(steps) - 1)] if steps else {}
    phrase = sanitize_scammer_text(_phrase(step))
    payload = {
        "phrase": phrase,
        "stage_index": stage_index,
        "title": script.title,
        "brand": script.brand or "",
        "channel": script.channel,
        "intent": step.get("intent") or "",
        "difficulty": difficulty,
        "recent": recent[-6:],
    }
    system = (
        "Bạn đóng vai người lừa đảo trong một bài luyện tập. Viết một tin nhắn tiếng Việt ngắn, kiểu chat, tối đa 350 ký tự. "
        "Không nhận mình là AI. Không đưa số điện thoại, số tài khoản, đường dẫn, ví, ID điều khiển từ xa, hay tên người thật. "
        "Dùng chỗ trống [SỐ_GIẢ], [STK_GIẢ], [NGÂN_HÀNG], [LINK_GIẢ], [VÍ_GIẢ], [ID_GIẢ], [APP_GIẢ]. "
        "Không hướng dẫn cài file ngoài kho ứng dụng, không hướng dẫn bật quyền trợ năng, không hướng dẫn vượt xác thực danh tính. "
        "Không đe dọa bạo lực, không nội dung tình dục, không lời lẽ xúc phạm."
    )
    result = _complete(provider, SimScammerOutput, system, _pack("Viết lời người lừa đảo cho bước hiện tại.", payload), "sim")
    text = ""
    if result is not None:
        text = sanitize_scammer_text(result.text or "")
    if not text or not scammer_text_safe(text):
        text = _fallback_line(script, stage_index)
    return text[:350]


def _strip_echo(reply: str, original: str) -> str:
    cleaned = reply
    for run in set(re.findall(r"\d{4,}", original or "")):
        if run and run in cleaned:
            cleaned = cleaned.replace(run, "[ĐÃ CHE]")
    return sanitize_scammer_text(cleaned)


def _closing(status: str, reason: str) -> str:
    if status == "scammed":
        if reason == "otp":
            return "Được, tôi đã nghe mã. Trong bài này thì bạn vừa mất tiền."
        if reason == "transfer":
            return "Tôi nhận được khoản chuyển. Trong đời thật thì tiền đã đi."
        if reason == "install":
            return "Máy đã cài xong theo lời tôi. Trong đời thật thì máy không còn là của bạn."
        return "Bạn đã làm theo. Trong bài này xem như bạn đã sập bẫy."
    if status == "timeout":
        return "Hết lượt luyện. Người lạ vẫn chưa bị chặn."
    return "Thôi được, bạn không làm theo. Tôi gác máy."


def purge_old_sessions(session, days: int = 7) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    old = list(session.scalars(select(TrainingSession).where(TrainingSession.created_at < cutoff)).all())
    for row in old:
        session.delete(row)
    return len(old)


def _published(session) -> list[Script]:
    return list(session.scalars(select(Script).where(Script.status == "published")).all())


def _load(session, session_id: str) -> TrainingSession:
    row = session.scalar(
        select(TrainingSession)
        .where(TrainingSession.id == session_id)
        .options(selectinload(TrainingSession.messages))
    )
    if row is None:
        raise TrainingError(404, "Không thấy phiên luyện tập.")
    row.messages.sort(key=lambda message: (message.seq, message.created_at))
    return row


def _script(session, script_id: str) -> Script:
    script = session.get(Script, script_id)
    if script is None or script.status != "published":
        raise TrainingError(404, "Không thấy kịch bản luyện tập.")
    return script


def scenario_public(script: Script) -> dict:
    steps = scammer_steps(script)
    group = group_for(script.category)
    return {
        "script_id": script.id,
        "title": script.title,
        "category": script.category,
        "category_label": CATEGORIES.get(script.category, script.category),
        "group": group,
        "channel": script.channel,
        "brand": script.brand or "",
        "occurrence_count": script.occurrence_count,
        "stages": len(steps),
        "rising": any(card.get("rising") for card in cards_for_category(script.category)),
    }


def list_scenarios(session, group: str = "") -> dict:
    rows = [script for script in _published(session) if scammer_steps(script)]
    groups = []
    for gid, _cats in TRAINING_GROUPS.items():
        groups.append(
            {
                "id": gid,
                "label": GROUP_LABELS[gid],
                "count": sum(1 for script in rows if group_for(script.category) == gid),
            }
        )
    chosen = rows
    if group:
        if group not in TRAINING_GROUPS:
            raise TrainingError(404, "Không thấy nhóm kịch bản.")
        chosen = [script for script in rows if group_for(script.category) == group]
    chosen.sort(key=lambda script: (script.occurrence_count, script.title), reverse=True)
    return {"groups": groups, "scenarios": [scenario_public(script) for script in chosen]}


def _pick_script(session, script_id: str | None, group: str | None) -> Script:
    if script_id:
        return _script(session, script_id)
    rows = [script for script in _published(session) if scammer_steps(script)]
    if group:
        if group not in TRAINING_GROUPS:
            raise TrainingError(404, "Không thấy nhóm kịch bản.")
        rows = [script for script in rows if group_for(script.category) == group]
    if not rows:
        raise TrainingError(404, "Không có kịch bản trong nhóm này.")
    return random.choice(rows)


def _message_public(message: TrainingMessage) -> dict:
    data = {
        "id": message.id,
        "role": message.role,
        "text": message.text,
        "stage_index": message.stage_index,
        "created_at": message.created_at.isoformat(),
    }
    if message.flags:
        data["flags"] = message.flags
    return data


def _visible_flags(row: TrainingSession, script: Script) -> dict:
    mapping = stage_flags(script)
    delivered = {message.stage_index for message in row.messages if message.role == "scammer"}
    items = []
    for stage in sorted(delivered):
        for flag_id in mapping.get(stage) or []:
            if flag_id < len(script.red_flags or []):
                items.append({"id": flag_id, "text": script.red_flags[flag_id], "stage_index": stage})
    if row.mode == "hoc":
        return {"mode": "hoc", "items": items}
    return {"mode": "thu_thach", "count": len(items)}


def session_public(row: TrainingSession, script: Script) -> dict:
    steps = scammer_steps(script)
    return {
        "id": row.id,
        "status": row.status,
        "end_reason": row.end_reason or "",
        "score": row.score,
        "scenario": {
            "script_id": script.id,
            "title": script.title,
            "category": script.category,
            "category_label": CATEGORIES.get(script.category, script.category),
            "channel": script.channel,
            "channel_label": CHANNELS.get(script.channel, script.channel),
            "scammer_name": scammer_alias(script),
            "brand": script.brand or "",
        },
        "difficulty": row.difficulty,
        "mode": row.mode,
        "turn_index": row.turn_index,
        "max_turns": max_turns_for(row.difficulty),
        "stage_index": row.stage_index,
        "stages": [
            {"index": index, "intent": step.get("intent") or "", "reached": index <= row.stage_index}
            for index, step in enumerate(steps)
        ],
        "messages": [_message_public(message) for message in row.messages],
        "visible_flags": _visible_flags(row, script),
        "hints_used": row.hints_used,
    }


def _add_message(session, row: TrainingSession, role: str, text: str, stage_index: int, flags: list[int]) -> TrainingMessage:
    message = TrainingMessage(
        id=uuid.uuid4().hex,
        session_id=row.id,
        seq=len(row.messages),
        role=role,
        text=text,
        stage_index=stage_index,
        flags=flags,
        created_at=utcnow(),
    )
    row.messages.append(message)
    return message


def create_training_session(
    session,
    script_id: str | None = None,
    group: str | None = None,
    difficulty: str = "vua",
    mode: str = "thu_thach",
) -> dict:
    if difficulty not in {"de", "vua", "kho"}:
        raise TrainingError(422, "Độ khó không hợp lệ.")
    if mode not in {"hoc", "thu_thach"}:
        raise TrainingError(422, "Chế độ không hợp lệ.")
    script = _pick_script(session, script_id, group)
    steps = scammer_steps(script)
    if not steps:
        raise TrainingError(404, "Kịch bản chưa có lời của người lừa đảo.")
    mapping = stage_flags(script)
    opening = _fallback_line(script, 0)
    row = TrainingSession(
        id=uuid.uuid4().hex,
        script_id=script.id,
        difficulty=difficulty,
        mode=mode,
        status="active",
        end_reason="",
        stage_index=0,
        turn_index=0,
        hints_used=0,
        events=[],
        score=None,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(row)
    session.flush()
    _add_message(session, row, "scammer", opening, 0, list(mapping.get(0) or []))
    session.flush()
    return session_public(row, script)


def _recent(row: TrainingSession) -> list[dict]:
    return [{"role": message.role, "text": message.text} for message in row.messages]


def _end(row: TrainingSession, script: Script, status: str, reason: str) -> None:
    row.status = status
    row.end_reason = reason
    row.score = score_session(row, script)
    row.updated_at = utcnow()


def _decide_end(row: TrainingSession, label: str, text: str) -> tuple[str, str] | None:
    labels = [event.get("label") or "" for event in _events(row)]
    if label == "fell":
        return "scammed", fell_reason(text)
    if _REPORT.search(text or ""):
        return "safe", "report"
    if _BLOCK.search(text or ""):
        return "safe", "hang_up"
    if len(labels) >= 2 and labels[-1] == "refuse" and labels[-2] == "refuse":
        return "safe", "refused"
    if "refuse" in labels and "verify" in labels:
        return "safe", "refused"
    if row.difficulty == "de" and label in {"refuse", "verify"}:
        return "safe", "verify_official" if label == "verify" else "refused"
    if row.turn_index >= max_turns_for(row.difficulty):
        return "timeout", "max_turns"
    return None


def post_training_message(session, provider, session_id: str, text: str) -> dict:
    row = _load(session, session_id)
    if row.status != "active":
        raise TrainingError(409, "Phiên đã kết thúc.")
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise TrainingError(422, "Tin nhắn trống.")
    if len(cleaned) > 500:
        raise TrainingError(422, "Tin nhắn dài quá 500 ký tự.")
    user_count = sum(1 for message in row.messages if message.role == "user")
    if user_count >= MAX_USER_MESSAGES:
        raise TrainingError(429, "Phiên đã đủ số tin cho phép.")
    script = _script(session, row.script_id)
    masked, leaked = mask_user_text(cleaned)
    rule = judge_rules(cleaned)
    mapping = stage_flags(script)
    flag_ids = list(mapping.get(row.stage_index) or [])
    label, caught_ids = _judge(provider, rule, script, row.stage_index, flag_ids, _recent(row), masked)
    row.turn_index += 1
    user_stage = row.stage_index
    _add_message(session, row, "user", masked, user_stage, [])
    event = {
        "turn": row.turn_index,
        "stage_index": user_stage,
        "label": label,
        "caught_flag_ids": [item for item in caught_ids if isinstance(item, int)],
        "leaked": leaked,
        "scammer_flag_ids": flag_ids,
        "reassured": False,
    }
    events = _events(row)
    events.append(event)
    row.events = events
    ending = _decide_end(row, label, cleaned)
    if ending is None and label in {"suspicious", "verify"}:
        used = sum(1 for item in events if item.get("reassured") and item.get("stage_index") == user_stage)
        if used < reassure_budget(row.difficulty):
            event["reassured"] = True
            row.events = events
    if ending is None and not event["reassured"]:
        steps = scammer_steps(script)
        if row.stage_index + 1 < len(steps):
            row.stage_index += 1
    if ending is not None:
        reply = _closing(*ending)
        _end(row, script, *ending)
    else:
        reply = _strip_echo(_scammer_reply(provider, script, row.stage_index, _recent(row), row.difficulty), cleaned)
        if not reply or not scammer_text_safe(reply):
            reply = _fallback_line(script, row.stage_index)
    reply_flags = list(mapping.get(row.stage_index) or [])
    _add_message(session, row, "scammer", reply, row.stage_index, reply_flags)
    row.updated_at = utcnow()
    session.flush()
    revealed = reply_flags if row.mode == "hoc" else []
    return {
        "reply": reply,
        "judgment": {"label": label, "revealed_flags": revealed},
        "session": session_public(row, script),
    }


def post_training_action(session, session_id: str, action: str) -> dict:
    row = _load(session, session_id)
    if row.status != "active":
        raise TrainingError(409, "Phiên đã kết thúc.")
    mapping = {
        "hang_up": ("safe", "hang_up"),
        "verify_official": ("safe", "verify_official"),
        "report": ("safe", "report"),
        "transfer": ("scammed", "transfer"),
        "share_otp": ("scammed", "otp"),
    }
    if action not in mapping:
        raise TrainingError(422, "Hành động không hợp lệ.")
    script = _script(session, row.script_id)
    status, reason = mapping[action]
    if action == "share_otp":
        events = _events(row)
        events.append(
            {
                "turn": row.turn_index,
                "stage_index": row.stage_index,
                "label": "fell",
                "caught_flag_ids": [],
                "leaked": ["otp"],
                "scammer_flag_ids": [],
                "reassured": False,
            }
        )
        row.events = events
    if action == "transfer":
        events = _events(row)
        events.append(
            {
                "turn": row.turn_index,
                "stage_index": row.stage_index,
                "label": "fell",
                "caught_flag_ids": [],
                "leaked": ["account"],
                "scammer_flag_ids": [],
                "reassured": False,
            }
        )
        row.events = events
    reply = _closing(status, reason)
    mapping_flags = stage_flags(script)
    _add_message(session, row, "scammer", reply, row.stage_index, list(mapping_flags.get(row.stage_index) or []))
    _end(row, script, status, reason)
    session.flush()
    return session_public(row, script)


def post_training_hint(session, session_id: str) -> dict:
    row = _load(session, session_id)
    if row.status != "active":
        raise TrainingError(409, "Phiên đã kết thúc.")
    script = _script(session, row.script_id)
    mapping = stage_flags(script)
    flag_ids = list(mapping.get(row.stage_index) or [])
    if flag_ids and flag_ids[0] < len(script.red_flags or []):
        source = script.red_flags[flag_ids[0]]
    else:
        source = script.advice or "Người lạ có đang giục bạn làm ngay không"
    hint = f"Bạn có để ý điều này không: {source.strip().rstrip('.')}?"
    row.hints_used = int(row.hints_used or 0) + 1
    row.updated_at = utcnow()
    session.flush()
    return {"hint": hint, "hints_used": row.hints_used}


def training_debrief(session, session_id: str) -> dict:
    row = _load(session, session_id)
    if row.status == "active":
        raise TrainingError(409, "Phiên chưa kết thúc.")
    script = _script(session, row.script_id)
    outcomes = _stage_outcomes(row, script)
    mapping = stage_flags(script)
    flags = []
    for item in outcomes:
        if item["outcome"] == "not_reached":
            continue
        messages = [message.text for message in row.messages if message.role == "scammer" and message.stage_index == item["index"]]
        quote = (messages[-1] if messages else "")[:160]
        for flag_id in mapping.get(item["index"]) or []:
            if flag_id >= len(script.red_flags or []):
                continue
            flags.append(
                {
                    "text": script.red_flags[flag_id],
                    "stage_index": item["index"],
                    "quote": quote,
                    "caught": item["outcome"] == "caught",
                }
            )
    tips: list[str] = []
    for flag in script.red_flags or []:
        if flag not in tips:
            tips.append(flag)
        if len(tips) >= 2:
            break
    if script.advice and script.advice not in tips:
        tips.append(script.advice)
    while len(tips) < 3:
        tips.append("Không chuyển tiền, không đọc mã OTP, không cài ứng dụng theo lời người lạ.")
    stopped = next((item["intent"] for item in outcomes if item["outcome"] == "not_reached"), "")
    duration = 0
    if row.updated_at and row.created_at:
        duration = max(0, int((row.updated_at - row.created_at).total_seconds()))
    score = row.score if row.score is not None else score_session(row, script)
    return {
        "score": score,
        "label": score_label(score),
        "status": row.status,
        "end_reason": row.end_reason,
        "turns": row.turn_index,
        "duration_s": duration,
        "stopped_before": stopped,
        "stages": outcomes,
        "flags": flags,
        "leaked": _leak_kinds(row),
        "tips": tips[:3],
        "warning_card_ids": [card["id"] for card in cards_for_category(script.category)[:4]],
        "hints_used": row.hints_used,
        "script": {
            "id": script.id,
            "title": script.title,
            "occurrence_count": script.occurrence_count,
            "last_seen": script.last_seen.isoformat() if script.last_seen else "",
            "sources": script.sources or [],
        },
    }


def build_quiz(session, n: int = 8) -> dict:
    count = max(1, min(int(n or 8), 20))
    scam_n = max(1, round(count * 0.6)) if count > 1 else 1
    safe_n = count - scam_n
    if count > 1 and safe_n < 1:
        safe_n = 1
        scam_n = count - 1
    rng = random.Random()
    scripts = [script for script in _published(session) if scammer_steps(script)]
    rng.shuffle(scripts)
    questions: list[dict] = []
    for script in scripts:
        if sum(1 for item in questions if item["answer"] == "scam") >= scam_n:
            break
        cleaned = ""
        for step in scammer_steps(script):
            for phrase in step.get("phrases") or []:
                candidate = sanitize_scammer_text(str(phrase))
                if candidate and scammer_text_safe(candidate):
                    cleaned = candidate
                    break
            if cleaned:
                break
        if not cleaned:
            continue
        explain = (script.red_flags or [script.advice or "Đây là lời của kịch bản lừa đảo đã ghi nhận."])[0]
        questions.append(
            {
                "id": f"scam-{script.id}",
                "text": cleaned[:350],
                "channel": script.channel,
                "answer": "scam",
                "explain": explain,
                "script_id": script.id,
            }
        )
    pool = list(SAFE_MESSAGES)
    rng.shuffle(pool)
    safe_added = 0
    for index, item in enumerate(pool):
        if safe_added >= safe_n:
            break
        if not scammer_text_safe(item["text"]):
            continue
        questions.append(
            {
                "id": f"safe-{index}",
                "text": item["text"],
                "channel": item["channel"],
                "answer": "safe",
                "explain": item["explain"],
                "script_id": None,
            }
        )
        safe_added += 1
    rng.shuffle(questions)
    return {"questions": questions[:count]}
