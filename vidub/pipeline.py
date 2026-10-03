"""Điều phối các bước. Mỗi bước là `run(project, ctx) -> project`.

Hai tầng cache:
- Bước "thô" (extract, separate, diarize, transcribe) khai báo `fingerprint`; nếu
  hash không đổi và kết quả còn trên đĩa thì bỏ qua cả bước.
- Bước "theo câu" (translate, synthesize, align) trả fingerprint None, luôn chạy
  nhưng tự bỏ qua câu nào có key trùng — nên sửa một câu trên web chỉ làm lại câu đó.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from .project import Project, StepRecord

log = logging.getLogger("vidub")

ProgressFn = Callable[[str, float, str], None]   # (bước, tỉ lệ 0..1, thông điệp)


@dataclass
class Context:
    cfg: dict
    force: bool = False
    progress: ProgressFn = field(default=lambda step, frac, msg: None)

    def section(self, name: str) -> dict:
        return self.cfg.get(name, {}) or {}


class Step(Protocol):
    name: str

    def fingerprint(self, project: Project, ctx: Context) -> dict | None: ...

    def outputs_exist(self, project: Project) -> bool: ...

    def run(self, project: Project, ctx: Context) -> Project: ...


def stable_hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def file_sig(path: Path | None) -> list | None:
    """Chữ ký rẻ của file: kích thước + mtime (đủ để biết file đầu vào đã đổi)."""
    if path is None or not path.exists():
        return None
    st = path.stat()
    return [st.st_size, int(st.st_mtime)]


def _registry() -> dict[str, Step]:
    from .steps import STEPS
    return {s.name: s for s in STEPS}


def step_names() -> list[str]:
    from .steps import STEPS
    return [s.name for s in STEPS]


def select_steps(only: list[str] | None = None, from_step: str | None = None, to_step: str | None = None) -> list[str]:
    names = step_names()
    for n in (only or []) + [x for x in (from_step, to_step) if x]:
        if n not in names:
            raise ValueError(f"Bước không tồn tại: {n}. Các bước: {', '.join(names)}")
    if only:
        return [n for n in names if n in only]
    a = names.index(from_step) if from_step else 0
    b = names.index(to_step) + 1 if to_step else len(names)
    return names[a:b]


def run_pipeline(project: Project, ctx: Context, steps: list[str] | None = None) -> Project:
    registry = _registry()
    for name in steps or step_names():
        step = registry[name]
        fp = step.fingerprint(project, ctx)
        h = stable_hash({"fp": fp, "cfg": ctx.section(name)}) if fp is not None else None
        rec = project.steps.get(name)
        if (not ctx.force and h is not None and rec is not None and rec.hash == h
                and step.outputs_exist(project)):
            log.info("[%s] bỏ qua (cache)", name)
            ctx.progress(name, 1.0, "cache")
            continue

        log.info("[%s] bắt đầu", name)
        ctx.progress(name, 0.0, "bắt đầu")
        t0 = time.perf_counter()
        project = step.run(project, ctx)
        elapsed = time.perf_counter() - t0
        project.steps[name] = StepRecord(
            hash=h, elapsed=round(elapsed, 3),
            finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        project.save()
        ctx.progress(name, 1.0, f"xong {elapsed:.1f}s")
        log.info("[%s] xong sau %.1fs", name, elapsed)
    return project


def rtf_report(project: Project) -> dict:
    """RTF toàn pipeline = tổng thời gian xử lý / thời lượng clip (dùng cho báo cáo)."""
    total = sum(r.elapsed for r in project.steps.values())
    per_step = {k: r.elapsed for k, r in project.steps.items()}
    dur = project.duration or 0.0
    return {
        "clip_duration": dur,
        "processing_time": round(total, 3),
        "rtf": round(total / dur, 3) if dur else None,
        "per_step": per_step,
    }
