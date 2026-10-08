"""Quản lý job: mỗi job là một thư mục chứa dự án JSON + status.json.

Hàng đợi: có REDIS_URL thì đẩy sang RQ (worker GPU riêng, xem worker.py);
không có thì chạy trong một luồng nền của chính API (đủ cho demo một máy).
Chỉ một job chạy một lúc vì chỉ có một GPU.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA_DIR = Path(os.environ.get("VIDUB_DATA", "data/jobs")).resolve()
STATUS_FILE = "status.json"
BUSY_STATES = ("queued", "running")

_local_pool: ThreadPoolExecutor | None = None


def job_dir(job_id: str) -> Path:
    path = (DATA_DIR / job_id).resolve()
    if path.parent != DATA_DIR:
        raise ValueError("job id không hợp lệ")
    return path


def list_job_dirs() -> list[Path]:
    """Thư mục job có project.json, mới nhất trước."""
    if not DATA_DIR.exists():
        return []
    return [d for d in sorted(DATA_DIR.iterdir(), reverse=True) if (d / "project" / "project.json").exists()]


def dir_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def new_job_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def read_status(job_id: str) -> dict:
    try:
        return json.loads((job_dir(job_id) / STATUS_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"state": "unknown"}


def write_status(jdir: Path, **fields) -> dict:
    path = jdir / STATUS_FILE
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        status = {}
    status.update(fields, updated=time.time())
    fd, tmp = tempfile.mkstemp(dir=jdir, prefix=".status.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False)
    os.replace(tmp, path)
    return status


def enqueue(job_id: str, steps: list[str] | None, force: bool = False) -> None:
    jdir = job_dir(job_id)
    write_status(jdir, state="queued", step=None, frac=0.0, msg="đang chờ", error=None, steps=steps)
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        from redis import Redis
        from rq import Queue

        Queue("vidub", connection=Redis.from_url(redis_url)).enqueue(
            "server.worker.run_job", str(jdir), steps, force, job_timeout=6 * 3600)
    else:
        global _local_pool
        if _local_pool is None:
            _local_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vidub-worker")
        from .worker import run_job

        _local_pool.submit(run_job, str(jdir), steps, force)
