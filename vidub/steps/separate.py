"""Bước 2: tách giọng nói khỏi nhạc nền + hiệu ứng (M&E) bằng Demucs."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from .. import audio
from ..pipeline import file_sig
from .base import BaseStep


class Separate(BaseStep):
    name = "separate"
    produces_tracks = ("vocals", "background")

    def fingerprint(self, project, ctx):
        return {"original": file_sig(project.abs(project.tracks.get("original")))}

    def run(self, project, ctx):
        cfg = ctx.section("separate")
        original = project.abs(project.tracks["original"])
        vocals = project.file("audio", "vocals.wav")
        background = project.file("audio", "background.wav")
        backend = cfg.get("backend", "demucs")

        if backend == "demucs":
            self._demucs(original, vocals, background, cfg)
        elif backend == "none":
            wav, sr = audio.load(original, mono=False)
            audio.save(vocals, wav, sr)
            audio.save(background, np.zeros_like(wav), sr)
        else:
            raise ValueError(f"separate.backend không hỗ trợ: {backend}")

        project.tracks["vocals"] = project.rel(vocals)
        project.tracks["background"] = project.rel(background)
        return project

    @staticmethod
    def _demucs(original: Path, vocals: Path, background: Path, cfg: dict) -> None:
        model = cfg.get("model", "htdemucs")
        with tempfile.TemporaryDirectory() as tmp:
            cmd = [sys.executable, "-m", "demucs", "--two-stems", "vocals", "-n", model,
                   "-d", cfg.get("device", "cuda"), "-o", tmp, str(original)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(f"Demucs lỗi:\n{proc.stderr[-2000:]}")
            out_dir = Path(tmp) / model / original.stem
            shutil.move(out_dir / "vocals.wav", vocals)
            shutil.move(out_dir / "no_vocals.wav", background)
