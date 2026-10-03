"""IndexTTSBackend truyền đúng tham số cho cả IndexTTS 2.5 lẫn IndexTTS2 (kiểm tra bằng lớp giả)."""

import sys
import types

import pytest

from vidub.backends.tts import IndexTTSBackend


class Fake25:
    """Chữ ký giống indextts.infer_v2_5.IndexTTS2."""
    calls: list = []

    def __init__(self, cfg_path="", model_dir="", use_bf16=False, device=None, use_qwen_emo=False):
        self.init = dict(cfg_path=cfg_path, model_dir=model_dir, use_bf16=use_bf16)

    def infer(self, spk_audio_prompt, text, output_path, lang, emo_audio_prompt=None, emo_alpha=1.0,
              verbose=False, duration_factor=1.0, text_normalization=True, **generation_kwargs):
        Fake25.calls.append(dict(text=text, lang=lang, duration_factor=duration_factor,
                                 text_normalization=text_normalization, gen=generation_kwargs))


class Fake2:
    """Chữ ký giống indextts.infer_v2.IndexTTS2: không có lang, duration_factor."""
    calls: list = []

    def __init__(self, cfg_path="", model_dir="", use_fp16=False, **kw):
        pass

    def infer(self, spk_audio_prompt, text, output_path, emo_audio_prompt=None, emo_alpha=1.0,
              verbose=False, **generation_kwargs):
        Fake2.calls.append(dict(text=text, gen=generation_kwargs))


@pytest.fixture(autouse=True)
def fake_module(monkeypatch):
    mod = types.ModuleType("fake_indextts")
    mod.Fake25, mod.Fake2 = Fake25, Fake2
    monkeypatch.setitem(sys.modules, "fake_indextts", mod)
    Fake25.calls.clear()
    Fake2.calls.clear()


def test_indextts25_gets_lang_frontend_and_generation(tmp_path):
    b = IndexTTSBackend("fake_indextts:Fake25", "m", "m/config.yaml", lang="vi", text_frontend="vi",
                        generation={"temperature": 0.7, "top_k": 30})
    assert b.model.init["use_bf16"] is True and b.supports_duration
    b.synthesize("Ngày 2/9 có 3 người.", tmp_path / "p.wav", None, tmp_path / "o.wav", duration_factor=1.1)
    call = Fake25.calls[0]
    assert call["text"] == "ngày hai tháng chín có ba người."
    assert call["lang"] == "vi" and call["text_normalization"] is False and call["duration_factor"] == 1.1
    assert call["gen"] == {"temperature": 0.7, "top_k": 30}


def test_indextts2_never_receives_unknown_kwargs(tmp_path):
    b = IndexTTSBackend("fake_indextts:Fake2", "m", "m/config.yaml", lang="vi",
                        generation={"temperature": 0.7})
    assert not b.supports_duration
    b.synthesize("Xin chào", tmp_path / "p.wav", None, tmp_path / "o.wav", duration_factor=1.2)
    # lang / duration_factor / text_normalization không lọt vào **generation_kwargs của IndexTTS2
    assert Fake2.calls[0] == {"text": "Xin chào", "gen": {"temperature": 0.7}}
