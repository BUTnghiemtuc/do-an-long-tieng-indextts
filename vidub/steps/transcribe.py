"""Bước 4: nhận dạng lời thoại (WhisperX, timestamp mức từ) và cắt thành câu."""

from __future__ import annotations

import logging
from pathlib import Path

from ..pipeline import file_sig, stable_hash
from ..project import Project, Segment, Speaker, Turn, Word
from ..srt import read_srt
from ..text import join_words, split_sentences
from .base import BaseStep

log = logging.getLogger("vidub.transcribe")

# Các trường thuộc về dịch / sinh giọng, được giữ lại khi nhận dạng lại cho ra câu y hệt.
_CARRY = ("vi_text", "vi_locked", "src_key", "max_syllables", "style_prompt", "tts_natural",
          "natural_dur", "tts_key", "tts_audio", "align_key", "place_start", "duration_ratio",
          "align_method", "status", "warnings")


class Transcribe(BaseStep):
    name = "transcribe"

    def fingerprint(self, project, ctx):
        return {
            "vocals": file_sig(project.abs(project.tracks.get("vocals"))),
            "turns": stable_hash([t.model_dump() for t in project.turns]),
            "srt": file_sig(sidecar_srt(project, ctx.section("transcribe"))),
            "lang": project.src_lang,
        }

    def outputs_exist(self, project):
        return bool(project.segments)

    def run(self, project, ctx):
        cfg = ctx.section("transcribe")
        backend = cfg.get("backend", "whisperx")
        if backend == "whisperx":
            words = self._whisperx(project, cfg)
            segments = words_to_segments(words, project.turns, cfg.get("pause_split", 0.6),
                                         cfg.get("max_sentence_dur", 12.0))
        elif backend == "srt":
            path = sidecar_srt(project, cfg)
            if path is None or not path.exists():
                raise FileNotFoundError(f"Backend srt cần file phụ đề gốc: {path}")
            segments = [
                Segment(id=i, start=round(c.start, 3), end=round(c.end, 3),
                        speaker=speaker_for(c.start, c.end, project.turns), src_text=c.text)
                for i, c in enumerate(read_srt(path))
            ]
        else:
            raise ValueError(f"transcribe.backend không hỗ trợ: {backend}")

        project.segments = carry_over(project.segments, segments)
        for spk in {s.speaker for s in project.segments} - project.speakers.keys():
            project.speakers[spk] = Speaker(name=spk)
        log.info("%d câu thoại", len(project.segments))
        return project

    @staticmethod
    def _whisperx(project: Project, cfg: dict) -> list[dict]:
        import whisperx

        device = cfg.get("device", "cuda")
        path = str(project.abs(project.tracks["vocals"]))
        wav = whisperx.load_audio(path)
        model = whisperx.load_model(cfg.get("model", "large-v3"), device,
                                    compute_type=cfg.get("compute_type", "float16"),
                                    language=project.src_lang)
        result = model.transcribe(wav, batch_size=cfg.get("batch_size", 16), language=project.src_lang)
        align_model, meta = whisperx.load_align_model(language_code=project.src_lang, device=device)
        result = whisperx.align(result["segments"], align_model, meta, wav, device,
                                return_char_alignments=False)
        words = []
        for seg in result["segments"]:
            for w in seg.get("words", []):
                if "start" in w and "end" in w:
                    words.append({"start": float(w["start"]), "end": float(w["end"]), "text": w["word"]})
        return words


def sidecar_srt(project: Project, cfg: dict) -> Path | None:
    if cfg.get("srt_path"):
        return Path(cfg["srt_path"])
    src = project.abs(project.source)
    return src.with_suffix(".srt") if src is not None else None


def speaker_for(start: float, end: float, turns: list[Turn]) -> str:
    """Người nói có thời gian chồng lấn lớn nhất; không chồng thì lấy lượt gần nhất."""
    if not turns:
        return "SPEAKER_00"
    best, best_ov = None, 0.0
    for t in turns:
        ov = min(end, t.end) - max(start, t.start)
        if ov > best_ov:
            best, best_ov = t.speaker, ov
    if best is not None:
        return best
    mid = (start + end) / 2
    return min(turns, key=lambda t: min(abs(mid - t.start), abs(mid - t.end))).speaker


def words_to_segments(words: list[dict], turns: list[Turn], pause_split: float, max_dur: float) -> list[Segment]:
    for w in words:
        w["speaker"] = speaker_for(w["start"], w["end"], turns)
    # Đổi người nói thì luôn ngắt câu.
    runs: list[list[dict]] = []
    for w in words:
        if runs and runs[-1][-1]["speaker"] == w["speaker"]:
            runs[-1].append(w)
        else:
            runs.append([w])
    segments = []
    for run in runs:
        for sent in split_sentences(run, pause_split, max_dur):
            segments.append(Segment(
                id=len(segments),
                start=round(sent[0]["start"], 3),
                end=round(sent[-1]["end"], 3),
                speaker=run[0]["speaker"],
                src_text=join_words(sent),
                words=[Word(start=w["start"], end=w["end"], text=w["text"]) for w in sent],
            ))
    return segments


def carry_over(old: list[Segment], new: list[Segment], tol: float = 0.3) -> list[Segment]:
    """Câu mới trùng nội dung và gần đúng thời điểm với câu cũ thì giữ bản dịch/giọng đã có."""
    for s in new:
        for o in old:
            if o.src_text == s.src_text and abs(o.start - s.start) < tol and abs(o.end - s.end) < tol:
                for f in _CARRY:
                    setattr(s, f, getattr(o, f))
                break
    return new
