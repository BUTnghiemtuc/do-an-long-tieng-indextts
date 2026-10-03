from pathlib import Path

from vidub.audio import probe_duration
from vidub.config import load_config
from vidub.pipeline import Context, run_pipeline
from vidub.project import Project
from vidub.srt import read_srt

MOCK = Path(__file__).resolve().parent.parent / "configs" / "mock.yaml"


def run(project, cfg, steps=None):
    return run_pipeline(project, Context(cfg=cfg), steps)


def test_end_to_end_mock(sample_clip, tmp_path):
    cfg = load_config([MOCK])
    project = run(Project.create(tmp_path / "proj", sample_clip), cfg)

    assert len(project.segments) == 4
    assert all(s.status == "done" for s in project.segments)
    assert project.speakers["SPEAKER_00"].timbre_prompt
    assert project.abs(project.speakers["SPEAKER_00"].timbre_prompt).exists()

    video = project.abs(project.outputs["video"])
    assert video.exists() and abs(probe_duration(video) - 14) < 0.5
    assert len(read_srt(project.abs(project.outputs["srt_vi"]))) == 4

    # Mỗi câu phải nằm gọn trong khoảng trống trước câu kế tiếp.
    ordered = sorted(project.segments, key=lambda s: s.start)
    for a, b in zip(ordered, ordered[1:]):
        assert a.place_start + a.duration * a.duration_ratio <= b.start + 1e-3

    # Nạp lại từ đĩa ra đúng nội dung.
    again = Project.load(project.dir)
    assert again.segments[1].vi_text == project.segments[1].vi_text


def test_cache_and_single_segment_regen(sample_clip, tmp_path):
    cfg = load_config([MOCK])
    project = run(Project.create(tmp_path / "proj", sample_clip), cfg)
    keys = {s.id: s.tts_key for s in project.segments}
    mtimes = {s.id: project.abs(s.tts_natural).stat().st_mtime_ns for s in project.segments}

    # Chạy lại: không câu nào bị sinh lại.
    project = run(project, cfg)
    assert {s.id: project.abs(s.tts_natural).stat().st_mtime_ns for s in project.segments} == mtimes

    # Sửa câu 2 -> chỉ câu 2 được sinh lại; bước dịch không ghi đè bản sửa tay.
    seg = project.segment(2)
    seg.vi_text = "Dừng lại ngay"
    seg.vi_locked = True
    project = run(project, cfg, ["translate", "synthesize", "align", "mix"])
    assert project.segment(2).vi_text == "Dừng lại ngay"
    changed = [s.id for s in project.segments if s.tts_key != keys[s.id]]
    assert changed == [2]


def test_speaker_rename_survives_rediarize(sample_clip, tmp_path):
    cfg = load_config([MOCK])
    project = run(Project.create(tmp_path / "proj", sample_clip), cfg)
    project.speakers["SPEAKER_00"].name = "Celia"
    project.save()
    project = run_pipeline(project, Context(cfg=cfg, force=True), ["diarize"])
    assert project.speakers["SPEAKER_00"].name == "Celia"
