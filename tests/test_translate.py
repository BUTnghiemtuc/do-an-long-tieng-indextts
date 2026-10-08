"""Kiểm tra bước dịch với LLM giả: payload gửi đi, khoá câu sửa tay, vòng rút gọn."""

import json
from types import SimpleNamespace

import pytest

from vidub.backends import llm
from vidub.config import load_config
from vidub.pipeline import Context
from vidub.project import Project, Segment, Speaker
from vidub.steps.translate import Translate


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        payload = json.loads(kw["messages"][0]["content"])
        if "current_vi" in payload["lines"][0]:          # yêu cầu rút gọn
            out = [{"id": l["id"], "vi": "Dừng lại"} for l in payload["lines"]]
        else:
            out = [{"id": l["id"], "vi": "một hai ba bốn năm sáu bảy tám chín mười" if l["id"] == 1 else f"câu {l['id']}"}
                   for l in payload["lines"] if l["todo"]]
        text = json.dumps({"lines": out}, ensure_ascii=False)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture
def fake_translator(monkeypatch):
    t = llm.AnthropicTranslator.__new__(llm.AnthropicTranslator)
    t.model, t.effort = "claude-opus-5-5", "medium"
    t.client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))
    monkeypatch.setattr("vidub.steps.translate.get_translator", lambda cfg: t)
    return t


def make_project(tmp_path):
    p = Project.create(tmp_path / "p", tmp_path / "x.mp4")
    p.speakers = {"SPEAKER_00": Speaker(name="Celia", notes="nữ, 25 tuổi"),
                  "SPEAKER_01": Speaker(name="Thom", notes="nam, bạn trai Celia")}
    p.segments = [
        Segment(id=0, start=0.0, end=2.0, speaker="SPEAKER_00", src_text="You never listened to me."),
        Segment(id=1, start=2.5, end=3.3, speaker="SPEAKER_01", src_text="Stop it."),
        Segment(id=2, start=3.5, end=5.0, speaker="SPEAKER_00", src_text="Go away.", vi_text="Đi đi", vi_locked=True),
    ]
    return p


def test_translate_with_fake_llm(fake_translator, tmp_path):
    cfg = load_config(overrides=["translate.backend=anthropic", "translate.model=claude-opus-5-5",
                                 "translate.vi_syllables_per_sec=5.0"])
    project = Translate().run(make_project(tmp_path), Context(cfg=cfg))
    calls = fake_translator.client.beta.messages.calls

    first = calls[0]
    assert first["model"] == "claude-opus-5-5"
    assert first["output_config"]["format"]["type"] == "json_schema"
    sent = json.loads(first["messages"][0]["content"])
    assert {c["name"] for c in sent["characters"]} == {"Celia", "Thom"}
    assert [l["todo"] for l in sent["lines"]] == [True, True, False]   # câu khoá chỉ làm ngữ cảnh
    assert sent["lines"][2]["vi"] == "Đi đi"
    assert sent["lines"][1]["max_syllables"] == 4                       # 0.8 s * 5 âm tiết/s

    # Câu 1 dài 10 âm tiết > 4 -> có vòng rút gọn
    assert any("current_vi" in json.loads(c["messages"][0]["content"])["lines"][0] for c in calls[1:])
    assert project.segment(1).vi_text == "Dừng lại"
    assert project.segment(0).vi_text == "câu 0"
    assert project.segment(2).vi_text == "Đi đi"

    # Chạy lại: không gọi LLM nữa vì không câu nào đổi.
    n = len(calls)
    Translate().run(project, Context(cfg=cfg))
    assert len(calls) == n


def test_openrouter_translator_parses_json_and_retries(monkeypatch):
    from vidub.backends.llm import Line, OpenAICompatTranslator

    replies = iter(["không phải JSON", '```json\n{"lines": [{"id": 0, "vi": " Anh chưa bao giờ nghe em "}]}\n```'])
    calls = []

    def create(**kw):
        calls.append(kw)
        msg = SimpleNamespace(content=next(replies))
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=msg)])

    t = OpenAICompatTranslator.__new__(OpenAICompatTranslator)
    t.model, t.temperature, t.max_retries = "google/gemini-2.5-flash", 0.3, 3
    t.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    out = t.translate_scene([Line(0, "Celia", "You never listened to me.", 2.0, 8)], {"Celia": ""}, "en")
    assert out == {0: "Anh chưa bao giờ nghe em"}
    assert len(calls) == 2 and calls[0]["model"] == "google/gemini-2.5-flash"
    assert calls[0]["response_format"]["json_schema"]["schema"]["required"] == ["lines"]


def test_env_file_does_not_override_real_env(tmp_path, monkeypatch):
    from vidub.config import load_env_file

    f = tmp_path / ".env"
    f.write_text("# chú thích\nVIDUB_TEST_A=tu_file\nVIDUB_TEST_B='co nhay'\nVIDUB_TEST_C=\n")
    monkeypatch.setenv("VIDUB_TEST_A", "that")
    monkeypatch.delenv("VIDUB_TEST_B", raising=False)
    monkeypatch.delenv("VIDUB_TEST_C", raising=False)
    load_env_file(f)
    import os
    assert os.environ["VIDUB_TEST_A"] == "that" and os.environ["VIDUB_TEST_B"] == "co nhay"
    assert "VIDUB_TEST_C" not in os.environ
