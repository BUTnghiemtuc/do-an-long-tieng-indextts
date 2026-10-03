"""Dự án JSON: một file cho mỗi clip, mọi bước đọc và ghi chung file này.

Đường dẫn trong file luôn tương đối so với thư mục dự án, để có thể chép cả
thư mục sang máy khác (máy GPU <-> máy chạy web) mà không phải sửa.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr

PROJECT_FILE = "project.json"
SCHEMA_VERSION = 1

SegmentStatus = Literal["new", "translated", "synthesized", "done", "error"]


class Speaker(BaseModel):
    name: str
    timbre_prompt: str | None = None
    # Ghi chú cho bước dịch chọn xưng hô: giới tính, tuổi, quan hệ với nhân vật khác.
    notes: str = ""


class Turn(BaseModel):
    """Một lượt nói từ diarization."""

    start: float
    end: float
    speaker: str


class Word(BaseModel):
    start: float
    end: float
    text: str


class Segment(BaseModel):
    id: int
    start: float
    end: float
    speaker: str
    src_text: str
    vi_text: str = ""
    words: list[Word] = Field(default_factory=list)

    # Dịch
    max_syllables: int | None = None
    src_key: str | None = None        # hash(src_text) lúc dịch; khác thì dịch lại
    vi_locked: bool = False           # người dùng đã sửa tay -> không dịch đè

    # Sinh giọng
    style_prompt: str | None = None
    tts_natural: str | None = None    # bản sinh tự nhiên (chưa căn thời lượng)
    natural_dur: float | None = None
    tts_key: str | None = None

    # Căn thời lượng
    tts_audio: str | None = None      # bản cuối cùng đặt lên timeline
    align_key: str | None = None
    place_start: float | None = None
    duration_ratio: float | None = None
    align_method: list[str] = Field(default_factory=list)

    status: SegmentStatus = "new"
    warnings: list[str] = Field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start


class StepRecord(BaseModel):
    hash: str | None = None
    elapsed: float = 0.0
    finished_at: str | None = None


class Project(BaseModel):
    version: int = SCHEMA_VERSION
    clip_id: str
    source: str                       # video gốc (tương đối)
    src_lang: str = "en"
    tgt_lang: str = "vi"
    duration: float | None = None
    tracks: dict[str, str] = Field(default_factory=dict)   # original, vocals, background, dub
    speakers: dict[str, Speaker] = Field(default_factory=dict)
    turns: list[Turn] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)
    steps: dict[str, StepRecord] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)  # video, srt_vi, srt_src

    _dir: Path | None = PrivateAttr(default=None)

    # ------------------------------------------------------------------ đường dẫn
    @property
    def dir(self) -> Path:
        if self._dir is None:
            raise RuntimeError("Project chưa gắn thư mục; dùng Project.load/create")
        return self._dir

    def abs(self, rel: str | None) -> Path | None:
        return None if rel is None else self.dir / rel

    def rel(self, path: str | Path) -> str:
        return os.path.relpath(Path(path), self.dir)

    def file(self, *parts: str) -> Path:
        """Tạo (nếu cần) thư mục cha và trả về đường dẫn tuyệt đối trong dự án."""
        p = self.dir.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # ------------------------------------------------------------------ truy vấn
    def segment(self, seg_id: int) -> Segment:
        for s in self.segments:
            if s.id == seg_id:
                return s
        raise KeyError(f"Không có câu id={seg_id}")

    def speaker_name(self, spk: str) -> str:
        return self.speakers[spk].name if spk in self.speakers else spk

    # ------------------------------------------------------------------ lưu / nạp
    @classmethod
    def create(cls, project_dir: str | Path, source: str | Path, clip_id: str | None = None, **kw) -> "Project":
        project_dir = Path(project_dir).resolve()
        project_dir.mkdir(parents=True, exist_ok=True)
        source = Path(source).resolve()
        proj = cls(clip_id=clip_id or source.stem, source=os.path.relpath(source, project_dir), **kw)
        proj._dir = project_dir
        proj.save()
        return proj

    @classmethod
    def load(cls, project_dir: str | Path) -> "Project":
        project_dir = Path(project_dir).resolve()
        if project_dir.is_file():
            project_dir = project_dir.parent
        data = json.loads((project_dir / PROJECT_FILE).read_text(encoding="utf-8"))
        proj = cls.model_validate(data)
        proj._dir = project_dir
        return proj

    def save(self) -> Path:
        """Ghi nguyên tử (file tạm + rename) để web và worker không đọc phải file dở."""
        path = self.dir / PROJECT_FILE
        text = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".project.", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
        return path
