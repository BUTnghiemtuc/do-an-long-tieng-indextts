"""Đánh giá tầng lồng tiếng trên các dự án đã chạy xong.

- Sai số thời lượng: trung bình |dur_vi - dur_src| / dur_src, và % câu lệch dưới 10%.
- Nhất quán giọng: SS giữa các câu cùng nhân vật (và với giọng mẫu).       (--ss, GPU)
- Chất lượng dịch: COMET-kiwi (không cần bản dịch tham chiếu).            (--comet, GPU)
- Xuất 50 câu ngẫu nhiên ra CSV để chấm tay độ đúng / tự nhiên.

  python -m eval.eval_dubbing runs/* --name full --ss --comet
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from vidub.pipeline import rtf_report
from vidub.project import Project
from vidub.text import vi_syllables

from . import metrics


def duration_metrics(projects: list[Project]) -> dict:
    errs = [abs(s.duration_ratio - 1) for p in projects for s in p.segments if s.duration_ratio]
    budget = [vi_syllables(s.vi_text) / s.max_syllables for p in projects for s in p.segments
              if s.max_syllables and s.vi_text]
    methods = defaultdict(int)
    for p in projects:
        for s in p.segments:
            for m in s.align_method:
                methods[m.split("=")[0]] += 1
    return {
        "segments": len(errs),
        "mean_abs_duration_error": round(float(np.mean(errs)), 4) if errs else None,
        "pct_within_10": round(100 * float(np.mean([e < 0.10 for e in errs])), 1) if errs else None,
        "syllables_over_budget_pct": round(100 * float(np.mean([b > 1.0 for b in budget])), 1) if budget else None,
        "align_methods": dict(methods),
        "truncated": sum(any(w.startswith("cắt") for w in s.warnings) for p in projects for s in p.segments),
    }


def voice_consistency(projects: list[Project], max_pairs: int = 50) -> dict:
    within, to_ref = [], []
    for p in projects:
        by_spk = defaultdict(list)
        for s in p.segments:
            if s.tts_audio:
                by_spk[s.speaker].append(str(p.abs(s.tts_audio)))
        for spk, wavs in by_spk.items():
            pairs = list(itertools.combinations(wavs, 2))
            random.Random(0).shuffle(pairs)
            within += [metrics.speaker_similarity(a, b) for a, b in pairs[:max_pairs]]
            ref = p.abs(p.speakers[spk].timbre_prompt)
            to_ref += [metrics.speaker_similarity(str(ref), w) for w in wavs]
    return {"ss_within_speaker": metrics.summarize(within), "ss_to_timbre": metrics.summarize(to_ref)}


def comet_kiwi(projects: list[Project]) -> dict:
    from comet import download_model, load_from_checkpoint

    model = load_from_checkpoint(download_model("Unbabel/wmt22-cometkiwi-da"))
    data = [{"src": s.src_text, "mt": s.vi_text} for p in projects for s in p.segments if s.vi_text]
    out = model.predict(data, batch_size=16, gpus=1 if __import__("torch").cuda.is_available() else 0)
    return {"comet_kiwi": round(float(out.system_score), 4), "n": len(data)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="+")
    ap.add_argument("--name", required=True)
    ap.add_argument("--ss", action="store_true")
    ap.add_argument("--comet", action="store_true")
    ap.add_argument("--manual", type=int, default=50, help="số câu xuất ra để chấm tay")
    ap.add_argument("--out", default="results/dubbing")
    args = ap.parse_args()

    projects = [Project.load(p) for p in args.projects]
    out_dir = Path(args.out) / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"name": args.name, "clips": len(projects), **duration_metrics(projects)}
    rtfs = [r["rtf"] for r in map(rtf_report, projects) if r["rtf"]]
    summary["pipeline_rtf"] = metrics.summarize(rtfs)
    if args.ss:
        summary.update(voice_consistency(projects))
    if args.comet:
        summary.update(comet_kiwi(projects))

    segs = [(p.clip_id, s) for p in projects for s in p.segments if s.vi_text]
    sample = random.Random(0).sample(segs, min(args.manual, len(segs)))
    with open(out_dir / "manual_review.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["clip", "id", "src", "vi", "dung_nghia_1_5", "tu_nhien_1_5", "ghi_chu"])
        w.writerows([c, s.id, s.src_text, s.vi_text, "", "", ""] for c, s in sample)

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
