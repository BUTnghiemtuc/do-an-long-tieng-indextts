"""Đăng nhập, đăng ký, phiên làm việc và các dependency kiểm tra quyền.

Luồng khởi tạo: khi CSDL chưa có người dùng nào, trang /#/setup cho tạo tài khoản quản trị
đầu tiên. Việc này cần mã khởi tạo (in ra log lúc server khởi động, hoặc đặt qua biến môi
trường VIDUB_SETUP_TOKEN) để người lạ truy cập trước không chiếm được quyền admin.
Cũng có thể tạo admin bằng dòng lệnh: python -m server.manage create-admin.
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import db
from .security import (DUMMY_HASH, EMAIL_RE, SESSION_COOKIE, client_ip, hash_password, login_failures,
                       new_token, normalize_email, password_problems, register_limiter, secure_cookies,
                       token_hash, verify_password)

log = logging.getLogger("vidub.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

_setup_token: str | None = None


def setup_token() -> str:
    global _setup_token
    env = os.environ.get("VIDUB_SETUP_TOKEN")
    if env:
        return env
    if _setup_token is None:
        _setup_token = secrets.token_urlsafe(12)
    return _setup_token


def user_count() -> int:
    with db.connect() as con:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def public_user(u: dict) -> dict:
    return {k: u[k] for k in ("id", "email", "name", "role", "active", "must_change_password", "created_at", "last_login_at")}


# ---------------------------------------------------------------- người dùng & phiên
def create_user(email: str, name: str, password: str, role: str = "user", must_change: bool = False) -> dict:
    email = normalize_email(email)
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Email không hợp lệ")
    name = name.strip()[:80] or email.split("@")[0]
    problems = password_problems(password, email)
    if problems:
        raise HTTPException(400, "Mật khẩu cần " + ", ".join(problems))
    with db.connect() as con:
        if con.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "Email này đã có tài khoản")
        cur = con.execute(
            "INSERT INTO users(email, name, password_hash, role, must_change_password, created_at) VALUES(?,?,?,?,?,?)",
            (email, name, hash_password(password), role, int(must_change), time.time()))
        return db.row(con.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


def start_session(request: Request, response: Response, user: dict, remember: bool) -> None:
    s = db.get_settings()
    ttl = s["remember_days"] * 86400 if remember else s["session_hours"] * 3600
    token, now = new_token(), time.time()
    with db.connect() as con:
        con.execute("INSERT INTO sessions(token_hash, user_id, created_at, expires_at, last_seen_at, ip, user_agent) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (token_hash(token), user["id"], now, now + ttl, now, client_ip(request),
                     (request.headers.get("user-agent") or "")[:300]))
        con.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, user["id"]))
        con.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=secure_cookies(request),
                        path="/", max_age=int(ttl) if remember else None)


def revoke_sessions(user_id: int, keep: str | None = None) -> int:
    with db.connect() as con:
        if keep:
            return con.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user_id, keep)).rowcount
        return con.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,)).rowcount


def _session_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Chưa đăng nhập")
    th, now = token_hash(token), time.time()
    with db.connect() as con:
        r = con.execute(
            "SELECT u.*, s.token_hash AS session_hash, s.last_seen_at AS session_seen FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?", (th, now)).fetchone()
        if r is None:
            raise HTTPException(401, "Phiên đăng nhập đã hết hạn")
        if not r["active"]:
            con.execute("DELETE FROM sessions WHERE user_id = ?", (r["id"],))
            raise HTTPException(401, "Tài khoản đã bị khoá")
        if now - r["session_seen"] > 60:  # không ghi CSDL ở mọi request
            con.execute("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?", (now, th))
    user = dict(r)
    request.state.user = user
    return user


def any_user(request: Request) -> dict:
    """Đã đăng nhập (kể cả khi đang bị buộc đổi mật khẩu)."""
    return _session_user(request)


def current_user(request: Request) -> dict:
    """Đã đăng nhập và không còn bị buộc đổi mật khẩu."""
    user = _session_user(request)
    if user["must_change_password"]:
        raise HTTPException(403, "Cần đổi mật khẩu tạm trước khi tiếp tục")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Chỉ quản trị viên được dùng chức năng này")
    return user


# ---------------------------------------------------------------- API
class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)
    remember: bool = False


class Registration(BaseModel):
    email: str = Field(max_length=320)
    name: str = Field("", max_length=80)
    password: str = Field(max_length=256)


class Setup(Registration):
    token: str = Field(max_length=200)


@router.get("/status")
def status(request: Request):
    """Trạng thái công khai + người dùng hiện tại (null nếu chưa đăng nhập), để giao diện không phải gọi /me."""
    try:
        user = me(_session_user(request))
    except HTTPException:
        user = None
    return {"setup_required": user_count() == 0, "allow_registration": db.setting("allow_registration"), "user": user}


@router.post("/setup")
def setup(body: Setup, request: Request, response: Response):
    if user_count() > 0:
        raise HTTPException(409, "Hệ thống đã được khởi tạo")
    if not hmac.compare_digest(body.token.strip(), setup_token()):
        db.audit("setup_failed", ip=client_ip(request))
        raise HTTPException(403, "Mã khởi tạo không đúng (xem log của server)")
    user = create_user(body.email, body.name, body.password, role="admin")
    db.audit("setup", user=user, ip=client_ip(request))
    start_session(request, response, user, remember=False)
    return public_user(user)


@router.post("/register")
def register(body: Registration, request: Request, response: Response):
    if not db.setting("allow_registration"):
        raise HTTPException(403, "Quản trị viên đã tắt đăng ký. Liên hệ để được cấp tài khoản.")
    ip = client_ip(request)
    wait = register_limiter.retry_after(ip)
    if wait:
        raise HTTPException(429, f"Đăng ký quá nhiều, thử lại sau {wait // 60 + 1} phút", headers={"Retry-After": str(wait)})
    register_limiter.hit(ip)
    user = create_user(body.email, body.name, body.password)
    db.audit("register", user=user, ip=ip)
    start_session(request, response, user, remember=False)
    return public_user(user)


@router.post("/login")
def login(body: Credentials, request: Request, response: Response):
    email, ip = normalize_email(body.email), client_ip(request)
    wait = max(login_failures.retry_after(f"email:{email}"), login_failures.retry_after(f"ip:{ip}"))
    if wait:
        raise HTTPException(429, f"Sai quá nhiều lần, thử lại sau {wait // 60 + 1} phút", headers={"Retry-After": str(wait)})
    with db.connect() as con:
        user = db.row(con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())
    ok = verify_password(body.password, user["password_hash"] if user else DUMMY_HASH)
    if not user or not ok:
        login_failures.hit(f"email:{email}")
        login_failures.hit(f"ip:{ip}")
        db.audit("login_failed", target=email, ip=ip)
        # Cùng một thông báo cho cả "không có email" lẫn "sai mật khẩu" để không lộ email nào tồn tại.
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    if not user["active"]:
        # Chỉ người biết đúng mật khẩu mới thấy thông báo này.
        db.audit("login_blocked", user=user, ip=ip)
        raise HTTPException(403, "Tài khoản đã bị khoá, liên hệ quản trị viên")
    login_failures.reset(f"email:{email}")
    start_session(request, response, user, body.remember)
    db.audit("login", user=user, ip=ip)
    return public_user(user)


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with db.connect() as con:
            r = con.execute("SELECT u.id, u.email FROM sessions s JOIN users u ON u.id = s.user_id "
                            "WHERE s.token_hash = ?", (token_hash(token),)).fetchone()
            con.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
        if r:
            db.audit("logout", user=dict(r), ip=client_ip(request))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(any_user)):
    s = db.get_settings()
    return {**public_user(user), "limits": {"max_upload_mb": s["max_upload_mb"], "max_active_jobs": s["max_active_jobs"]}}


class ProfilePatch(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.patch("/me")
def update_me(body: ProfilePatch, user: dict = Depends(current_user)):
    with db.connect() as con:
        con.execute("UPDATE users SET name = ? WHERE id = ?", (body.name.strip(), user["id"]))
    return me({**user, "name": body.name.strip()})


class PasswordChange(BaseModel):
    current: str = Field(max_length=256)
    new: str = Field(max_length=256)


@router.post("/password")
def change_password(body: PasswordChange, request: Request, user: dict = Depends(any_user)):
    if not verify_password(body.current, user["password_hash"]):
        db.audit("password_change_failed", user=user, ip=client_ip(request))
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    if body.new == body.current:
        raise HTTPException(400, "Mật khẩu mới phải khác mật khẩu cũ")
    problems = password_problems(body.new, user["email"])
    if problems:
        raise HTTPException(400, "Mật khẩu cần " + ", ".join(problems))
    with db.connect() as con:
        con.execute("UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                    (hash_password(body.new), user["id"]))
    n = revoke_sessions(user["id"], keep=user["session_hash"])
    db.audit("password_change", user=user, ip=client_ip(request), detail={"revoked_sessions": n})
    return {"ok": True, "revoked_sessions": n}


@router.get("/sessions")
def my_sessions(user: dict = Depends(current_user)):
    with db.connect() as con:
        rows = con.execute("SELECT rowid AS id, token_hash, created_at, last_seen_at, expires_at, ip, user_agent "
                           "FROM sessions WHERE user_id = ? AND expires_at > ? ORDER BY last_seen_at DESC",
                           (user["id"], time.time())).fetchall()
    return [{**{k: r[k] for k in r.keys() if k != "token_hash"}, "current": r["token_hash"] == user["session_hash"]}
            for r in rows]


@router.delete("/sessions/{sid}")
def revoke_session(sid: int, request: Request, user: dict = Depends(current_user)):
    with db.connect() as con:
        n = con.execute("DELETE FROM sessions WHERE rowid = ? AND user_id = ?", (sid, user["id"])).rowcount
    if not n:
        raise HTTPException(404, "Không có phiên này")
    db.audit("session_revoke", user=user, ip=client_ip(request), target=str(sid))
    return {"ok": True}


@router.post("/sessions/revoke-others")
def revoke_others(request: Request, user: dict = Depends(current_user)):
    n = revoke_sessions(user["id"], keep=user["session_hash"])
    db.audit("session_revoke_others", user=user, ip=client_ip(request), detail={"count": n})
    return {"ok": True, "revoked": n}
