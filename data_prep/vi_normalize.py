"""Chuẩn hoá văn bản tiếng Việt cho TTS: số, ngày, giờ, phần trăm, đơn vị, ký hiệu.

Đây là bộ chuẩn hoá tối thiểu tự viết, không phụ thuộc thư viện ngoài. Kế hoạch đề
xuất VietNormalizer (xử lý thêm viết tắt, từ tiếng Anh xen lẫn); khi dùng, cắm vào
`normalize()` và GIỮ NGUYÊN hàm đó ở cả lúc train lẫn lúc suy luận.
"""

from __future__ import annotations

import re
import unicodedata

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
UNITS = {"km": "ki lô mét", "m": "mét", "cm": "xen ti mét", "mm": "mi li mét", "kg": "ki lô gam",
         "g": "gam", "h": "giờ", "s": "giây", "°c": "độ xê", "km/h": "ki lô mét trên giờ",
         "đ": "đồng", "vnđ": "việt nam đồng", "usd": "đô la mỹ"}
SYMBOLS = {"&": " và ", "+": " cộng ", "=": " bằng ", "@": " a còng ", "#": " thăng "}


def _three(n: int, full: bool) -> str:
    """Đọc số 0..999. full=True: đọc đủ 'không trăm' khi đứng sau nhóm lớn hơn."""
    h, t, u = n // 100, (n // 10) % 10, n % 10
    words = []
    if h or full:
        words += [DIGITS[h], "trăm"]
    if t == 0:
        if u and (h or full):
            words.append("lẻ")
    elif t == 1:
        words.append("mười")
    else:
        words += [DIGITS[t], "mươi"]
    if u:
        if u == 1 and t >= 2:
            words.append("mốt")
        elif u == 5 and t >= 1:
            words.append("lăm")
        elif u == 4 and t >= 2:
            words.append("tư")
        else:
            words.append(DIGITS[u])
    return " ".join(words)


def _below_billion(n: int, full: bool) -> str:
    words, started = [], full
    for g, scale in ((n // 1_000_000, "triệu"), ((n // 1000) % 1000, "nghìn"), (n % 1000, "")):
        if g == 0:
            continue
        words.append(_three(g, full=started))
        if scale:
            words.append(scale)
        started = True
    return " ".join(words)


def number_to_words(n: int) -> str:
    """1_000_005 -> 'một triệu không trăm lẻ năm'; 21 -> 'hai mươi mốt'."""
    if n == 0:
        return "không"
    if n < 0:
        return "âm " + number_to_words(-n)
    if n >= 1_000_000_000:
        hi, lo = divmod(n, 1_000_000_000)
        out = number_to_words(hi) + " tỷ"
        return out + (" " + _below_billion(lo, full=True) if lo else "")
    return _below_billion(n, full=False)


def _read_digits(s: str) -> str:
    return " ".join(DIGITS[int(c)] for c in s)


def _num(m: re.Match) -> str:
    return _num_str(m.group(0))


def _num_str(s: str) -> str:
    if re.fullmatch(r"0\d+", s):                     # số điện thoại, mã: đọc từng chữ số
        return _read_digits(s)
    if "," in s and re.fullmatch(r"\d+,\d+", s):      # thập phân kiểu Việt: 3,5
        a, b = s.split(",")
        return f"{number_to_words(int(a))} phẩy {_read_digits(b) if b.startswith('0') else number_to_words(int(b))}"
    return number_to_words(int(s.replace(".", "")))


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # ngày tháng năm
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
                  lambda m: f"ngày {number_to_words(int(m[1]))} tháng {number_to_words(int(m[2]))} năm {number_to_words(int(m[3]))}", text)
    text = re.sub(r"\b(\d{1,2})/(\d{4})\b",
                  lambda m: f"tháng {number_to_words(int(m[1]))} năm {number_to_words(int(m[2]))}", text)
    text = re.sub(r"\b(ngày|tháng)\s+(?:ngày|tháng)\b", r"\1", text, flags=re.IGNORECASE)  # "ngày 25/11" -> không lặp
    # giờ
    text = re.sub(r"\b(\d{1,2})[h:](\d{2})\b",
                  lambda m: f"{number_to_words(int(m[1]))} giờ {number_to_words(int(m[2]))} phút", text)
    # phần trăm
    text = re.sub(r"(\d+(?:,\d+)?)\s?%", lambda m: _num_str(m[1]) + " phần trăm", text)
    # đơn vị đi sau số
    unit_re = "|".join(sorted(map(re.escape, UNITS), key=len, reverse=True))
    text = re.sub(rf"(\d+(?:[.,]\d+)?)\s?({unit_re})\b", lambda m: f"{m[1]} {UNITS[m[2].lower()]}", text,
                  flags=re.IGNORECASE)
    # số: 1.000.000 / 3,5 / 2024
    text = re.sub(r"\d{1,3}(?:\.\d{3})+(?!\d)|\d+,\d+|\d+", _num, text)
    for k, v in SYMBOLS.items():
        text = text.replace(k, v)
    text = re.sub(r"[\"“”«»\[\](){}]", "", text)
    text = re.sub(r"\s*([,.!?;:…])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


if __name__ == "__main__":
    import sys

    for line in sys.stdin:
        print(normalize(line))
