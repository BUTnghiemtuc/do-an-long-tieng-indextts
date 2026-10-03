"""Thống kê manifest cho chương 4 của báo cáo, và ước lượng tốc độ nói tiếng Việt.

Tốc độ nói (âm tiết/giây, trung vị) là giá trị nên đặt cho translate.vi_syllables_per_sec.

  python -m data_prep.stats data/splits/train.jsonl --md docs/data_stats.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from vidub.text import vi_syllables

from .common import read_jsonl

BINS = [0, 2, 4, 6, 8, 10, 15, 20, 25, 1e9]


def compute(rows: list[dict]) -> dict:
    durs = np.array([r["duration"] for r in rows])
    rates = np.array([vi_syllables(r.get("text_norm", r["text"])) / r["duration"] for r in rows if r["duration"] > 0])
    by_ds = defaultdict(lambda: {"utts": 0, "hours": 0.0, "speakers": set()})
    for r in rows:
        d = by_ds[r.get("dataset", "?")]
        d["utts"] += 1
        d["hours"] += r["duration"] / 3600
        d["speakers"].add(r["speaker"])
    spk_hours = Counter()
    for r in rows:
        spk_hours[r["speaker"]] += r["duration"] / 3600
    hist, _ = np.histogram(durs, bins=BINS)
    return {
        "utterances": len(rows),
        "hours": round(float(durs.sum()) / 3600, 2),
        "speakers": len(spk_hours),
        "duration_sec": {"mean": round(float(durs.mean()), 2), "median": round(float(np.median(durs)), 2),
                         "p5": round(float(np.quantile(durs, 0.05)), 2), "p95": round(float(np.quantile(durs, 0.95)), 2)},
        "duration_hist": {f"{BINS[i]}-{BINS[i + 1] if BINS[i + 1] < 1e9 else '+'}s": int(h) for i, h in enumerate(hist)},
        "syllables_per_sec": {"median": round(float(np.median(rates)), 2), "p10": round(float(np.quantile(rates, 0.1)), 2),
                              "p90": round(float(np.quantile(rates, 0.9)), 2)},
        "hours_per_speaker": {"median": round(float(np.median(list(spk_hours.values()))), 3),
                              "max": round(max(spk_hours.values()), 2)},
        "by_dataset": {k: {"utts": v["utts"], "hours": round(v["hours"], 2), "speakers": len(v["speakers"])}
                       for k, v in sorted(by_ds.items())},
    }


def to_markdown(s: dict) -> str:
    lines = [
        f"Tổng: **{s['hours']} giờ**, {s['utterances']} câu, {s['speakers']} người nói. "
        f"Tốc độ nói trung vị {s['syllables_per_sec']['median']} âm tiết/giây "
        f"(p10–p90: {s['syllables_per_sec']['p10']}–{s['syllables_per_sec']['p90']}).",
        "",
        "| Bộ dữ liệu | Số câu | Giờ | Người nói |", "| --- | ---: | ---: | ---: |",
        *[f"| {k} | {v['utts']} | {v['hours']} | {v['speakers']} |" for k, v in s["by_dataset"].items()],
        "",
        "| Độ dài câu | Số câu |", "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in s["duration_hist"].items()],
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="+")
    ap.add_argument("--md", help="ghi bảng markdown ra file")
    args = ap.parse_args()
    rows = [r for m in args.manifest for r in read_jsonl(m)]
    s = compute(rows)
    print(json.dumps(s, indent=2, ensure_ascii=False))
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(to_markdown(s), encoding="utf-8")


if __name__ == "__main__":
    main()
