"""Worker GPU: chạy pipeline cho một job. Model được nạp một lần mỗi tiến trình (cache trong backend).

Chạy riêng với Redis:  rq worker vidub --url $REDIS_URL
"""

from __future__ import annotations

import logging
import os
import time
import traceback
from pathlib import Path

from vidub.config import load_config
from vidub.pipeline import Context, run_pipeline
from vidub.project import Project

from .jobs import write_status

log = logging.getLogger("vidub.worker")


def server_config() -> dict:
    paths = [p for p in os.environ.get("VIDUB_CONFIG", "").split(",") if p]
    return load_config(paths)


def run_job(job_dir: str, steps: list[str] | None = None, force: bool = False) -> None:
    jdir = Path(job_dir)
    last = [0.0]

    def progress(step: str, frac: float, msg: str) -> None:
        now = time.time()
        if frac in (0.0, 1.0) or now - last[0] > 0.5:   # không ghi đĩa quá dày
            last[0] = now
            write_status(jdir, state="running", step=step, frac=round(frac, 3), msg=msg)

    write_status(jdir, state="running", started=time.time())
    try:
        project = Project.load(jdir / "project")
        run_pipeline(project, Context(cfg=server_config(), force=force, progress=progress), steps)
        write_status(jdir, state="done", step=None, frac=1.0, msg="xong")
    except Exception as e:
        log.exception("Job %s lỗi", jdir.name)
        write_status(jdir, state="error", error=f"{type(e).__name__}: {e}",
                     trace=traceback.format_exc()[-3000:])
