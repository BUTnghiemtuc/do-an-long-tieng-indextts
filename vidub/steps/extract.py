"""Bước 1: tách audio từ video."""

from __future__ import annotations

from .. import audio
from ..pipeline import file_sig
from .base import BaseStep


class Extract(BaseStep):
    name = "extract"
    produces_tracks = ("original",)

    def fingerprint(self, project, ctx):
        return {"source": file_sig(project.abs(project.source))}

    def run(self, project, ctx):
        sr = ctx.section("extract").get("sample_rate", 44100)
        src = project.abs(project.source)
        out = project.file("audio", "original.wav")
        audio.run_ffmpeg(["-i", str(src), "-vn", "-ac", "2", "-ar", str(sr), "-c:a", "pcm_s16le", str(out)])
        project.tracks["original"] = project.rel(out)
        project.duration = round(audio.duration(out), 3)
        return project
