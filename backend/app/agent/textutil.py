"""Lightweight Vietnamese text helpers. No NLP dependency on the request path."""

import re
import unicodedata

_STOP_RAW = {
    "tôi", "bạn", "anh", "chị", "bác", "là", "của", "và", "cho", "một", "các", "đang",
    "này", "có", "không", "được", "để", "em", "cô", "cháu", "với", "thì", "nhưng",
    "nha", "ơi", "ạ", "đã", "vâng", "mình", "tui", "rồi", "nhé", "ah", "thế", "sao",
    "gì", "nào", "khi", "trong", "trên", "dưới", "ra", "vào", "đến", "bị", "sẽ",
    "qua", "lại", "nếu", "mà", "hay", "hoặc", "ko", "dc",
}

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def fold(text: str) -> str:
    text = (text or "").lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def tokenize(text: str) -> set[str]:
    raw = fold(_PUNCT.sub(" ", text or ""))
    stop = {fold(word) for word in _STOP_RAW}
    return {tok for tok in raw.split() if len(tok) > 1 and tok not in stop}


def contains_phrase(text: str, phrase: str) -> bool:
    hay = fold(text or "")
    needle = fold(phrase or "").strip()
    if not needle:
        return False
    if " " in needle or len(needle) >= 5:
        return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay) is not None
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay) is not None


def digit_runs(text: str) -> list[str]:
    found = re.findall(r"\d(?:[\d\s.]{3,}\d)", text or "")
    cleaned = []
    for item in found:
        digits = re.sub(r"\D", "", item)
        if len(digits) >= 6:
            cleaned.append(digits)
    return cleaned


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))
