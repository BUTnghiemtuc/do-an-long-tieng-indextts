import time

import pytest

pytest.importorskip("fastapi")


def wait_done(client, job_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = client.get(f"/api/jobs/{job_id}").json()["status"]
        if st["state"] in ("done", "error"):
            assert st["state"] == "done", st
            return
        time.sleep(0.2)
    raise TimeoutError


def upload(client, clip):
    with open(clip, "rb") as v, open(clip.with_suffix(".srt"), "rb") as s:
        return client.post("/api/jobs", files={"video": ("clip.mp4", v, "video/mp4"),
                                               "subtitles": ("clip.srt", s, "text/plain")},
                           data={"src_lang": "en"})


def test_upload_edit_regenerate(user_client, sample_clip):
    client = user_client
    r = upload(client, sample_clip)
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    wait_done(client, job_id)

    job = client.get(f"/api/jobs/{job_id}").json()
    p = job["project"]
    assert len(p["segments"]) == 4 and p["outputs"]["video"]
    assert client.get(f"/api/jobs/{job_id}/files/{p['outputs']['video']}").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/files/../../../etc/passwd").status_code == 404
    assert client.get(f"/api/jobs/{job_id}/source").status_code == 200

    # Đổi tên nhân vật, sửa bản dịch, tạo lại một câu.
    client.patch(f"/api/jobs/{job_id}/speakers/SPEAKER_00", json={"name": "Celia"})
    old_key = p["segments"][0]["tts_key"]
    r = client.patch(f"/api/jobs/{job_id}/segments/0", json={"vi_text": "Anh chưa bao giờ nghe em cả."})
    assert r.json()["project"]["segments"][0]["vi_locked"] is True
    assert client.post(f"/api/jobs/{job_id}/segments/0/regenerate").status_code == 200
    wait_done(client, job_id)

    p = client.get(f"/api/jobs/{job_id}").json()["project"]
    assert p["speakers"]["SPEAKER_00"]["name"] == "Celia"
    assert p["segments"][0]["vi_text"] == "Anh chưa bao giờ nghe em cả."
    assert p["segments"][0]["tts_key"] != old_key
    assert [j["id"] for j in client.get("/api/jobs").json()] == [job_id]

    # Xoá job
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get("/api/jobs").json() == []


def test_job_isolation(web, admin_client, user_client, sample_clip):
    """Người dùng khác không thấy, không sửa, không tải được job của người khác; admin thì được."""
    from server.auth import create_user

    from conftest import login

    job_id = upload(user_client, sample_clip).json()["id"]
    wait_done(user_client, job_id)

    create_user("other@vidub.test", "Other", "Khac2026xx")
    other = web()
    login(other, "other@vidub.test", "Khac2026xx")
    assert other.get("/api/jobs").json() == []
    for method, url in [("get", f"/api/jobs/{job_id}"), ("get", f"/api/jobs/{job_id}/source"),
                        ("get", f"/api/jobs/{job_id}/events"), ("delete", f"/api/jobs/{job_id}"),
                        ("patch", f"/api/jobs/{job_id}/segments/0")]:
        kw = {"json": {"vi_text": "x"}} if method == "patch" else {}
        assert getattr(other, method)(url, **kw).status_code == 404, url

    assert admin_client.get(f"/api/jobs/{job_id}").status_code == 200
    assert job_id in [j["id"] for j in admin_client.get("/api/admin/jobs").json()]


def test_upload_validation(user_client, admin_client, sample_clip):
    r = user_client.post("/api/jobs", files={"video": ("evil.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400
    r = user_client.post("/api/jobs", files={"video": ("a.mp4", b"x", "video/mp4")}, data={"src_lang": "xx"})
    assert r.status_code == 400

    admin_client.patch("/api/admin/settings", json={"max_upload_mb": 1})
    big = b"0" * (2 * 2 ** 20)
    r = user_client.post("/api/jobs", files={"video": ("big.mp4", big, "video/mp4")})
    assert r.status_code == 413
