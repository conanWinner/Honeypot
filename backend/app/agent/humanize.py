"""Make the persona's messages read like a person texting, not an assistant.

Sources for the tells and the fixes:
- Jones & Bergen, Turing test studies (arXiv 2405.08007, 2503.23674): judges caught
  AIs mostly by style: too formal, too tidy, too long, templated, over-polite,
  answering every question with a question. Lowercase, sparse punctuation, short
  messages and admitted ignorance read as human.
- tejash-sr/scambait-ai-honeypot: a post-processing guard that strips assistant
  phrasing and caps length; its word lists are English, so these are Vietnamese.
- ViLexNorm (arXiv 2401.16403): the most varied words in Vietnamese social text are
  không, rồi, vậy, quá, thôi, ơi, which is where people abbreviate.

Two parts: `ai_tells` measures (used by critique and eval), `humanize` applies
small deterministic edits to a reply that already passed the safety gate. The
edits never add meaning and never touch digits.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from app.data.personas import PRONOUNS, STYLES

_ADDRESS = r"(?:anh|chị|em|cô|chú|bác|cháu|bạn)"
_SLASH = re.compile(rf"\b({_ADDRESS})\s*/\s*({_ADDRESS})\b", re.IGNORECASE)
_FORMAL = re.compile(
    r"(?<!\w)(ngoài ra|tuy nhiên|bên cạnh đó|do đó|hơn nữa|cụ thể là|xin lưu ý|lưu ý rằng|vui lòng|quý khách|"
    r"xin cảm ơn|cảm ơn (?:anh|chị|bạn) đã|rất tiếc|xin lỗi vì sự bất tiện|tôi hiểu rằng|"
    r"hãy cho (?:tôi|em|cô|chú|tui) biết|trân trọng|kính gửi)(?!\w)",
    re.IGNORECASE,
)
# Desk words: fine from an office worker, odd from a grandmother or a driver.
_BUREAU = re.compile(r"(?<!\w)(cung cấp|thực hiện|thao tác|nội dung|xác minh|đơn vị nào|yêu cầu này)(?!\w)", re.IGNORECASE)
_DISCLAIMER = re.compile(
    r"(?<!\w)chưa\s+(?:chuyển|ck|bấm|cài|làm|trả|thao tác|xác nhận|mở|đọc)(?!\w)",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")


def _sentences(text: str) -> list[str]:
    return [piece.strip() for piece in _SENTENCE.findall(text or "") if piece.strip()]


def style_of(persona_id: str) -> dict:
    return STYLES.get(persona_id) or STYLES["tuan-vp"]


def ai_tells(text: str, recent: list[str] | None = None, persona_id: str = "", incoming: str = "") -> list[str]:
    """Style tells that make a reply read as machine-written."""
    body = (text or "").strip()
    if not body:
        return []
    style = style_of(persona_id)
    tells: list[str] = []
    if _SLASH.search(body):
        tells.append("slash_address")
    if _FORMAL.search(body):
        tells.append("formal_phrase")
    if not style.get("desk_words") and _BUREAU.search(body):
        tells.append("desk_words")
    if len(body) > int(style.get("max_chars", 140)):
        tells.append("too_long")
    if _DISCLAIMER.search(body) and any(_DISCLAIMER.search(old or "") for old in (recent or [])[-2:]):
        tells.append("repeated_disclaimer")
    if style.get("case") == "lower" and re.match(r"^[A-ZÀ-Ỹ]", body) and body.endswith("."):
        tells.append("too_tidy")
    sentences = _sentences(body)
    if "?" in (incoming or "") and sentences and all(item.endswith("?") for item in sentences) and len(sentences) >= 2:
        tells.append("question_wall")
    return tells


def _rng(*parts: str) -> float:
    """Deterministic 0..1 from the conversation and turn, so tests and replays agree."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


def _strip_marks(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return unicodedata.normalize("NFC", "".join(ch for ch in text if unicodedata.category(ch) != "Mn"))


def _drop_repeated_disclaimer(text: str, recent: list[str] | None) -> str:
    """Saying "I haven't paid" in every message is the loudest tell. Keep it once in a while."""
    if not any(_DISCLAIMER.search(old or "") for old in (recent or [])[-2:]):
        return text
    sentences = _sentences(text)
    if len(sentences) < 2:
        return text
    kept = []
    for sentence in sentences:
        words = re.sub(r"[^\w\s]", " ", sentence).split()
        # Only a sentence that is nothing but the disclaimer: "Em chưa chuyển đâu."
        if _DISCLAIMER.search(sentence) and len(words) <= 6 and "?" not in sentence:
            continue
        kept.append(sentence)
    return " ".join(kept) if kept else text


def _abbreviate(text: str, table: dict[str, str], roll: float) -> str:
    if not table:
        return text
    out = text
    for index, (word, short) in enumerate(table.items()):
        # Not every word, every time: people are inconsistent.
        if (roll * (index + 3)) % 1 < 0.7:
            out = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", short, out, flags=re.IGNORECASE)
    return out


def humanize(text: str, persona_id: str, recent: list[str] | None = None, seed: str = "", address: str = "") -> str:
    """Small edits toward how this persona types. Digits and meaning stay as they are."""
    body = (text or "").strip()
    if not body:
        return body
    style = style_of(persona_id)
    other = address or ((PRONOUNS.get(persona_id) or {}).get("other") or ["anh"])[0]

    def pick(match: re.Match) -> str:
        word = other if other.lower() in {match.group(1).lower(), match.group(2).lower()} else match.group(1)
        return word.capitalize() if match.group(0)[0].isupper() else word.lower()

    body = _SLASH.sub(pick, body)
    body = _drop_repeated_disclaimer(body, recent)
    roll = _rng(seed, persona_id, body[:24])
    body = _abbreviate(body, style.get("abbrev") or {}, roll)
    if style.get("case") == "lower":
        body = body[:1].lower() + body[1:]
        body = re.sub(r"([.!?]\s+)([A-ZÀ-Ỹ])", lambda m: m.group(1) + m.group(2).lower(), body)
    if style.get("drop_final_period") and body.endswith(".") and not body.endswith(".."):
        body = body[:-1]
    if style.get("ellipsis") and roll < 0.35 and body.endswith(".") and not body.endswith(".."):
        body = body[:-1] + "..."
    # Models already write "..." for this kind of persona; never stack more dots.
    body = re.sub(r"\.{4,}", "...", body)
    # Diacritics depend on the keyboard someone has set up, so decide once per
    # conversation, not per message: flipping between the two looks scripted.
    conversation = (seed or "").split(":", 1)[0]
    if _rng(conversation, persona_id, "marks") < float(style.get("strip_marks", 0)):
        body = _strip_marks(body)
    return re.sub(r"\s{2,}", " ", body).strip()


def typing_delay_ms(reply: str, incoming: str, persona_id: str, seed: str = "") -> int:
    """Reading plus typing time, after Jones & Bergen: a floor, per-character typing,
    a little per-character reading, and a right-skewed pause for thinking."""
    style = style_of(persona_id)
    per_char = float(style.get("ms_per_char", 45))
    roll = _rng(seed, "delay", reply[:16])
    thinking = 400 + int(1600 * roll * roll)
    total = 900 + per_char * len(reply or "") + 12 * len(incoming or "") + thinking
    return int(max(1200, min(9000, total)))
