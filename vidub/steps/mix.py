"""Bước 8: chuẩn hoá loudness từng câu, đặt lên timeline, trộn với M&E, ghép video, xuất SRT."""

from __future__ import annotations

import json
import logging
import subprocess

import numpy as np
import pyloudnorm as pyln

from .. import audio
from ..srt import Cue, write_srt
from .base import BaseStep

log = logging.getLogger("vidub.mix")


def has_video(path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                          "stream=codec_type", "-of", "json", str(path)], capture_output=True, text=True)
    return bool(json.loads(out.stdout or "{}").get("streams"))


def normalize_loudness(wav: np.ndarray, sr: int, target_lufs: float) -> np.ndarray:
    if len(wav) >= int(0.4 * sr):   # pyloudnorm cần tối thiểu một block 400 ms
        loud = pyln.Meter(sr).integrated_loudness(wav)
        if np.isfinite(loud):
            return (wav * 10 ** ((target_lufs - loud) / 20)).astype(np.float32)
    gain_db = target_lufs - audio.rms_db(wav) - 3.0   # RMS ~ LUFS + 3 dB với tiếng nói
    return (wav * 10 ** (gain_db / 20)).astype(np.float32)


class Mix(BaseStep):
    name = "mix"

    def run(self, project, ctx):
        cfg = ctx.section("mix")
        bg, sr = audio.load(project.abs(project.tracks["background"]), mono=False)
        n = len(bg)
        dialog = np.zeros(n, dtype=np.float32)

        placed = 0
        for seg in project.segments:
            if seg.status != "done" or not seg.tts_audio:
                continue
            wav, _ = audio.load(project.abs(seg.tts_audio), sr=sr)
            wav = audio.fade(normalize_loudness(wav, sr, cfg.get("dialog_lufs", -20.0)), sr)
            a = int(round((seg.place_start or seg.start) * sr))
            b = min(n, a + len(wav))
            if a < n:
                dialog[a:b] += wav[: b - a]
                placed += 1

        bg = bg * 10 ** (cfg.get("background_gain_db", 0.0) / 20)
        duck = cfg.get("duck_db", 0.0)
        if duck:
            env = (np.abs(dialog) > 1e-3).astype(np.float32)
            k = int(0.15 * sr)
            env = np.clip(np.convolve(env, np.ones(k) / k, mode="same") * 4, 0, 1)
            bg = bg * (1 - env * (1 - 10 ** (-abs(duck) / 20)))[:, None]

        mix = bg + dialog[:, None]
        peak = float(np.max(np.abs(mix))) if mix.size else 0.0
        if peak > 0.98:
            mix = mix * (0.98 / peak)

        dialog_path = audio.save(project.file("audio", "dub_dialog.wav"), dialog, sr)
        mix_path = audio.save(project.file("audio", "dub_mix.wav"), mix.astype(np.float32), sr)
        project.tracks["dub_dialog"] = project.rel(dialog_path)
        project.tracks["dub"] = project.rel(mix_path)

        srt_vi = write_srt(project.file("output", f"{project.clip_id}.vi.srt"),
                           [Cue(s.start, s.end, s.vi_text) for s in project.segments if s.vi_text])
        srt_src = write_srt(project.file("output", f"{project.clip_id}.{project.src_lang}.srt"),
                            [Cue(s.start, s.end, s.src_text) for s in project.segments])
        project.outputs["srt_vi"] = project.rel(srt_vi)
        project.outputs["srt_src"] = project.rel(srt_src)

        src = project.abs(project.source)
        if has_video(src):
            video = project.file("output", f"{project.clip_id}.vi.mp4")
            audio.run_ffmpeg(["-i", str(src), "-i", str(mix_path), "-map", "0:v:0", "-map", "1:a:0",
                              "-c:v", "copy", "-c:a", cfg.get("audio_codec", "aac"),
                              "-b:a", cfg.get("audio_bitrate", "192k"), "-shortest", str(video)])
            project.outputs["video"] = project.rel(video)
        log.info("Đã trộn %d câu", placed)
        return project
