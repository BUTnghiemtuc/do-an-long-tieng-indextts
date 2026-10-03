"""Chia tập train / dev / test zero-shot theo người nói và tạo bộ test TTS.

- test: 20–30 người nói KHÔNG xuất hiện khi train; mỗi câu test có prompt là một câu
  khác của cùng người nói (zero-shot), chọn tổng --test-utts câu.
- dev: --dev-utts câu của người nói trong train (chấm checkpoint, seed cố định).
- crossling (tuỳ chọn): prompt tiếng Anh (--en-prompts thư mục wav) + văn bản tiếng Việt.

  python -m data_prep.split data/clean/all.jsonl data/splits --test-speakers 25
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path

from .common import read_jsonl, write_jsonl


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="+", help="một hoặc nhiều manifest đã lọc")
    ap.add_argument("out_dir")
    ap.add_argument("--test-speakers", type=int, default=25)
    ap.add_argument("--test-utts", type=int, default=200)
    ap.add_argument("--dev-utts", type=int, default=100)
    ap.add_argument("--min-test-spk-utts", type=int, default=5)
    ap.add_argument("--en-prompts", help="thư mục wav tiếng Anh cho bộ cross-lingual")
    ap.add_argument("--crossling-utts", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = [r for m in args.manifest for r in read_jsonl(m)]
    by_spk: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_spk[r["speaker"]].append(r)

    # Người nói test: lấy rải đều các bộ dữ liệu, đủ số câu để có prompt + target.
    eligible = sorted(s for s, u in by_spk.items() if len(u) >= args.min_test_spk_utts)
    rng.shuffle(eligible)
    by_ds: dict[str, list[str]] = defaultdict(list)
    for s in eligible:
        by_ds[s.split(":")[0]].append(s)
    test_spk: list[str] = []
    while len(test_spk) < args.test_speakers and any(by_ds.values()):
        for ds in sorted(by_ds):
            if by_ds[ds] and len(test_spk) < args.test_speakers:
                test_spk.append(by_ds[ds].pop())
    test_set = set(test_spk)

    train = [r for r in rows if r["speaker"] not in test_set]
    rng.shuffle(train)
    dev, train = train[: args.dev_utts], train[args.dev_utts:]

    per_spk = max(1, args.test_utts // max(1, len(test_spk)))
    test = []
    for s in test_spk:
        utts = sorted(by_spk[s], key=lambda r: r["duration"])
        prompts = [u for u in utts if 3.0 <= u["duration"] <= 10.0] or utts
        for tgt in rng.sample(utts, min(per_spk, len(utts))):
            prompt = next((p for p in prompts if p["id"] != tgt["id"]), None)
            if prompt:
                test.append({"id": tgt["id"], "text": tgt.get("text_norm", tgt["text"]), "speaker": s,
                             "prompt_audio": prompt["audio"], "prompt_text": prompt.get("text_norm", prompt["text"]),
                             "ref_audio": tgt["audio"]})
    test = test[: args.test_utts]

    out = Path(args.out_dir)
    write_jsonl(out / "train.jsonl", train)
    write_jsonl(out / "dev.jsonl", dev)
    write_jsonl(out / "test_zeroshot.jsonl", test)
    # dev cũng được dùng như bộ test TTS (prompt = câu khác cùng người nói trong train)
    dev_prompts = defaultdict(list)
    for r in train:
        if 3.0 <= r["duration"] <= 10.0:
            dev_prompts[r["speaker"]].append(r)
    dev_tts = [{"id": r["id"], "text": r.get("text_norm", r["text"]), "speaker": r["speaker"],
                "prompt_audio": dev_prompts[r["speaker"]][0]["audio"], "ref_audio": r["audio"]}
               for r in dev if dev_prompts[r["speaker"]]]
    write_jsonl(out / "dev_tts.jsonl", dev_tts)

    if args.en_prompts:
        en = sorted(Path(args.en_prompts).glob("*.wav"))
        texts = rng.sample(test, min(args.crossling_utts, len(test)))
        write_jsonl(out / "test_crossling.jsonl", [
            {"id": f"xl_{i:04d}", "text": t["text"], "prompt_audio": str(rng.choice(en).resolve())}
            for i, t in enumerate(texts)
        ])

    hours = lambda rs: sum(r["duration"] for r in rs) / 3600  # noqa: E731
    print(f"train: {len(train)} câu, {hours(train):.1f} giờ, {len({r['speaker'] for r in train})} người nói")
    print(f"dev: {len(dev)} câu ({len(dev_tts)} có prompt) | test zero-shot: {len(test)} câu, {len(test_spk)} người nói")


if __name__ == "__main__":
    main()
