"""Xác thực, CSRF, phân quyền và trang quản trị."""

import pytest

from conftest import ADMIN, USER, login

pytest.importorskip("fastapi")


def test_requires_login(web):
    c = web()
    assert c.get("/api/jobs").status_code == 401
    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/admin/overview").status_code == 401
    assert c.get("/api/meta").status_code == 200


def test_setup_flow(web):
    c = web()
    assert c.get("/api/auth/status").json()["setup_required"] is True
    body = {"email": "boss@vidub.test", "name": "Boss", "password": "Giamdoc2026"}
    assert c.post("/api/auth/setup", json={**body, "token": "sai"}).status_code == 403
    r = c.post("/api/auth/setup", json={**body, "token": "setup-token-test"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert c.get("/api/auth/me").json()["email"] == "boss@vidub.test"
    # Đã có người dùng thì không khởi tạo lại được
    assert c.post("/api/auth/setup", json={**body, "token": "setup-token-test"}).status_code == 409


def test_csrf_required(web, admin_client):
    c = web()
    c.headers.pop("X-CSRF-Token")
    assert login(c, *ADMIN).status_code == 403
    c.headers["X-CSRF-Token"] = "khac-cookie"
    assert login(c, *ADMIN).status_code == 403


def test_login_logout_and_cookie_flags(web, admin_client):
    c = web()
    r = login(c, *ADMIN)
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie.replace("Lax", "lax")
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_wrong_password_same_message_and_lockout(web, admin_client):
    c = web()
    r1 = login(c, ADMIN[0], "sai12345")
    r2 = login(c, "khongco@vidub.test", "sai12345")
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]
    for _ in range(3):
        login(c, ADMIN[0], "sai12345")
    r = login(c, *ADMIN)  # 5 lần sai theo IP -> bị chặn kể cả khi đúng mật khẩu
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_register_and_policy(web, admin_client):
    c = web()
    weak = c.post("/api/auth/register", json={"email": "a@vidub.test", "password": "12345678"})
    assert weak.status_code == 400
    ok = c.post("/api/auth/register", json={"email": "New@Vidub.test", "name": "New", "password": "Phim2026x"})
    assert ok.status_code == 200 and ok.json()["role"] == "user" and ok.json()["email"] == "new@vidub.test"
    dup = web().post("/api/auth/register", json={"email": "new@vidub.test", "password": "Phim2026x"})
    assert dup.status_code == 409

    admin_client.patch("/api/admin/settings", json={"allow_registration": False})
    r = web().post("/api/auth/register", json={"email": "b@vidub.test", "password": "Phim2026x"})
    assert r.status_code == 403


def test_user_cannot_use_admin(user_client):
    assert user_client.get("/api/admin/overview").status_code == 403
    assert user_client.get("/api/admin/users").status_code == 403
    assert user_client.patch("/api/admin/settings", json={"max_upload_mb": 9999}).status_code == 403


def test_admin_user_management(web, admin_client, user_client):
    users = admin_client.get("/api/admin/users").json()
    uid = next(u["id"] for u in users if u["email"] == USER[0])
    me = next(u["id"] for u in users if u["email"] == ADMIN[0])

    # Không tự hạ quyền / tự khoá / tự xoá, phải còn ít nhất một admin
    assert admin_client.patch(f"/api/admin/users/{me}", json={"role": "user"}).status_code == 400
    assert admin_client.patch(f"/api/admin/users/{me}", json={"active": False}).status_code == 400
    assert admin_client.delete(f"/api/admin/users/{me}").status_code == 400

    # Khoá tài khoản -> phiên của người đó mất hiệu lực
    assert admin_client.patch(f"/api/admin/users/{uid}", json={"active": False}).status_code == 200
    assert user_client.get("/api/auth/me").status_code == 401
    assert login(web(), *USER).status_code == 403
    admin_client.patch(f"/api/admin/users/{uid}", json={"active": True})

    # Đặt lại mật khẩu -> buộc đổi mật khẩu trước khi dùng tiếp
    temp = admin_client.post(f"/api/admin/users/{uid}/reset-password").json()["temp_password"]
    c = web()
    assert login(c, USER[0], temp).json()["must_change_password"] == 1
    assert c.get("/api/jobs").status_code == 403
    assert c.post("/api/auth/password", json={"current": temp, "new": "Moi2026abc"}).status_code == 200
    assert c.get("/api/jobs").status_code == 200

    # Tạo người dùng với mật khẩu tạm
    r = admin_client.post("/api/admin/users", json={"email": "x@vidub.test", "name": "X"}).json()
    assert r["temp_password"] and r["user"]["must_change_password"] == 1

    actions = admin_client.get("/api/admin/audit").json()["actions"]
    assert {"login", "user_update", "user_reset_password", "user_create"} <= set(actions)
    ov = admin_client.get("/api/admin/overview").json()
    assert ov["users"]["total"] == 3 and len(ov["jobs"]["per_day"]) == 14


def test_sessions_and_password_change(web, user_client):
    other = web()
    login(other, *USER)
    sessions = user_client.get("/api/auth/sessions").json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    assert "token_hash" not in sessions[0]

    r = user_client.post("/api/auth/password", json={"current": USER[1], "new": "Doimk2026"})
    assert r.json()["revoked_sessions"] == 1
    assert other.get("/api/auth/me").status_code == 401       # phiên khác bị đăng xuất
    assert user_client.get("/api/auth/me").status_code == 200  # phiên hiện tại giữ nguyên


def test_security_headers(web):
    r = web().get("/")
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert web().get("/api/meta").headers["cache-control"] == "no-store"
