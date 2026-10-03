"""Dataset cặp (giọng mẫu, câu đích) từ đặc trưng đã trích sẵn.

Thư mục đặc trưng (do prepare_features.py tạo):
    feats_*.pt     dict id -> {"text_ids": int32[L], "codes": int16[T], "spk": f16[192], "emo": f16[D]}
    pairs_<split>.jsonl  mỗi dòng {"target": id, "prompt": id}
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import torch
from torch.utils.data import Dataset, Sampler

from .model import Batch


def load_features(feat_dir: str | Path) -> dict[str, dict]:
    feats: dict[str, dict] = {}
    for f in sorted(Path(feat_dir).glob("feats_*.pt")):
        feats.update(torch.load(f, map_location="cpu"))
    if not feats:
        raise FileNotFoundError(f"Không có feats_*.pt trong {feat_dir}")
    return feats


def load_pairs(path: str | Path) -> list[tuple[str, str]]:
    with open(path, encoding="utf-8") as f:
        return [(r["target"], r["prompt"]) for r in map(json.loads, f) if r]


class PairDataset(Dataset):
    def __init__(self, feats: dict[str, dict], pairs: list[tuple[str, str]],
                 max_text_tokens: int = 600, max_mel_tokens: int = 1815):
        # bỏ cặp thiếu đặc trưng hoặc dài quá giới hạn của model (+2 cho start/stop)
        self.feats = feats
        self.pairs = [(t, p) for t, p in pairs if t in feats and p in feats
                      and len(feats[t]["text_ids"]) + 2 <= max_text_tokens
                      and len(feats[t]["codes"]) + 2 <= max_mel_tokens]
        self.dropped = len(pairs) - len(self.pairs)

    def __len__(self) -> int:
        return len(self.pairs)

    def length(self, i: int) -> int:
        t = self.feats[self.pairs[i][0]]
        return len(t["text_ids"]) + len(t["codes"])

    def __getitem__(self, i: int) -> dict:
        tgt, prm = self.pairs[i]
        t, p = self.feats[tgt], self.feats[prm]
        return {"text_ids": t["text_ids"].long(), "codes": t["codes"].long(),
                "spk": p["spk"].float(), "emo": p["emo"].float()}


def collate(items: list[dict]) -> Batch:
    return Batch([x["text_ids"] for x in items], [x["codes"] for x in items],
                 torch.stack([x["spk"] for x in items]), torch.stack([x["emo"] for x in items]))


class BucketBatchSampler(Sampler[list[int]]):
    """Gom các mẫu dài gần bằng nhau vào cùng batch để ít phải đệm; thứ tự batch vẫn ngẫu nhiên."""

    def __init__(self, dataset: PairDataset, batch_size: int, seed: int = 1234, bucket_factor: int = 50,
                 drop_last: bool = False):
        self.ds, self.bs, self.seed, self.factor, self.drop_last = dataset, batch_size, seed, bucket_factor, drop_last
        self.epoch = 0

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def __iter__(self):
        rng = random.Random(self.seed + self.epoch)
        idx = list(range(len(self.ds)))
        rng.shuffle(idx)
        chunk = self.bs * self.factor
        batches = []
        for s in range(0, len(idx), chunk):
            part = sorted(idx[s:s + chunk], key=self.ds.length)
            batches += [part[k:k + self.bs] for k in range(0, len(part), self.bs)]
        if self.drop_last:
            batches = [b for b in batches if len(b) == self.bs]
        rng.shuffle(batches)
        return iter(batches)

    def __len__(self) -> int:
        n = len(self.ds) // self.bs
        return n if self.drop_last else n + (len(self.ds) % self.bs > 0)


def make_pairs(manifest: list[dict], pairs_per_utt: int = 2, prompt_min: float = 3.0, prompt_max: float = 15.0,
               seed: int = 1234) -> list[dict]:
    """Mỗi câu đích ghép với `pairs_per_utt` câu khác cùng người nói làm giọng mẫu.

    Ưu tiên giọng mẫu dài 3–15 s (IndexTTS cắt prompt ở 15 s). Bản tiếng Đức dùng 2 cặp/câu.
    """
    rng = random.Random(seed)
    by_spk: dict[str, list[dict]] = {}
    for r in manifest:
        by_spk.setdefault(r["speaker"], []).append(r)
    pairs = []
    for r in manifest:
        others = [o for o in by_spk[r["speaker"]] if o["id"] != r["id"]]
        good = [o for o in others if prompt_min <= o["duration"] <= prompt_max] or others
        for o in rng.sample(good, min(pairs_per_utt, len(good))):
            pairs.append({"target": r["id"], "prompt": o["id"]})
    return pairs
