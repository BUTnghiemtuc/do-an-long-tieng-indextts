import json
import subprocess
import sys
from pathlib import Path

import pytest

from data_prep.vi_normalize import normalize, number_to_words

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("n,words", [
    (0, "không"), (10, "mười"), (15, "mười lăm"), (21, "hai mươi mốt"), (24, "hai mươi tư"),
    (105, "một trăm lẻ năm"), (1005, "một nghìn không trăm lẻ năm"),
    (1_500_000, "một triệu năm trăm nghìn"), (3_000_000_000, "ba tỷ"),
])
def test_number_to_words(n, words):
    assert number_to_words(n) == words


def test_normalize_sentence():
    out = normalize("Ngày 25/11/2026 lúc 7h30, giá tăng 3,5% lên 1.200.000 đ.")
    assert out == ("Ngày hai mươi lăm tháng mười một năm hai nghìn không trăm hai mươi sáu lúc bảy giờ "
                   "ba mươi phút, giá tăng ba phẩy năm phần trăm lên một triệu hai trăm nghìn đồng.")
    assert not any(c.isdigit() for c in out)


def test_extend_tokenizer(tmp_path):
    spm = pytest.importorskip("sentencepiece")
    pytest.importorskip("google.protobuf")
    en = tmp_path / "en.txt"
    en.write_text("\n".join(["the quick brown fox jumps over the lazy dog"] * 200))
    spm.SentencePieceTrainer.train(input=str(en), model_prefix=str(tmp_path / "base"), vocab_size=40,
                                   model_type="bpe", character_coverage=1.0, minloglevel=2)
    manifest = tmp_path / "m.jsonl"
    manifest.write_text("\n".join(json.dumps({"text": t, "text_norm": t}, ensure_ascii=False)
                                  for t in ["anh có biết cô ấy đi đâu không"] * 30))
    out = tmp_path / "vi.model"
    subprocess.run([sys.executable, str(ROOT / "training" / "extend_tokenizer.py"), str(tmp_path / "base.model"),
                    str(manifest), str(out), "--num-syllables", "20", "--min-count", "2"],
                   check=True, capture_output=True)
    report = json.loads(out.with_suffix(".report.json").read_text())
    assert report["after"]["unk_tokens"] == 0
    assert report["after"]["tokens_per_syllable"] < report["before"]["tokens_per_syllable"]
    sp = spm.SentencePieceProcessor(model_file=str(out))
    assert "▁biết" in sp.encode("anh biết", out_type=str)


def test_eval_dubbing_duration_metrics(sample_clip, tmp_path):
    from eval.eval_dubbing import duration_metrics
    from vidub.config import load_config
    from vidub.pipeline import Context, run_pipeline
    from vidub.project import Project

    cfg = load_config([ROOT / "configs" / "mock.yaml"])
    project = run_pipeline(Project.create(tmp_path / "p", sample_clip), Context(cfg=cfg))
    m = duration_metrics([project])
    assert m["segments"] == 4
    assert 0 <= m["mean_abs_duration_error"] < 1
    assert 0 <= m["pct_within_10"] <= 100
