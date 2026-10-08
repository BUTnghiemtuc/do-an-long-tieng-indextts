"""Ghép lại cặp (giọng mẫu, câu đích) từ đặc trưng đã trích, có lọc theo độ giống giọng.

prepare_features.py ghép cặp chỉ theo nhãn người nói. Chạy lệnh này sau đó để:
  - bỏ câu mẫu khác người thật (nhãn nhóm như kênh YouTube): --min-spk-sim 0.5
  - lấy câu mẫu cho dev từ train (dev chỉ 100 câu, ít người có 2 câu): --prompt-manifest

  python -m training.indextts25.make_pairs data/splits/train.jsonl data/features/train/pairs_train.jsonl \\
      --features data/features/train --min-spk-sim 0.5
  python -m training.indextts25.make_pairs data/splits/dev.jsonl data/features/dev/pairs_dev.jsonl \\
      --prompt-manifest data/splits/train.jsonl --features data/features/train data/features/dev --min-spk-sim 0.5
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import torch

from data_prep.common import read_jsonl, write_jsonl

from .data import make_pairs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", help="câu đích")
    ap.add_argument("out", help="pairs_<split>.jsonl")
    ap.add_argument("--features", nargs="+", required=True, help="thư mục feats_*.pt (lấy vector giọng)")
    ap.add_argument("--prompt-manifest", help="kho câu mẫu (mặc định = manifest)")
    ap.add_argument("--min-spk-sim", type=float, default=0.5)
    ap.add_argument("--pairs-per-utt", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    spk = {}
    for d in args.features:
        for f in sorted(Path(d).glob("feats_*.pt")):
            spk.update({k: v["spk"] for k, v in torch.load(f, map_location="cpu").items()})
    rows = list(read_jsonl(args.manifest))
    prompts = list(read_jsonl(args.prompt_manifest)) if args.prompt_manifest else None
    pairs = make_pairs(rows, args.pairs_per_utt, seed=args.seed, prompts=prompts, spk=spk, min_sim=args.min_spk_sim)

    ds = {r["id"]: r.get("dataset", "?") for r in rows}
    n_tgt = Counter(ds[p["target"]] for p in {p["target"]: p for p in pairs}.values())
    n_all = Counter(r.get("dataset", "?") for r in rows)
    for k in sorted(n_all):
        print(f"  {k}: {n_tgt[k]}/{n_all[k]} câu đích còn câu mẫu đạt ngưỡng")
    write_jsonl(args.out, pairs)
    print(f"{len(pairs)} cặp ({len(n_tgt) and sum(n_tgt.values())} câu đích) -> {args.out}")


if __name__ == "__main__":
    main()
