"""Kiểm tra phần ghép nối của prepare_features bằng một IndexTTS2 giả (không cần trọng số thật)."""

import json
import sys
import types

import numpy as np
import pytest
import soundfile as sf

torch = pytest.importorskip("torch")
pytest.importorskip("torchaudio")


class FakeTTS:
    def __init__(self, cfg_path=None, model_dir=None, **kw):
        self.device = "cpu"
        self.text_process = types.SimpleNamespace(clean_pattern=__import__("re").compile("…"),
                                                  char_rep_map={"…": "..."})
        self.tokenizer = types.SimpleNamespace(encode=lambda s, allowed_special=None: [ord(c) % 500 for c in s])
        self.campplus_model = lambda fbank: torch.ones(1, 192)
        self.gpt = types.SimpleNamespace(get_emovec=lambda emb, lens: torch.ones(1, 1280))

    def extract_features(self, audio, sampling_rate, return_tensors):
        n = audio.shape[-1] // 320                       # 50 Hz như w2v-BERT
        return {"input_features": torch.zeros(1, n, 160), "attention_mask": torch.ones(1, n)}

    def get_emb(self, feats, mask):
        return torch.zeros(1, feats.shape[1], 1024)

    def get_scode(self, emb):
        return torch.arange(emb.shape[1] // 2)[None]     # 25 Hz


@pytest.fixture
def fake_indextts(monkeypatch):
    infer = types.ModuleType("indextts.infer_v2_5")
    infer.IndexTTS2 = FakeTTS
    infer.apply_pronunciation_annotations = lambda s: s
    pkg = types.ModuleType("indextts")
    monkeypatch.setitem(sys.modules, "indextts", pkg)
    monkeypatch.setitem(sys.modules, "indextts.infer_v2_5", infer)
    from training.indextts25 import prepare_features as P
    monkeypatch.setattr(P, "import_indextts", lambda repo=None: None)
    return P


def test_prepare_features_shards_resume_pairs(fake_indextts, tmp_path, monkeypatch):
    P = fake_indextts
    rows = []
    for i in range(5):
        path = tmp_path / f"u{i}.wav"
        sf.write(path, (0.1 * np.random.randn(16000 * (2 + i))).astype("float32"), 16000)
        rows.append({"id": f"u{i}", "audio": str(path), "text": f"Ngày {i + 1} có 2 người…",
                     "speaker": f"s{i % 2}", "duration": 2.0 + i})
    manifest = tmp_path / "m.jsonl"
    manifest.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    out = tmp_path / "feats"

    argv = ["prep", str(manifest), str(out), "--model-dir", str(tmp_path), "--shard-size", "2",
            "--split-name", "train"]
    monkeypatch.setattr(sys, "argv", argv)
    P.main()
    shards = sorted(out.glob("feats_*.pt"))
    assert len(shards) == 3
    feats = {}
    for s in shards:
        feats.update(torch.load(s))
    assert set(feats) == {f"u{i}" for i in range(5)}
    f = feats["u2"]
    assert f["codes"].dtype == torch.int16 and len(f["codes"]) == (16000 * 4 // 320) // 2
    assert f["spk"].shape == (192,) and f["emo"].shape == (1280,)
    # văn bản đi qua front-end tiếng Việt: chữ số -> chữ, viết thường, có tiền tố <|vi|>
    assert len(f["text_ids"]) == len("<|vi|> ngày ba có hai người...")

    pairs = [json.loads(l) for l in (out / "pairs_train.jsonl").read_text().splitlines()]
    assert all(rows[int(p["target"][1:])]["speaker"] == rows[int(p["prompt"][1:])]["speaker"] for p in pairs)
    assert all(p["target"] != p["prompt"] for p in pairs)

    # Chạy lại: không trích lại câu nào
    P.main()
    assert len(sorted(out.glob("feats_*.pt"))) == 3
