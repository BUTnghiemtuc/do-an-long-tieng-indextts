"""Xử lý văn bản: đếm âm tiết tiếng Việt, cắt câu từ timestamp mức từ."""

from __future__ import annotations

import re
import unicodedata

_PUNCT_END = re.compile(r"[.!?…]+[\"')\]]*$")
_TOKEN = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
_EN_VOWEL_GROUPS = re.compile(r"[aeiouy]+")


def vi_syllables(text: str) -> int:
    """Tiếng Việt viết tách âm tiết bằng khoảng trắng, nên đếm token chữ là đủ.

    Số viết bằng chữ số được tính theo số chữ số (gần đúng: "2024" đọc ~ 5-6 âm tiết).
    """
    n = 0
    for tok in _TOKEN.findall(text):
        if tok.isdigit():
            n += max(1, len(tok) + (len(tok) - 1) // 2)
        else:
            n += 1
    return n


def en_syllables(text: str) -> int:
    """Ước lượng thô số âm tiết tiếng Anh (đếm cụm nguyên âm)."""
    total = 0
    for word in re.findall(r"[a-zA-Z']+", text.lower()):
        groups = len(_EN_VOWEL_GROUPS.findall(word))
        if word.endswith("e") and groups > 1 and not word.endswith(("le", "ee")):
            groups -= 1
        total += max(1, groups)
    return total


def syllable_budget(duration: float, syllables_per_sec: float) -> int:
    return max(1, int(round(duration * syllables_per_sec)))


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def ends_sentence(word: str) -> bool:
    return bool(_PUNCT_END.search(word.strip()))


def split_sentences(words: list[dict], pause_split: float = 0.6, max_dur: float = 12.0) -> list[list[dict]]:
    """Gom các từ {start, end, text} thành câu.

    Ngắt khi: hết câu (dấu câu), khoảng lặng >= pause_split, hoặc câu dài hơn max_dur
    (khi đó ngắt tại khoảng lặng lớn nhất bên trong).
    """
    sentences: list[list[dict]] = []
    cur: list[dict] = []
    for i, w in enumerate(words):
        if cur and w["start"] - cur[-1]["end"] >= pause_split:
            sentences.append(cur)
            cur = []
        cur.append(w)
        if ends_sentence(w["text"]):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)

    out: list[list[dict]] = []
    stack = list(reversed(sentences))
    while stack:
        s = stack.pop()
        if s[-1]["end"] - s[0]["start"] <= max_dur or len(s) < 2:
            out.append(s)
            continue
        gaps = [s[i + 1]["start"] - s[i]["end"] for i in range(len(s) - 1)]
        k = max(range(len(gaps)), key=gaps.__getitem__) + 1
        stack.extend([s[k:], s[:k]])
    return out


def join_words(words: list[dict]) -> str:
    text = " ".join(w["text"].strip() for w in words)
    return re.sub(r"\s+([,.!?;:…])", r"\1", text).strip()
