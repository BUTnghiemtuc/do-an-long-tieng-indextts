"""Các khối bảo mật dùng chung: băm mật khẩu, token, giới hạn tần suất, CSRF, header HTTP.

Chỉ dùng thư viện chuẩn:
- Mật khẩu băm bằng scrypt (hashlib), muối ngẫu nhiên 16 byte, so sánh hằng thời gian.
- Phiên đăng nhập là token ngẫu nhiên 256 bit trong cookie HttpOnly; CSDL chỉ giữ sha256(token),
  nên lộ file CSDL cũng không dùng được để đăng nhập.
- CSRF kiểu double-submit: cookie `vidub_csrf` (JS đọc được) phải trùng header `X-CSRF-Token`
  ở mọi request ghi (POST/PATCH/PUT/DELETE) vào /api.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

SESSION_COOKIE = "vidub_session"
CSRF_COOKIE = "vidub_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# ---------------------------------------------------------------- mật khẩu
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=64 * 2 ** 20, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        expect = base64.b64decode(dk)
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             maxmem=64 * 2 ** 20, dklen=len(expect))
        return hmac.compare_digest(got, expect)
    except (ValueError, TypeError):
        return False


# Băm sẵn một mật khẩu giả: khi email không tồn tại vẫn tốn thời gian như khi sai mật khẩu,
# để không đoán được email nào đã đăng ký qua thời gian phản hồi.
DUMMY_HASH = hash_password(secrets.token_urlsafe(12))

COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "password1", "password123", "qwerty123",
    "abc12345", "11111111", "iloveyou1", "matkhau123", "admin123", "admin1234", "vidub123",
}


def password_problems(password: str, email: str = "") -> list[str]:
    """Trả về danh sách lý do mật khẩu chưa đạt (rỗng = đạt)."""
    out = []
    if len(password) < 8:
        out.append("ít nhất 8 ký tự")
    if len(password) > 128:
        out.append("tối đa 128 ký tự")
    if not re.search(r"[A-Za-zÀ-ỹ]", password) or not re.search(r"\d", password):
        out.append("có cả chữ và số")
    if password.lower() in COMMON_PASSWORDS:
        out.append("không dùng mật khẩu quá phổ biến")
    local = email.split("@")[0].lower()
    if len(local) >= 4 and local in password.lower():
        out.append("không chứa tên email")
    return out


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def temp_password() -> str:
    """Mật khẩu tạm dễ đọc (không có ký tự dễ nhầm), luôn đạt chính sách."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(8)) + "-" + "".join(secrets.choice("23456789") for _ in range(4))


EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ---------------------------------------------------------------- giới hạn tần suất
class RateLimiter:
    """Cửa sổ trượt trong bộ nhớ: tối đa `limit` lần trong `window` giây cho mỗi khoá.

    Đủ cho API chạy một tiến trình. Chạy nhiều tiến trình thì cần chuyển sang Redis.
    """

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, q: deque[float], now: float) -> None:
        while q and now - q[0] > self.window:
            q.popleft()

    def retry_after(self, key: str) -> int:
        """Số giây phải chờ nếu khoá đang bị chặn, 0 nếu được phép."""
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return 0
            self._trim(q, now)
            return int(self.window - (now - q[0])) + 1 if len(q) >= self.limit else 0

    def hit(self, key: str) -> None:
        with self._lock:
            self._hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


login_failures = RateLimiter(limit=5, window=15 * 60)     # 5 lần sai / 15 phút (theo email và theo IP)
register_limiter = RateLimiter(limit=10, window=60 * 60)  # 10 tài khoản / giờ / IP


def client_ip(request: Request) -> str:
    if os.environ.get("VIDUB_TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def secure_cookies(request: Request) -> bool:
    return os.environ.get("VIDUB_SECURE_COOKIE") == "1" or request.url.scheme == "https"


# ---------------------------------------------------------------- middleware
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",      # Motion/Sonner đặt style inline
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


async def security_middleware(request: Request, call_next):
    path = request.url.path
    cookie = request.cookies.get(CSRF_COOKIE)

    if path.startswith("/api/") and request.method not in SAFE_METHODS:
        header = request.headers.get(CSRF_HEADER, "")
        if not cookie or not hmac.compare_digest(cookie, header):
            return JSONResponse({"detail": "Thiếu hoặc sai mã CSRF, tải lại trang rồi thử lại"}, status_code=403)

    response = await call_next(request)

    if not cookie:
        response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(24), samesite="strict",
                            secure=secure_cookies(request), path="/")
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "same-origin")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if not path.startswith("/api/"):
        h.setdefault("Content-Security-Policy", CSP)
    elif "/files/" not in path and not path.endswith("/source"):
        h.setdefault("Cache-Control", "no-store")   # JSON có dữ liệu riêng tư; media thì để trình duyệt cache
    if secure_cookies(request):
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
