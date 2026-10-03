from vidub.config import load_config, parse_override
from vidub.pipeline import select_steps
from vidub.project import Segment, Turn
from vidub.steps.diarize import merge_turns
from vidub.steps.transcribe import speaker_for, words_to_segments
from vidub.steps.translate import split_scenes
from vidub.text import en_syllables, split_sentences, syllable_budget, vi_syllables


def test_vi_syllables():
    assert vi_syllables("Anh chưa bao giờ nghe em cả.") == 7
    assert vi_syllables("Dừng lại!") == 2
    assert vi_syllables("") == 0


def test_en_syllables_rough():
    assert 5 <= en_syllables("You never listened to me.") <= 8


def test_budget():
    assert syllable_budget(2.0, 5.0) == 10
    assert syllable_budget(0.05, 5.0) == 1


def test_split_sentences_on_punct_and_pause():
    words = [
        {"start": 0.0, "end": 0.3, "text": "Hello"},
        {"start": 0.35, "end": 0.6, "text": "there."},
        {"start": 0.7, "end": 1.0, "text": "How"},
        {"start": 1.05, "end": 1.3, "text": "are"},
        {"start": 2.5, "end": 2.8, "text": "you"},
    ]
    sents = split_sentences(words, pause_split=0.6)
    assert [len(s) for s in sents] == [2, 2, 1]


def test_split_long_sentence_at_largest_gap():
    words = [{"start": i * 1.0, "end": i * 1.0 + 0.8, "text": "w"} for i in range(10)]
    words[6]["start"] += 0.15  # khoảng lặng lớn nhất trước từ thứ 7
    words[6]["end"] += 0.15
    sents = split_sentences(words, pause_split=5, max_dur=8)
    assert [len(s) for s in sents] == [6, 4]


def test_speaker_assignment_and_turn_merge():
    turns = merge_turns([Turn(start=0, end=1, speaker="A"), Turn(start=1.2, end=2, speaker="A"),
                         Turn(start=2.5, end=4, speaker="B")], gap=0.5)
    assert [(t.start, t.end, t.speaker) for t in turns] == [(0, 2, "A"), (2.5, 4, "B")]
    assert speaker_for(2.6, 3.0, turns) == "B"
    assert speaker_for(2.1, 2.2, turns) == "A"  # không chồng lấn -> lượt gần nhất


def test_words_to_segments_break_on_speaker_change():
    turns = [Turn(start=0, end=1.0, speaker="A"), Turn(start=1.0, end=2.0, speaker="B")]
    words = [{"start": 0.1, "end": 0.4, "text": "Hi"}, {"start": 0.5, "end": 0.9, "text": "Bob"},
             {"start": 1.1, "end": 1.5, "text": "Hey."}]
    segs = words_to_segments(words, turns, 0.6, 12)
    assert [(s.speaker, s.src_text) for s in segs] == [("A", "Hi Bob"), ("B", "Hey.")]


def test_scenes():
    segs = [Segment(id=i, start=s, end=s + 1, speaker="A", src_text="x") for i, s in enumerate([0, 1.5, 6, 7.2])]
    assert [[s.id for s in sc] for sc in split_scenes(segs, gap=2.0, max_lines=10)] == [[0, 1], [2, 3]]
    assert [[s.id for s in sc] for sc in split_scenes(segs, gap=2.0, max_lines=1)] == [[0], [1], [2], [3]]


def test_config_overrides():
    assert parse_override("a.b.c=1") == {"a": {"b": {"c": 1}}}
    cfg = load_config(overrides=["synthesize.backend=mock", "align.max_stretch=0.2"])
    assert cfg["synthesize"]["backend"] == "mock"
    assert cfg["align"]["max_stretch"] == 0.2
    assert cfg["align"]["max_borrow"] == 0.6  # khoá khác giữ nguyên


def test_select_steps():
    assert select_steps(from_step="synthesize") == ["synthesize", "align", "mix"]
    assert select_steps(only=["mix", "extract"]) == ["extract", "mix"]
