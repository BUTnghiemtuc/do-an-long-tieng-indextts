import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from vidub.srt import Cue, write_srt

LINES = [
    (0.5, 2.5, "You never listened to me."),
    (3.0, 5.2, "I always listened. You just never said anything."),
    (5.5, 6.6, "Stop it."),
    (9.5, 12.0, "We have to leave before the sun comes up."),
]


@pytest.fixture
def sample_clip(tmp_path: Path) -> Path:
    """Video 14 s: hình test + audio có 'tiếng nói' (sóng điều biên) đúng thời điểm các câu + SRT."""
    sr = 16000
    t = np.arange(int(14 * sr)) / sr
    wav = 0.02 * np.sin(2 * np.pi * 60 * t)  # nền nhỏ
    for start, end, _ in LINES:
        m = (t >= start) & (t < end)
        wav[m] += 0.3 * np.sin(2 * np.pi * 180 * t[m]) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t[m]))
    wav_path = tmp_path / "audio.wav"
    sf.write(wav_path, wav.astype(np.float32), sr)

    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         "testsrc=size=320x240:rate=15", "-i", str(wav_path), "-t", "14", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)],
        check=True,
    )
    write_srt(video.with_suffix(".srt"), [Cue(a, b, txt) for a, b, txt in LINES])
    return video


# ---------------------------------------------------------------- web: client có đăng nhập
MOCK_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "mock.yaml"
ADMIN = ("admin@vidub.test", "Quantri2026")
USER = ("user@vidub.test", "Bientap2026")


@pytest.fixture
def web(tmp_path, monkeypatch):
    """App FastAPI với CSDL, thư mục job riêng cho mỗi test; trả về hàm tạo client."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from server import app as app_mod
    from server import jobs
    from server.security import login_failures, register_limiter

    data = (tmp_path / "jobs").resolve()
    data.mkdir()
    monkeypatch.setattr(jobs, "DATA_DIR", data)
    monkeypatch.setenv("VIDUB_DB", str(tmp_path / "vidub.db"))
    monkeypatch.setenv("VIDUB_SETUP_TOKEN", "setup-token-test")
    monkeypatch.setenv("VIDUB_CONFIG", str(MOCK_CONFIG))
    monkeypatch.delenv("REDIS_URL", raising=False)
    login_failures.clear()
    register_limiter.clear()

    def new_client() -> "TestClient":
        c = TestClient(app_mod.app)
        c.get("/api/auth/status")  # nhận cookie CSRF
        c.headers["X-CSRF-Token"] = c.cookies.get("vidub_csrf")
        return c

    return new_client


def login(client, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture
def admin_client(web):
    from server.auth import create_user

    create_user(ADMIN[0], "Admin", ADMIN[1], role="admin")
    c = web()
    assert login(c, *ADMIN).status_code == 200
    return c


@pytest.fixture
def user_client(web, admin_client):
    from server.auth import create_user

    create_user(USER[0], "User", USER[1])
    c = web()
    assert login(c, *USER).status_code == 200
    return c
