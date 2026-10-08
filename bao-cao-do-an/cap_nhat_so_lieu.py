"""Cập nhật các CSV trong bao-cao-do-an/so-lieu/ từ kết quả mới nhất trong repo.

  python bao-cao-do-an/cap_nhat_so_lieu.py

Ghi lại: tong-hop-danh-gia-tts.csv (mọi results/tts/*/summary.json), duong-loss-train.csv,
duong-loss-dev.csv (runs/*/log.jsonl), ket-qua-run2.md và bản sao scores.csv của các hệ thống chính.
pheu-loc-du-lieu.csv và benchmark-vram.csv nhập tay từ log, không ghi đè ở đây.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bao-cao-do-an" / "so-lieu"
RUNS = ["overfit", "run1_lr5e-5", "run1_lr2e-5", "run2", "run3_pilot", "run3_pilot_p1"]
MAIN = ["test_base", "test_dinhthuan", "test_r1_lr5e-5_9159", "test_r2_028000", "emo_base", "emo_dinhthuan",
        "emo_r2_028000", "emo_r3p_9200", "emo_r3p1_9200", "dev3_base", "dev3_r2_028000", "dev3_r3p_9200",
        "dev3_r3p1_9200"]
TRAIN_KEYS = ["step", "epoch", "lr", "loss", "text_loss", "mel_loss", "mel_acc", "grad_norm", "elapsed_s", "max_vram_gb"]


def summaries() -> None:
    rows = []
    for p in sorted((ROOT / "results/tts").glob("*/summary.json")):
        s = json.loads(p.read_text())
        r = {"he_thong": s.get("name", p.parent.name)}
        for k, v in s.items():
            if isinstance(v, dict) and v.get("mean") is not None:
                r[k], r[k + "_n"] = round(v["mean"], 4), v.get("n")
        rows.append(r)
    keys = ["he_thong"] + sorted({k for r in rows for k in r} - {"he_thong"})
    with open(OUT / "tong-hop-danh-gia-tts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "hệ thống")


def losses() -> None:
    with open(OUT / "duong-loss-train.csv", "w", newline="") as f, open(OUT / "duong-loss-dev.csv", "w", newline="") as g:
        tw, dw = csv.writer(f), csv.writer(g)
        tw.writerow(["run"] + TRAIN_KEYS)
        dw.writerow(["run", "step", "dev_loss", "dev_text_loss", "dev_mel_loss", "dev_mel_acc"])
        for run in RUNS:
            log = ROOT / "runs" / run / "log.jsonl"
            if not log.exists():
                continue
            for line in log.open():
                x = json.loads(line)
                if "elapsed_s" in x:
                    tw.writerow([run] + [x.get(k) for k in TRAIN_KEYS])
                elif "dev" in x:
                    d = x["dev"]
                    dw.writerow([run, x["step"], d["loss"], d["text_loss"], d["mel_loss"], d["mel_acc"]])


def copies() -> None:
    (OUT / "ket-qua-tts").mkdir(exist_ok=True)
    for name in MAIN:
        src = ROOT / "results/tts" / name / "scores.csv"
        if src.exists():
            shutil.copy(src, OUT / "ket-qua-tts" / f"{name}.csv")
    shutil.copy(ROOT / "results/tts/report_run2.md", OUT / "ket-qua-run2.md")
    shutil.copy(ROOT / "docs/data_stats.md", OUT / "thong-ke-du-lieu-train.md")


if __name__ == "__main__":
    summaries()
    losses()
    copies()
