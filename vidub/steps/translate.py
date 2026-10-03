"""Bước 5: dịch theo cảnh, có ngân sách âm tiết cho từng câu; câu quá dài thì rút gọn."""

from __future__ import annotations

import logging

from ..backends.llm import Line, get_translator
from ..pipeline import stable_hash
from ..project import Project, Segment
from ..text import syllable_budget, vi_syllables
from .base import BaseStep

log = logging.getLogger("vidub.translate")


def src_key(seg: Segment, cfg: dict) -> str:
    return stable_hash([seg.src_text, seg.speaker, round(seg.duration, 2), cfg.get("backend"), cfg.get("model")])


def split_scenes(segments: list[Segment], gap: float, max_lines: int) -> list[list[Segment]]:
    scenes: list[list[Segment]] = []
    for s in sorted(segments, key=lambda s: s.start):
        if scenes and s.start - scenes[-1][-1].end <= gap and len(scenes[-1]) < max_lines:
            scenes[-1].append(s)
        else:
            scenes.append([s])
    return scenes


class Translate(BaseStep):
    name = "translate"

    def run(self, project: Project, ctx):
        cfg = ctx.section("translate")
        rate = cfg.get("vi_syllables_per_sec", 5.0)
        tol = cfg.get("length_tolerance", 0.15)
        translator = get_translator(cfg)
        characters = {sp.name: sp.notes for sp in project.speakers.values()}

        def needs(s: Segment) -> bool:
            return not s.vi_locked and (ctx.force or not s.vi_text or s.src_key != src_key(s, cfg))

        for s in project.segments:
            s.max_syllables = syllable_budget(s.duration, rate)

        scenes = split_scenes(project.segments, cfg.get("scene_gap", 2.0), cfg.get("max_lines_per_scene", 25))
        todo_scenes = [sc for sc in scenes if any(needs(s) for s in sc)]
        for i, scene in enumerate(todo_scenes):
            ctx.progress(self.name, i / max(1, len(todo_scenes)), f"cảnh {i + 1}/{len(todo_scenes)}")
            lines = [self._line(project, s, todo=needs(s)) for s in scene]
            result = translator.translate_scene(lines, characters, project.src_lang)
            for s in scene:
                if s.id in result:
                    s.vi_text = result[s.id]
                    s.src_key = src_key(s, cfg)
                    s.status = "translated"
            project.save()

        # Rút gọn câu vượt ngân sách (tối đa N vòng); câu sửa tay thì chỉ cảnh báo.
        for round_ in range(cfg.get("max_shorten_rounds", 2)):
            too_long = [s for s in project.segments
                        if not s.vi_locked and s.vi_text and vi_syllables(s.vi_text) > s.max_syllables * (1 + tol)]
            if not too_long:
                break
            log.info("Vòng rút gọn %d: %d câu quá dài", round_ + 1, len(too_long))
            result = translator.shorten([self._line(project, s, todo=True) for s in too_long], characters)
            for s in too_long:
                if s.id in result:
                    s.vi_text = result[s.id]

        for s in project.segments:
            s.warnings = [w for w in s.warnings if not w.startswith("dịch dài")]
            n = vi_syllables(s.vi_text)
            if s.vi_text and n > s.max_syllables * (1 + tol):
                s.warnings.append(f"dịch dài: {n}/{s.max_syllables} âm tiết")
        return project

    @staticmethod
    def _line(project: Project, s: Segment, todo: bool) -> Line:
        return Line(id=s.id, speaker=project.speaker_name(s.speaker), src=s.src_text, duration=s.duration,
                    max_syllables=s.max_syllables or 1, vi=s.vi_text, todo=todo)
