"""Bước 3: phân đoạn người nói (ai nói khi nào) trên track giọng."""

from __future__ import annotations

import logging
import os

import numpy as np

from .. import audio
from ..pipeline import file_sig
from ..project import Speaker, Turn
from .base import BaseStep

log = logging.getLogger("vidub.diarize")


class Diarize(BaseStep):
    name = "diarize"

    def fingerprint(self, project, ctx):
        return {"vocals": file_sig(project.abs(project.tracks.get("vocals")))}

    def outputs_exist(self, project):
        return bool(project.turns)

    def run(self, project, ctx):
        cfg = ctx.section("diarize")
        vocals = project.abs(project.tracks["vocals"])
        backend = cfg.get("backend", "pyannote")
        if backend == "pyannote":
            turns = self._pyannote(vocals, cfg)
        elif backend == "single":
            turns = energy_vad_turns(vocals)
        else:
            raise ValueError(f"diarize.backend không hỗ trợ: {backend}")

        turns = merge_turns(turns, cfg.get("merge_gap", 0.5))
        project.turns = turns
        # Giữ tên nhân vật người dùng đã đặt nếu ID người nói không đổi.
        old = project.speakers
        project.speakers = {
            spk: old.get(spk, Speaker(name=spk)) for spk in sorted({t.speaker for t in turns})
        }
        log.info("%d lượt nói, %d người nói", len(turns), len(project.speakers))
        return project

    @staticmethod
    def _pyannote(vocals, cfg) -> list[Turn]:
        import torch
        from pyannote.audio import Pipeline

        token = os.environ.get(cfg.get("hf_token_env", "HF_TOKEN"))
        try:
            pipe = Pipeline.from_pretrained(cfg["model"], token=token)          # pyannote >= 4
        except TypeError:
            pipe = Pipeline.from_pretrained(cfg["model"], use_auth_token=token)  # pyannote 3.x
        if pipe is None:
            raise RuntimeError("Không nạp được pyannote: kiểm tra HF_TOKEN và đã chấp nhận điều khoản model trên HF")
        if torch.cuda.is_available():
            pipe.to(torch.device("cuda"))

        wav, sr = audio.load(vocals, sr=16000)
        kw = {k: cfg[k] for k in ("min_speakers", "max_speakers") if cfg.get(k)}
        result = pipe({"waveform": torch.from_numpy(wav)[None], "sample_rate": sr}, **kw)
        annotation = getattr(result, "speaker_diarization", result)
        return [
            Turn(start=round(seg.start, 3), end=round(seg.end, 3), speaker=str(spk))
            for seg, _, spk in annotation.itertracks(yield_label=True)
        ]


def merge_turns(turns: list[Turn], gap: float) -> list[Turn]:
    out: list[Turn] = []
    for t in sorted(turns, key=lambda t: t.start):
        if out and out[-1].speaker == t.speaker and t.start - out[-1].end <= gap:
            out[-1].end = max(out[-1].end, t.end)
        else:
            out.append(t.model_copy())
    return out


def energy_vad_turns(path, frame: float = 0.03, thresh_db: float = -35.0, min_dur: float = 0.3,
                     speaker: str = "SPEAKER_00") -> list[Turn]:
    """VAD năng lượng đơn giản, gán hết cho một người nói (backend `single`)."""
    wav, sr = audio.load(path, sr=16000)
    n = int(frame * sr)
    frames = len(wav) // n
    if frames == 0:
        return []
    rms = np.sqrt(np.mean(wav[: frames * n].reshape(frames, n) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / (rms.max() + 1e-12) + 1e-12)
    active = db > thresh_db
    turns, start = [], None
    for i, a in enumerate(np.append(active, False)):
        if a and start is None:
            start = i
        elif not a and start is not None:
            if (i - start) * frame >= min_dur:
                turns.append(Turn(start=round(start * frame, 3), end=round(i * frame, 3), speaker=speaker))
            start = None
    return turns
