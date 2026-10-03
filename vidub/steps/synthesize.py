"""Bước 6: sinh giọng tiếng Việt.

- Timbre prompt: clip sạch nhất 3–10 s của mỗi nhân vật, chọn một lần (người dùng đổi được).
- Style prompt: chính câu thoại gốc, để mang cảm xúc sang bản tiếng Việt.
Câu nào có key (văn bản + prompt + cấu hình TTS) không đổi thì không sinh lại.
"""

from __future__ import annotations

import logging

import numpy as np

from .. import audio
from ..backends.tts import backend_signature, get_tts
from ..pipeline import file_sig, stable_hash
from ..project import Project, Segment, Turn
from .base import BaseStep

log = logging.getLogger("vidub.synthesize")

PROMPT_SR = 24000


def overlap_with_others(seg: Segment, turns: list[Turn]) -> float:
    """Tỉ lệ thời gian câu bị người khác nói chồng lên."""
    ov = sum(max(0.0, min(seg.end, t.end) - max(seg.start, t.start)) for t in turns if t.speaker != seg.speaker)
    return ov / max(seg.duration, 1e-6)


def pick_timbre_span(project: Project, spk: str, min_dur: float, max_dur: float) -> tuple[float, float] | None:
    """Chọn khoảng thời gian làm giọng mẫu: ít bị chồng tiếng nhất, dài gần 6 s nhất.

    Không có câu nào đủ dài thì nối các câu liền nhau của cùng người nói.
    """
    segs = sorted((s for s in project.segments if s.speaker == spk), key=lambda s: s.start)
    if not segs:
        return None
    ideal = (min_dur + max_dur) / 2

    candidates: list[tuple[float, float, float]] = []   # (điểm, start, end)
    for i, s in enumerate(segs):
        start, end = s.start, s.end
        j = i
        while end - start < min_dur and j + 1 < len(segs) and segs[j + 1].start - end < 1.0:
            j += 1
            end = segs[j].end
        end = min(end, start + max_dur)
        dur = end - start
        overlap = max(overlap_with_others(x, project.turns) for x in segs[i:j + 1])
        score = -10 * overlap - abs(dur - ideal) / ideal - (2.0 if dur < min_dur else 0.0)
        candidates.append((score, start, end))
    _, start, end = max(candidates)
    return start, end


class Synthesize(BaseStep):
    name = "synthesize"

    def run(self, project: Project, ctx):
        cfg = ctx.section("synthesize")
        vocals, sr = audio.load(project.abs(project.tracks["vocals"]), sr=PROMPT_SR)
        self._prepare_prompts(project, vocals, sr, cfg)
        project.save()

        tts = None
        sig = backend_signature(cfg)
        todo = [s for s in project.segments if s.vi_text.strip()]
        for i, seg in enumerate(todo):
            timbre = project.abs(project.speakers[seg.speaker].timbre_prompt)
            key = stable_hash([seg.vi_text, file_sig(timbre), str(timbre), seg.style_prompt, sig])
            out = project.file("tts", f"seg{seg.id:04d}_natural.wav")
            if not ctx.force and seg.tts_key == key and out.exists():
                continue
            ctx.progress(self.name, i / max(1, len(todo)), f"câu {i + 1}/{len(todo)}")
            tts = tts or get_tts(cfg)
            try:
                tts.synthesize(seg.vi_text, timbre, project.abs(seg.style_prompt), out)
                wav, out_sr = audio.load(out)
                wav = audio.trim_silence(wav, out_sr)
                audio.save(out, wav, out_sr)
            except Exception as e:  # một câu lỗi không làm hỏng cả clip
                log.exception("Sinh giọng câu %d lỗi", seg.id)
                seg.status = "error"
                seg.warnings.append(f"lỗi TTS: {e}")
                continue
            seg.tts_natural = project.rel(out)
            seg.natural_dur = round(len(wav) / out_sr, 3)
            seg.tts_key = key
            seg.status = "synthesized"
            seg.warnings = [w for w in seg.warnings if not w.startswith("lỗi TTS")]
            project.save()
        return project

    @staticmethod
    def _prepare_prompts(project: Project, vocals: np.ndarray, sr: int, cfg: dict) -> None:
        min_dur, max_dur = cfg.get("timbre_min_dur", 3.0), cfg.get("timbre_max_dur", 10.0)
        for spk, speaker in project.speakers.items():
            if speaker.timbre_prompt and project.abs(speaker.timbre_prompt).exists():
                continue
            span = pick_timbre_span(project, spk, min_dur, max_dur)
            if span is None:
                continue
            path = project.file("prompts", f"{spk}_timbre.wav")
            audio.save(path, audio.fade(audio.cut(vocals, sr, *span), sr), sr)
            speaker.timbre_prompt = project.rel(path)
            log.info("Giọng mẫu %s: %.2f–%.2f s", spk, *span)

        for seg in project.segments:
            path = project.file("prompts", f"seg{seg.id:04d}_src.wav")
            if seg.style_prompt and path.exists():
                continue
            clip = audio.cut(vocals, sr, max(0.0, seg.start - 0.05), seg.end + 0.05)
            audio.save(path, audio.fade(clip, sr), sr)
            seg.style_prompt = project.rel(path)
