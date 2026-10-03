"""Đánh giá tầng TTS: sinh từng câu của bộ test rồi chấm CER/WER, SS, UTMOS, (ES), RTF.

Bộ test JSONL: {id, text, prompt_audio, [style_audio], [ref_audio]}
(do data_prep.split tạo: test_zeroshot.jsonl, test_crossling.jsonl, dev_tts.jsonl).

Mỗi hệ thống (mô hình chính, baseline) là một cấu hình `synthesize` khác nhau:

  python -m eval.eval_tts data/splits/test_zeroshot.jsonl --name indextts25_vi \
      --set synthesize.indextts.model_dir=checkpoints/indextts_vi
  python -m eval.eval_tts data/splits/test_zeroshot.jsonl --name dinhthuan \
      --set synthesize.indextts.model_dir=checkpoints/dinhthuan --set synthesize.indextts.cfg_path=...
  python -m eval.eval_tts ... --name f5_vi -c configs/f5_vi.yaml        # backend: command
  python -m eval.eval_tts --compare results/tts/*/summary.json            # bảng so sánh

Kết quả: results/tts/<name>/{wavs/, scores.csv, summary.json}
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from data_prep.common import read_jsonl
from vidub import audio
from vidub.backends.tts import get_tts
from vidub.config import load_config

from . import metrics


def generate(rows: list[dict], cfg: dict, out_dir: Path, gpu_name: str) -> list[dict]:
    tts = get_tts(cfg["synthesize"])
    results = []
    for i, r in enumerate(rows):
        out = out_dir / "wavs" / f"{r['id']}.wav"
        if not out.exists():
            t0 = time.perf_counter()
            tts.synthesize(r["text"], Path(r["prompt_audio"]), Path(r.get("style_audio") or r["prompt_audio"]), out)
            elapsed = time.perf_counter() - t0
        else:
            elapsed = None
        dur = audio.duration(out)
        results.append({**r, "wav": str(out), "gen_time": elapsed, "dur": round(dur, 3),
                        "rtf": round(elapsed / dur, 4) if elapsed and dur else None})
        if i % 20 == 0:
            print(f"sinh {i + 1}/{len(rows)}", flush=True)
    return results


def score(results: list[dict], asr: str, use_es: bool) -> None:
    hyps = metrics.transcribe([r["wav"] for r in results], asr)
    for r, hyp in zip(results, hyps):
        r["asr"] = hyp
        r["cer"] = round(metrics.cer(r["text"], hyp), 4)
        r["wer"] = round(metrics.wer(r["text"], hyp), 4)
        r["ss"] = round(metrics.speaker_similarity(r["prompt_audio"], r["wav"]), 4)
        r["utmos"] = round(metrics.utmos(r["wav"]), 3)
        if use_es and r.get("style_audio"):
            r["es"] = round(metrics.emotion_similarity(r["style_audio"], r["wav"]), 4)


def compare(paths: list[str]) -> None:
    rows = [json.loads(Path(p).read_text()) for p in paths]
    keys = ["cer", "wer", "ss", "utmos", "es", "rtf"]
    print("| Hệ thống | " + " | ".join(k.upper() for k in keys) + " |")
    print("| --- |" + " ---: |" * len(keys))
    for s in rows:
        cells = [f"{s[k]['mean']:.3f}" if s.get(k, {}).get("mean") is not None else "–" for k in keys]
        print(f"| {s['name']} | " + " | ".join(cells) + " |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("testset", nargs="?")
    ap.add_argument("--name")
    ap.add_argument("-c", "--config", action="append", default=[])
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--asr", default="parakeet", choices=["parakeet", "whisper"])
    ap.add_argument("--es", action="store_true", help="tính emotion similarity (cần style_audio)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default="results/tts")
    ap.add_argument("--compare", nargs="+")
    args = ap.parse_args()

    if args.compare:
        return compare(args.compare)
    if not (args.testset and args.name):
        ap.error("cần testset và --name")

    import torch

    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    cfg = load_config(args.config, args.set)
    rows = list(read_jsonl(args.testset))[: args.limit]
    out_dir = Path(args.out) / args.name
    results = generate(rows, cfg, out_dir, gpu)
    score(results, args.asr, args.es)

    fields = ["id", "text", "asr", "cer", "wer", "ss", "utmos", "es", "dur", "gen_time", "rtf", "wav"]
    with open(out_dir / "scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    summary = {"name": args.name, "testset": args.testset, "gpu": gpu, "config": cfg["synthesize"],
               **{k: metrics.summarize([r.get(k) for r in results]) for k in ("cer", "wer", "ss", "utmos", "es", "rtf")}}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: summary[k] for k in ("cer", "ss", "utmos", "rtf")}, indent=2))


if __name__ == "__main__":
    main()
