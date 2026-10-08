"""Dịch theo cảnh bằng LLM, có ràng buộc số âm tiết cho từng câu.

Backend: `openrouter` (API kiểu OpenAI; mặc định google/gemini-2.5-flash, key OPENROUTER_API_KEY),
`anthropic` (ANTHROPIC_API_KEY), `copy` (giữ câu gốc, để test).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

log = logging.getLogger("vidub.llm")


@dataclass
class Line:
    id: int
    speaker: str          # tên nhân vật
    src: str
    duration: float
    max_syllables: int
    vi: str = ""          # bản dịch hiện có (làm ngữ cảnh, hoặc bản cần rút gọn)
    todo: bool = True     # True = cần dịch / rút gọn câu này


SYSTEM_PROMPT = """You are a professional dubbing translator producing Vietnamese voice-over scripts for films.

You receive one scene: a list of characters (with optional notes on gender, age, relationships) and the scene's dialogue lines in order. Lines marked "todo": false already have a Vietnamese line; use them only as context and keep pronouns consistent with them.

For every line marked "todo": true, write the Vietnamese line an actor will speak:
- Natural spoken Vietnamese, not written style. Keep meaning, tone, and emotion; drop filler words if needed.
- Length is a hard constraint: the line must fit the original timing. Use at most "max_syllables" Vietnamese syllables (one syllable = one space-separated word) and aim for 80-100% of it. Shorten by paraphrasing rather than cutting meaning.
- Choose Vietnamese pronouns (tôi/tao/anh/em/chị/cậu/ông/bà/con/cháu...) from the speakers' relationship, age, and the scene's tone, and keep them consistent across the scene.
- Keep personal names and place names as in the source. Write numbers as Vietnamese words.
- Output only the spoken words: no stage directions, notes, quotes, or speaker labels.

Return a translation for every todo line id and no others."""

SHORTEN_PROMPT = """Some Vietnamese dubbing lines are too long for their timing. Rewrite each one so it has at most "max_syllables" syllables (one syllable = one space-separated word), keeping the meaning, emotion, and the pronouns already used. Return every listed id."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "vi": {"type": "string"}},
                "required": ["id", "vi"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["lines"],
    "additionalProperties": False,
}


class Translator:
    def translate_scene(self, lines: list[Line], characters: dict[str, str], src_lang: str) -> dict[int, str]:
        raise NotImplementedError

    def shorten(self, lines: list[Line], characters: dict[str, str]) -> dict[int, str]:
        raise NotImplementedError


class CopyTranslator(Translator):
    """Giữ nguyên câu gốc, cắt theo ngân sách âm tiết. Chỉ để test pipeline."""

    def translate_scene(self, lines, characters, src_lang):
        return {l.id: " ".join(l.src.split()[: l.max_syllables]) for l in lines if l.todo}

    def shorten(self, lines, characters):
        return {l.id: " ".join(l.vi.split()[: l.max_syllables]) for l in lines}


class LLMTranslator(Translator):
    """Dựng payload theo cảnh và kiểm tra kết quả; lớp con chỉ cài `_call` (gọi API, trả JSON {"lines": [...]})."""

    def _call(self, system: str, payload: dict, expect_ids: set[int]) -> dict[int, str]:
        raise NotImplementedError

    @staticmethod
    def _collect(data: dict, expect_ids: set[int]) -> dict[int, str]:
        out = {int(x["id"]): x["vi"].strip() for x in data["lines"]}
        missing = expect_ids - out.keys()
        if missing:
            log.warning("LLM thiếu bản dịch cho các câu %s", sorted(missing))
        return {k: v for k, v in out.items() if k in expect_ids}

    def translate_scene(self, lines, characters, src_lang):
        payload = {
            "source_language": src_lang,
            "characters": [{"name": n, "notes": note} for n, note in characters.items()],
            "lines": [
                {"id": l.id, "speaker": l.speaker, "text": l.src, "duration_sec": round(l.duration, 2),
                 "max_syllables": l.max_syllables, "todo": l.todo, **({} if l.todo else {"vi": l.vi})}
                for l in lines
            ],
        }
        return self._call(SYSTEM_PROMPT, payload, {l.id for l in lines if l.todo})

    def shorten(self, lines, characters):
        payload = {
            "characters": [{"name": n, "notes": note} for n, note in characters.items()],
            "lines": [
                {"id": l.id, "speaker": l.speaker, "source": l.src, "current_vi": l.vi,
                 "max_syllables": l.max_syllables}
                for l in lines
            ],
        }
        return self._call(SHORTEN_PROMPT, payload, {l.id for l in lines})


class AnthropicTranslator(LLMTranslator):
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium", **_):
        import anthropic

        self.anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort

    def _call(self, system: str, payload: dict, expect_ids: set[int]) -> dict[int, str]:
        resp = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            # Lời thoại phim có thể có bạo lực / chửi thề: nếu bị từ chối thì
            # server tự chạy lại bằng mô hình dự phòng trong cùng một lời gọi.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"LLM từ chối dịch cảnh này: {getattr(resp, 'stop_details', None)}")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("LLM hết max_tokens; giảm translate.max_lines_per_scene")
        text = next(b.text for b in resp.content if b.type == "text")
        return self._collect(json.loads(text), expect_ids)


class OpenAICompatTranslator(LLMTranslator):
    """API kiểu OpenAI: OpenRouter (mặc định), hoặc vLLM / OpenAI qua `base_url`."""

    def __init__(self, model: str = "google/gemini-2.5-flash", base_url: str = "https://openrouter.ai/api/v1",
                 api_key_env: str = "OPENROUTER_API_KEY", temperature: float = 0.3, max_retries: int = 3, **_):
        from openai import OpenAI

        key = os.environ.get(api_key_env)
        if not key:
            raise RuntimeError(f"Chưa đặt {api_key_env}: thêm vào file .env (xem .env.example)")
        self.client = OpenAI(base_url=base_url, api_key=key)
        self.model, self.temperature, self.max_retries = model, temperature, max_retries

    def _call(self, system: str, payload: dict, expect_ids: set[int]) -> dict[int, str]:
        for attempt in range(1, self.max_retries + 1):
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=16000,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "dubbing_lines", "strict": True, "schema": OUTPUT_SCHEMA}},
            )
            choice = resp.choices[0]
            if choice.finish_reason == "length":
                raise RuntimeError("LLM hết max_tokens; giảm translate.max_lines_per_scene")
            if choice.finish_reason == "content_filter":
                raise RuntimeError("LLM từ chối dịch cảnh này (content_filter)")
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (choice.message.content or "").strip())
            try:
                return self._collect(json.loads(text), expect_ids)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                log.warning("LLM trả JSON không hợp lệ (lần %d/%d): %s", attempt, self.max_retries, e)
        raise RuntimeError(f"LLM trả JSON không hợp lệ {self.max_retries} lần liền")


_CACHE: dict[str, Translator] = {}


def get_translator(cfg: dict) -> Translator:
    name = cfg.get("backend", "openrouter")
    key = json.dumps(cfg, sort_keys=True)
    if key not in _CACHE:
        if name == "copy":
            _CACHE[key] = CopyTranslator()
        elif name == "openrouter":
            _CACHE[key] = OpenAICompatTranslator(**{k: v for k, v in cfg.items() if k in (
                "model", "base_url", "api_key_env", "temperature", "max_retries")})
        elif name == "anthropic":
            _CACHE[key] = AnthropicTranslator(model=cfg.get("model", "claude-opus-5-5"),
                                              effort=cfg.get("effort", "medium"))
        else:
            raise ValueError(f"Translate backend không hỗ trợ: {name}")
    return _CACHE[key]
