"""Backend sinh giọng.

Giao diện chung: synthesize(text, timbre_prompt, style_prompt, out_path, duration_factor=None).
- timbre_prompt: clip giọng mẫu của nhân vật (âm sắc).
- style_prompt: câu thoại gốc tiếng Anh (cảm xúc, ngữ điệu); None thì dùng timbre.
- duration_factor: thời lượng đích / thời lượng tự nhiên; None = tự nhiên.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import logging
from functools import lru_cache
from pathlib import Path

import numpy as np

from .. import audio
from ..text import vi_syllables

log = logging.getLogger("vidub.tts")


class TTSBackend:
    name = "base"
    supports_duration = False

    def synthesize(self, text: str, timbre_prompt: Path, style_prompt: Path | None, out_path: Path,
                   duration_factor: float | None = None) -> Path:
        raise NotImplementedError


class MockTTS(TTSBackend):
    """Sinh tín hiệu giống tiếng nói (không có nội dung) để chạy pipeline không cần GPU.

    Thời lượng ~ số âm tiết / tốc độ, có nhiễu theo hash câu để giống TTS thật
    (lúc dài lúc ngắn), và tôn trọng duration_factor.
    """

    name = "mock"
    supports_duration = True

    def __init__(self, sample_rate: int = 22050, syllables_per_sec: float = 5.0):
        self.sr = sample_rate
        self.rate = syllables_per_sec

    def synthesize(self, text, timbre_prompt, style_prompt, out_path, duration_factor=None):
        h = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        jitter = 0.85 + 0.35 * (h % 1000) / 1000          # 0.85..1.2
        n_syl = max(1, vi_syllables(text))
        dur = n_syl / self.rate * jitter * (duration_factor or 1.0)
        t = np.arange(int(dur * self.sr)) / self.sr
        f0 = 110 + (h % 7) * 15 + 20 * np.sin(2 * np.pi * 0.7 * t)
        phase = 2 * np.pi * np.cumsum(f0) / self.sr
        voice = sum(np.sin(k * phase) / k for k in range(1, 6))
        envelope = 0.5 * (1 - np.cos(2 * np.pi * self.rate * t)) # nhịp âm tiết
        wav = (0.2 * voice * envelope).astype(np.float32)
        audio.save(out_path, audio.fade(wav, self.sr), self.sr)
        return Path(out_path)


class IndexTTSBackend(TTSBackend):
    """Bọc lớp suy luận của IndexTTS2 / IndexTTS 2.5 / bản finetune.

    Chỉ truyền những tham số mà hàm `infer` thật sự có (kiểm tra bằng inspect), nên
    cùng một backend dùng được cho IndexTTS2 gốc, checkpoint dinhthuan và IndexTTS 2.5.
    """

    name = "indextts"

    def __init__(self, entry: str, model_dir: str, cfg_path: str, use_fp16: bool = True,
                 lang: str | None = "vi", emo_alpha: float = 0.8, use_style_prompt: bool = True,
                 **extra_init):
        mod_name, cls_name = entry.split(":")
        cls = getattr(importlib.import_module(mod_name), cls_name)
        init_kw = {"cfg_path": cfg_path, "model_dir": model_dir, "use_fp16": use_fp16, **extra_init}
        init_kw = _filter_kwargs(cls.__init__, init_kw)
        log.info("Nạp %s(%s)", entry, init_kw)
        self.model = cls(**init_kw)
        self.infer_params = set(inspect.signature(self.model.infer).parameters)
        self.supports_duration = "duration_factor" in self.infer_params
        self.lang = lang
        self.emo_alpha = emo_alpha
        self.use_style_prompt = use_style_prompt
        if not self.supports_duration:
            log.warning("infer() không có duration_factor: căn thời lượng sẽ chỉ dùng co giãn + mượn khoảng lặng")

    def synthesize(self, text, timbre_prompt, style_prompt, out_path, duration_factor=None):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        kw = {
            "spk_audio_prompt": str(timbre_prompt),
            "text": text,
            "output_path": str(out_path),
            "lang": self.lang,
            "verbose": False,
        }
        if self.use_style_prompt and style_prompt is not None:
            kw["emo_audio_prompt"] = str(style_prompt)
            kw["emo_alpha"] = self.emo_alpha
        if duration_factor is not None and self.supports_duration:
            kw["duration_factor"] = float(duration_factor)
        self.model.infer(**{k: v for k, v in kw.items() if k in self.infer_params and v is not None})
        return Path(out_path)


class CommandTTS(TTSBackend):
    """Gọi một lệnh ngoài cho mỗi câu — dùng cho baseline khác kiến trúc (F5-TTS-vi, VoxCPM...).

    Biến thay thế trong `command`: {text} {ref_audio} {ref_text} {style_audio} {out}.
    {ref_text} đọc từ file <ref_audio>.txt nếu có (F5-TTS cần transcript của giọng mẫu).
    Ví dụ: f5-tts_infer-cli -m F5TTS_Base -p ckpt.pt -v vocab.txt -r {ref_audio} -s {ref_text} -t {text} -o {out_dir} -w {out_name}
    """

    name = "command"

    def __init__(self, command: str, timeout: int = 600):
        self.command = command
        self.timeout = timeout

    def synthesize(self, text, timbre_prompt, style_prompt, out_path, duration_factor=None):
        import shlex
        import subprocess

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ref_txt = Path(str(timbre_prompt) + ".txt")
        values = {
            "text": text, "ref_audio": str(timbre_prompt), "style_audio": str(style_prompt or timbre_prompt),
            "ref_text": ref_txt.read_text(encoding="utf-8").strip() if ref_txt.exists() else "",
            "out": str(out_path), "out_dir": str(out_path.parent), "out_name": out_path.name,
        }
        args = [part.format(**values) for part in shlex.split(self.command)]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=self.timeout)
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"Lệnh TTS lỗi ({proc.returncode}): {proc.stderr[-1500:]}")
        return out_path


def _filter_kwargs(fn, kw: dict) -> dict:
    params = inspect.signature(fn).parameters
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return kw
    return {k: v for k, v in kw.items() if k in params}


@lru_cache(maxsize=4)
def _cached(name: str, kw_json: str) -> TTSBackend:
    kw = json.loads(kw_json)
    if name == "mock":
        return MockTTS(**kw)
    if name == "indextts":
        return IndexTTSBackend(**kw)
    if name == "command":
        return CommandTTS(**kw)
    raise ValueError(f"TTS backend không hỗ trợ: {name}")


def get_tts(cfg: dict) -> TTSBackend:
    """cfg = mục `synthesize` của cấu hình."""
    name = cfg.get("backend", "indextts")
    kw = dict(cfg.get(name, {}) or {})
    if name == "mock":
        kw.setdefault("syllables_per_sec", 5.0)
    return _cached(name, json.dumps(kw, sort_keys=True))


def backend_signature(cfg: dict) -> dict:
    """Phần cấu hình ảnh hưởng tới âm thanh sinh ra (dùng trong key cache từng câu)."""
    name = cfg.get("backend", "indextts")
    return {"backend": name, **(cfg.get(name, {}) or {})}
