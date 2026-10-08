"""Quản lý tài khoản từ dòng lệnh (khi chưa có admin hoặc quên mật khẩu admin).

    python -m server.manage create-admin admin@example.com --name "Quản trị"
    python -m server.manage reset-password user@example.com
    python -m server.manage list-users

Mật khẩu được hỏi qua getpass (không hiện, không lưu vào lịch sử shell).
"""

from __future__ import annotations

import argparse
import getpass
import sys

from fastapi import HTTPException

from . import db
from .auth import create_user, revoke_sessions
from .security import hash_password, password_problems


def ask_password(email: str) -> str:
    while True:
        pw = getpass.getpass("Mật khẩu: ")
        problems = password_problems(pw, email)
        if problems:
            print("Mật khẩu cần " + ", ".join(problems), file=sys.stderr)
            continue
        if getpass.getpass("Nhập lại: ") != pw:
            print("Hai lần nhập không khớp", file=sys.stderr)
            continue
        return pw


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m server.manage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-admin", help="tạo tài khoản quản trị")
    c.add_argument("email")
    c.add_argument("--name", default="")
    r = sub.add_parser("reset-password", help="đặt lại mật khẩu, đăng xuất mọi phiên")
    r.add_argument("email")
    sub.add_parser("list-users", help="liệt kê tài khoản")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "create-admin":
            user = create_user(args.email, args.name, ask_password(args.email), role="admin")
            db.audit("user_create", target=user["email"], ip="cli", detail={"role": "admin"})
            print(f"Đã tạo quản trị viên {user['email']} (id={user['id']})")
        elif args.cmd == "reset-password":
            email = args.email.strip().lower()
            with db.connect() as con:
                u = con.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if not u:
                print(f"Không có tài khoản {email}", file=sys.stderr)
                return 1
            pw = ask_password(email)
            with db.connect() as con:
                con.execute("UPDATE users SET password_hash = ?, must_change_password = 0, active = 1 WHERE id = ?",
                            (hash_password(pw), u["id"]))
            revoke_sessions(u["id"])
            db.audit("user_reset_password", target=email, ip="cli")
            print(f"Đã đặt lại mật khẩu cho {email}")
        else:
            with db.connect() as con:
                for u in con.execute("SELECT id, email, name, role, active FROM users ORDER BY id"):
                    print(f"{u['id']:>4}  {u['role']:<5}  {'' if u['active'] else '[khoá] '}{u['email']}  ({u['name']})")
    except HTTPException as e:
        print(e.detail, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
