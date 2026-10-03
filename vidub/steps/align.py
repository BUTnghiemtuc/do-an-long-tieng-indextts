"""Bước 7: căn thời lượng câu tiếng Việt cho khớp câu gốc.

Thứ tự ưu tiên (bước 4 đã lo (a) độ dài bản dịch):
 (b) sinh lại với duration_factor = đích / tự nhiên, kẹp trong [0.75, 1.25]
 (c) co giãn thời gian tối đa ±10%
 (d) mượn khoảng lặng phía sau câu, không lấn sang câu kế tiếp
Vẫn dài hơn khoảng trống thì cắt đuôi có fade và gắn cảnh báo.
"""

from __future__ import annotations

import logging
import shutil

from .. import audio
from ..backends.tts import get_tts
from ..pipeline import stable_hash
from ..project import Project, Segment
from .base import BaseStep

log = logging.getLogger("vidub.align")


def available_end(project: Project, idx: int, ordered: list[Segment], cfg: dict) -> float:
    seg = ordered[idx]
    limit = seg.end + cfg.get("max_borrow", 0.6)
    if idx + 1 < len(ordered):
        limit = min(limit, ordered[idx + 1].start - cfg.get("min_gap", 0.08))
    if project.duration:
        limit = min(limit, project.duration)
    return max(limit, seg.end)


class Align(BaseStep):
    name = "align"

    def run(self, project: Project, ctx):
        cfg = ctx.section("align")
        syn_cfg = ctx.section("synthesize")
        ordered = sorted(project.segments, key=lambda s: s.start)
        tts = None
        for idx, seg in enumerate(ordered):
            if not seg.tts_natural or seg.status == "error":
                continue
            window_end = available_end(project, idx, ordered, cfg)
            key = stable_hash([seg.tts_key, seg.start, seg.end, round(window_end, 3), cfg])
            out = project.file("tts", f"seg{seg.id:04d}_final.wav")
            if not ctx.force and seg.align_key == key and out.exists():
                continue
            ctx.progress(self.name, idx / max(1, len(ordered)), f"câu {idx + 1}/{len(ordered)}")
            if tts is None:
                tts = get_tts(syn_cfg)
            self._align_one(project, seg, window_end, out, cfg, tts)
            seg.align_key = key
            project.save()
        return project

    @staticmethod
    def _align_one(project: Project, seg: Segment, window_end: float, out, cfg: dict, tts) -> None:
        target = seg.duration
        tol = cfg.get("ratio_tolerance", 0.05)
        work = project.file("tts", f"seg{seg.id:04d}_work.wav")
        shutil.copyfile(project.abs(seg.tts_natural), work)
        dur = seg.natural_dur or audio.duration(work)
        methods: list[str] = []

        # (b) điều khiển thời lượng ngay trong TTS
        if abs(dur / target - 1) > tol and tts.supports_duration:
            factor = min(max(target / dur, cfg.get("duration_factor_min", 0.75)), cfg.get("duration_factor_max", 1.25))
            timbre = project.abs(project.speakers[seg.speaker].timbre_prompt)
            tts.synthesize(seg.vi_text, timbre, project.abs(seg.style_prompt), work, duration_factor=factor)
            wav, sr = audio.load(work)
            audio.save(work, audio.trim_silence(wav, sr), sr)
            dur = audio.duration(work)
            methods.append(f"duration_factor={factor:.2f}")

        # (c) co giãn thời gian, giữ cao độ
        if abs(dur / target - 1) > tol:
            max_stretch = cfg.get("max_stretch", 0.10)
            rate = min(max(dur / target, 1 - max_stretch), 1 + max_stretch)
            stretched = project.file("tts", f"seg{seg.id:04d}_stretch.wav")
            audio.time_stretch(work, stretched, rate)
            shutil.move(stretched, work)
            dur = audio.duration(work)
            methods.append(f"stretch={rate:.3f}")

        # (d) mượn khoảng lặng / cắt đuôi
        wav, sr = audio.load(work)
        allowed = window_end - seg.start
        seg.warnings = [w for w in seg.warnings if not w.startswith(("lệch", "cắt"))]
        if dur > target + 1e-3:
            methods.append(f"borrow={min(dur, allowed) - target:.2f}s")
        if dur > allowed:
            wav = audio.fade(wav[: int(allowed * sr)], sr, fade_in=0.0, fade_out=0.08)
            seg.warnings.append(f"cắt {dur - allowed:.2f}s cuối")
            dur = allowed
        audio.save(out, wav, sr)
        work.unlink(missing_ok=True)

        seg.tts_audio = project.rel(out)
        seg.place_start = seg.start
        seg.duration_ratio = round(dur / target, 3)
        seg.align_method = methods
        seg.status = "done"
        if abs(seg.duration_ratio - 1) > cfg.get("warn_ratio", 0.10):
            seg.warnings.append(f"lệch thời lượng {100 * (seg.duration_ratio - 1):+.0f}%")
