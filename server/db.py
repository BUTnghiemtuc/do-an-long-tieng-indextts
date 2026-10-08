"""CSDL SQLite cho người dùng, phiên đăng nhập, quyền sở hữu job, nhật ký và cài đặt.

Dữ liệu của từng clip vẫn nằm trong project.json (xem vidub/project.py). File này chỉ
giữ những thứ cần truy vấn chéo: ai sở hữu job nào, ai đang đăng nhập, ai đã làm gì.
Chỉ dùng thư viện chuẩn (sqlite3), không thêm phụ thuộc.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    email            TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    password_hash    TEXT NOT NULL,
    role             TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    active           INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at       REAL NOT NULL,
    last_login_at    REAL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash   TEXT PRIMARY KEY,             -- sha256(token); cookie giữ token thật
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   REAL NOT NULL,
    expires_at   REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    ip           TEXT,
    user_agent   TEXT
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS jobs (
    id         TEXT PRIMARY KEY,
    owner_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    filename   TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(owner_id);
CREATE TABLE IF NOT EXISTS audit (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    user_id INTEGER,
    email   TEXT,
    action  TEXT NOT NULL,
    target  TEXT,
    ip      TEXT,
    detail  TEXT
);
CREATE INDEX IF NOT EXISTS audit_ts ON audit(ts);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS: dict[str, Any] = {
    "allow_registration": True,    # cho phép tự đăng ký tài khoản
    "max_upload_mb": 500,          # dung lượng tối đa mỗi video
    "max_active_jobs": 2,          # số job đang chờ/chạy tối đa mỗi người dùng thường
    "session_hours": 12,           # thời hạn phiên khi không chọn "ghi nhớ"
    "remember_days": 30,           # thời hạn phiên khi chọn "ghi nhớ"
}

_lock = threading.Lock()
_path: Path | None = None


def db_path() -> Path:
    return Path(os.environ.get("VIDUB_DB", "data/vidub.db")).resolve()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Một kết nối cho mỗi thao tác; tự commit, tự tạo bảng ở lần đầu."""
    global _path
    path = db_path()
    with _lock:
        if _path != path:
            path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(path)
            con.executescript(SCHEMA)
            con.execute("PRAGMA journal_mode=WAL")
            con.close()
            _path = path
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None


# ---------------------------------------------------------------- cài đặt
def get_settings() -> dict[str, Any]:
    out = dict(DEFAULT_SETTINGS)
    with connect() as con:
        for r in con.execute("SELECT key, value FROM settings"):
            if r["key"] in out:
                out[r["key"]] = json.loads(r["value"])
    return out


def setting(key: str) -> Any:
    return get_settings()[key]


def set_settings(values: dict[str, Any]) -> dict[str, Any]:
    with connect() as con:
        for k, v in values.items():
            if k not in DEFAULT_SETTINGS:
                raise KeyError(k)
            con.execute("INSERT INTO settings(key, value) VALUES(?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, json.dumps(v)))
    return get_settings()


# ---------------------------------------------------------------- nhật ký
def audit(action: str, *, user: dict | None = None, target: str | None = None,
          ip: str | None = None, detail: str | dict | None = None) -> None:
    if isinstance(detail, dict):
        detail = json.dumps(detail, ensure_ascii=False)
    with connect() as con:
        con.execute("INSERT INTO audit(ts, user_id, email, action, target, ip, detail) VALUES(?,?,?,?,?,?,?)",
                    (time.time(), user and user["id"], user and user["email"], action, target, ip, detail))
