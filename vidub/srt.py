"""Đọc / ghi phụ đề SRT."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
_TAGS = re.compile(r"<[^>]+>|\{[^}]+\}")


@dataclass
class Cue:
    start: float
    end: float
    text: str


def fmt_time(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path: str | Path, cues: list[Cue]) -> Path:
    path = Path(path)
    lines = []
    for i, c in enumerate(sorted(cues, key=lambda c: c.start), 1):
        lines += [str(i), f"{fmt_time(c.start)} --> {fmt_time(c.end)}", c.text.strip(), ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def read_srt(path: str | Path) -> list[Cue]:
    raw = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            m = _TIME.search(line)
            if m:
                g = list(map(int, m.groups()))
                start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
                end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
                text = " ".join(_TAGS.sub("", t).strip() for t in lines[i + 1:] if t.strip())
                if text:
                    cues.append(Cue(start, end, text))
                break
    return cues
