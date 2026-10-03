import time
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

MOCK = Path(__file__).resolve().parent.parent / "configs" / "mock.yaml"


@pytest.fixture
def client(tmp_path, monkeypatch):
    from server import app as app_mod
    from server import jobs

    data = (tmp_path / "jobs").resolve()
    data.mkdir()
    monkeypatch.setattr(jobs, "DATA_DIR", data)
    monkeypatch.setattr(app_mod, "DATA_DIR", data)
    monkeypatch.setenv("VIDUB_CONFIG", str(MOCK))
    monkeypatch.delenv("REDIS_URL", raising=False)
    return TestClient(app_mod.app)


def wait_done(client, job_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = client.get(f"/api/jobs/{job_id}").json()["status"]
        if st["state"] in ("done", "error"):
            assert st["state"] == "done", st
            return
        time.sleep(0.2)
    raise TimeoutError


def test_upload_edit_regenerate(client, sample_clip):
    with open(sample_clip, "rb") as v, open(sample_clip.with_suffix(".srt"), "rb") as s:
        r = client.post("/api/jobs", files={"video": ("clip.mp4", v, "video/mp4"),
                                            "subtitles": ("clip.srt", s, "text/plain")},
                        data={"src_lang": "en"})
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
