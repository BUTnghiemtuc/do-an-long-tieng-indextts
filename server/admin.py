"""API trang quản trị: tổng quan hệ thống, người dùng, toàn bộ job, nhật ký, cài đặt."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import db
from .auth import create_user, public_user, require_admin, revoke_sessions
from . import jobs as joblib
from .jobs import dir_size, list_job_dirs, read_status
from .security import client_ip, hash_password, temp_password

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_gpu_cache: tuple[float, list | None] = (0.0, None)


def gpu_info() -> list[dict] | None:
    """Đọc nvidia-smi (cache 10 s). Máy không có GPU NVIDIA thì trả None."""
    global _gpu_cache
    if time.time() - _gpu_cache[0] < 10:
        return _gpu_cache[1]
    out = None
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
            out = []
            for line in res.stdout.strip().splitlines():
                name, used, total, util, temp = [x.strip() for x in line.split(",")]
                out.append({"name": name, "mem_used_mb": int(used), "mem_total_mb": int(total),
                            "util": int(util), "temp": int(temp)})
        except (subprocess.SubprocessError, ValueError):
            out = None
    _gpu_cache = (time.time(), out)
    return out


def all_jobs() -> list[dict]:
    """Mọi job trên đĩa, ghép với chủ sở hữu trong CSDL (job cũ chưa có chủ thì owner = None)."""
    with db.connect() as con:
        meta = {r["id"]: dict(r) for r in con.execute(
            "SELECT j.*, u.email AS owner_email, u.name AS owner_name FROM jobs j LEFT JOIN users u ON u.id = j.owner_id")}
    out = []
    for d in list_job_dirs():
        st = read_status(d.name)
        m = meta.get(d.name, {})
        created = m.get("created_at")
        if created is None:
            try:
                created = datetime.strptime(d.name[:15], "%Y%m%d-%H%M%S").timestamp()
            except ValueError:
                created = d.stat().st_mtime
        out.append({"id": d.name, "filename": m.get("filename") or st.get("filename"), "state": st.get("state"),
                    "step": st.get("step"), "error": st.get("error"), "owner_id": m.get("owner_id"),
                    "owner_email": m.get("owner_email"), "owner_name": m.get("owner_name"),
                    "created_at": created, "size_bytes": dir_size(d)})
    return out


@router.get("/overview")
def overview():
    jobs = all_jobs()
    now = time.time()
    with db.connect() as con:
        users = con.execute("SELECT COUNT(*), SUM(role = 'admin'), SUM(active = 0) FROM users").fetchone()
        sessions = con.execute("SELECT COUNT(DISTINCT user_id) FROM sessions WHERE expires_at > ? AND last_seen_at > ?",
                               (now, now - 900)).fetchone()[0]
        failed = con.execute("SELECT COUNT(*) FROM audit WHERE action = 'login_failed' AND ts > ?", (now - 86400,)).fetchone()[0]
        recent = [dict(r) for r in con.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 8")]
    by_state: dict[str, int] = {}
    for j in jobs:
        by_state[j["state"] or "unknown"] = by_state.get(j["state"] or "unknown", 0) + 1
    # Số job tạo mỗi ngày trong 14 ngày gần nhất
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    days = {datetime.fromtimestamp(today - i * 86400 + 3600).strftime("%Y-%m-%d"): 0 for i in range(13, -1, -1)}
    for j in jobs:
        day = datetime.fromtimestamp(j["created_at"]).strftime("%Y-%m-%d")
        if day in days:
            days[day] += 1
    joblib.DATA_DIR.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(joblib.DATA_DIR)
    return {
        "users": {"total": users[0] or 0, "admins": users[1] or 0, "disabled": users[2] or 0, "online": sessions},
        "jobs": {"total": len(jobs), "by_state": by_state, "per_day": [{"day": d, "count": n} for d, n in days.items()],
                 "storage_bytes": sum(j["size_bytes"] for j in jobs)},
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "gpu": gpu_info(),
        "queue": "redis" if os.environ.get("REDIS_URL") else "local",
        "security": {"failed_logins_24h": failed},
        "recent": recent,
    }


# ---------------------------------------------------------------- người dùng
@router.get("/users")
def list_users():
    now = time.time()
    with db.connect() as con:
        rows = con.execute(
            "SELECT u.*, (SELECT COUNT(*) FROM jobs j WHERE j.owner_id = u.id) AS job_count, "
            "(SELECT COUNT(*) FROM sessions s WHERE s.user_id = u.id AND s.expires_at > ?) AS session_count "
            "FROM users u ORDER BY u.created_at DESC", (now,)).fetchall()
    return [{**public_user(dict(r)), "job_count": r["job_count"], "session_count": r["session_count"]} for r in rows]


class NewUser(BaseModel):
    email: str = Field(max_length=320)
    name: str = Field("", max_length=80)
    role: str = Field("user", pattern="^(admin|user)$")
    password: str | None = Field(None, max_length=256)   # bỏ trống -> sinh mật khẩu tạm


@router.post("/users")
def add_user(body: NewUser, request: Request, admin: dict = Depends(require_admin)):
    temp = None if body.password else temp_password()
    user = create_user(body.email, body.name, body.password or temp, role=body.role, must_change=temp is not None)
    db.audit("user_create", user=admin, target=user["email"], ip=client_ip(request), detail={"role": body.role})
    return {"user": public_user(user), "temp_password": temp}


def _target(uid: int) -> dict:
    with db.connect() as con:
        u = db.row(con.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())
    if not u:
        raise HTTPException(404, "Không có người dùng này")
    return u


def _other_admins(uid: int) -> int:
    with db.connect() as con:
        return con.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1 AND id != ?", (uid,)).fetchone()[0]


class UserPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    role: str | None = Field(None, pattern="^(admin|user)$")
    active: bool | None = None


@router.patch("/users/{uid}")
def patch_user(uid: int, body: UserPatch, request: Request, admin: dict = Depends(require_admin)):
    u = _target(uid)
    demote = body.role == "user" and u["role"] == "admin"
    disable = body.active is False and u["active"]
    if uid == admin["id"] and (demote or disable):
        raise HTTPException(400, "Không thể tự hạ quyền hoặc tự khoá tài khoản của mình")
    if (demote or disable) and u["role"] == "admin" and _other_admins(uid) == 0:
        raise HTTPException(400, "Phải còn ít nhất một quản trị viên đang hoạt động")
    sets, args = [], []
    for k in ("name", "role", "active"):
        v = getattr(body, k)
        if v is not None:
            sets.append(f"{k} = ?")
            args.append(int(v) if k == "active" else v.strip() if k == "name" else v)
    if sets:
        with db.connect() as con:
            con.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", (*args, uid))
    if disable:
        revoke_sessions(uid)
    db.audit("user_update", user=admin, target=u["email"], ip=client_ip(request),
             detail=body.model_dump(exclude_none=True))
    return public_user(_target(uid))


@router.post("/users/{uid}/reset-password")
def reset_password(uid: int, request: Request, admin: dict = Depends(require_admin)):
    u = _target(uid)
    temp = temp_password()
    with db.connect() as con:
        con.execute("UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?", (hash_password(temp), uid))
    revoke_sessions(uid)
    db.audit("user_reset_password", user=admin, target=u["email"], ip=client_ip(request))
    return {"temp_password": temp}


@router.delete("/users/{uid}/sessions")
def kick_user(uid: int, request: Request, admin: dict = Depends(require_admin)):
    u = _target(uid)
    n = revoke_sessions(uid, keep=admin["session_hash"] if uid == admin["id"] else None)
    db.audit("user_kick", user=admin, target=u["email"], ip=client_ip(request), detail={"count": n})
    return {"revoked": n}


@router.delete("/users/{uid}")
def delete_user(uid: int, request: Request, admin: dict = Depends(require_admin)):
    u = _target(uid)
    if uid == admin["id"]:
        raise HTTPException(400, "Không thể tự xoá tài khoản của mình")
    if u["role"] == "admin" and _other_admins(uid) == 0:
        raise HTTPException(400, "Phải còn ít nhất một quản trị viên đang hoạt động")
    with db.connect() as con:
        con.execute("DELETE FROM users WHERE id = ?", (uid,))  # job giữ lại, owner_id -> NULL
    db.audit("user_delete", user=admin, target=u["email"], ip=client_ip(request))
    return {"ok": True}


# ---------------------------------------------------------------- job, nhật ký, cài đặt
@router.get("/jobs")
def admin_jobs():
    return all_jobs()


@router.get("/audit")
def audit_log(limit: int = 50, offset: int = 0, action: str | None = None, q: str | None = None):
    limit = max(1, min(200, limit))
    where, args = [], []
    if action:
        where.append("action = ?")
        args.append(action)
    if q:
        where.append("(email LIKE ? OR target LIKE ? OR ip LIKE ?)")
        args += [f"%{q}%"] * 3
    sql_where = f"WHERE {' AND '.join(where)}" if where else ""
    with db.connect() as con:
        total = con.execute(f"SELECT COUNT(*) FROM audit {sql_where}", args).fetchone()[0]
        rows = [dict(r) for r in con.execute(f"SELECT * FROM audit {sql_where} ORDER BY id DESC LIMIT ? OFFSET ?",
                                             (*args, limit, offset))]
        actions = [r[0] for r in con.execute("SELECT DISTINCT action FROM audit ORDER BY action")]
    return {"total": total, "items": rows, "actions": actions}


class SettingsPatch(BaseModel):
    allow_registration: bool | None = None
    max_upload_mb: int | None = Field(None, ge=1, le=10_000)
    max_active_jobs: int | None = Field(None, ge=1, le=100)
    session_hours: int | None = Field(None, ge=1, le=24 * 30)
    remember_days: int | None = Field(None, ge=1, le=365)


@router.get("/settings")
def get_settings():
    return db.get_settings()


@router.patch("/settings")
def patch_settings(body: SettingsPatch, request: Request, admin: dict = Depends(require_admin)):
    values = body.model_dump(exclude_none=True)
    out = db.set_settings(values)
    db.audit("settings_update", user=admin, ip=client_ip(request), detail=values)
    return out
