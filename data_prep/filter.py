"""Lọc và chuẩn hoá manifest, theo pipeline dữ liệu của paper IndexTTS 2.5 (mục 2).

Các bước (chọn bằng --stages, mỗi bước ghi thêm trường vào manifest, chạy lại được):
  duration   bỏ câu < 1 s hoặc > 25 s
  normalize  chuẩn hoá văn bản (số, ngày, đơn vị...) -> trường text_norm
  asr        nhận dạng lại, tính CER với transcript gốc -> trường cer   (GPU)
  quality    chấm UTMOS -> trường utmos                                 (GPU)
  select     giữ câu CER <= --max-cer, bỏ --drop-quality phần đáy UTMOS,
             bỏ người nói có < --min-utts câu

  python -m data_prep.filter data/raw/vivoice/raw.jsonl data/clean/vivoice.jsonl \
      --stages duration normalize asr quality select
"""

from __future__ import annotations

import argparse
from collections import Counter

import numpy as np

from .common import read_jsonl, write_jsonl
from .vi_normalize import normalize

ALL_STAGES = ["duration", "normalize", "asr", "quality", "select"]


def cer(ref: str, hyp: str) -> float:
    import jiwer

    norm = lambda s: " ".join(normalize(s).lower().replace(",", " ").replace(".", " ").split())  # noqa: E731
    r = norm(ref)
    return float(jiwer.cer(r, norm(hyp))) if r else 1.0


# ------------------------------------------------------------------- ASR
class ParakeetASR:
    def __init__(self, model: str = "nvidia/parakeet-ctc-0.6b-vi"):
        import nemo.collections.asr as nemo_asr

        self.model = nemo_asr.models.ASRModel.from_pretrained(model).eval()

    def __call__(self, paths: list[str]) -> list[str]:
        out = self.model.transcribe(paths, batch_size=len(paths), verbose=False)
        if isinstance(out, tuple):
            out = out[0]
        return [o if isinstance(o, str) else o.text for o in out]


class WhisperASR:
    def __init__(self, model: str = "large-v3"):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model, device="cuda", compute_type="float16")

    def __call__(self, paths: list[str]) -> list[str]:
        return [" ".join(s.text for s in self.model.transcribe(p, language="vi")[0]).strip() for p in paths]


def stage_asr(rows: list[dict], backend: str, batch: int) -> None:
    asr = ParakeetASR() if backend == "parakeet" else WhisperASR()
    todo = [r for r in rows if "cer" not in r]
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        for r, hyp in zip(chunk, asr([r["audio"] for r in chunk])):
            r["asr"] = hyp
            r["cer"] = round(cer(r["text"], hyp), 4)
        if i // batch % 20 == 0:
            print(f"ASR {i + len(chunk)}/{len(todo)}", flush=True)


# ------------------------------------------------------------------- UTMOS
def stage_quality(rows: list[dict]) -> None:
    import torch

    from vidub.audio import load

    predictor = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    predictor = predictor.to(device).eval()
    todo = [r for r in rows if "utmos" not in r]
    with torch.inference_mode():
        for i, r in enumerate(todo):
            wav, sr = load(r["audio"], sr=16000)
            r["utmos"] = round(float(predictor(torch.from_numpy(wav)[None].to(device), sr)), 3)
            if i % 2000 == 0:
                print(f"UTMOS {i}/{len(todo)}", flush=True)


# ------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--stages", nargs="+", default=ALL_STAGES, choices=ALL_STAGES)
    ap.add_argument("--min-dur", type=float, default=1.0)
    ap.add_argument("--max-dur", type=float, default=25.0)
    ap.add_argument("--asr", default="parakeet", choices=["parakeet", "whisper"])
    ap.add_argument("--asr-batch", type=int, default=32)
    ap.add_argument("--max-cer", type=float, default=0.10)
    ap.add_argument("--drop-quality", type=float, default=0.12, help="bỏ phần đáy theo UTMOS (0.10–0.15)")
    ap.add_argument("--min-utts", type=int, default=2)
    args = ap.parse_args()

    rows = list(read_jsonl(args.inp))
    print(f"Đầu vào: {len(rows)} câu")

    if "duration" in args.stages:
        rows = [r for r in rows if args.min_dur <= r["duration"] <= args.max_dur]
        print(f"duration: còn {len(rows)}")
    if "normalize" in args.stages:
        for r in rows:
            r["text_norm"] = normalize(r["text"])
        rows = [r for r in rows if r["text_norm"]]
    if "asr" in args.stages:
        stage_asr(rows, args.asr, args.asr_batch)
        write_jsonl(args.out, rows)   # lưu giữa chừng: ASR là bước lâu nhất
    if "quality" in args.stages:
        stage_quality(rows)
    if "select" in args.stages:
        if any("cer" in r for r in rows):
            rows = [r for r in rows if r.get("cer", 0) <= args.max_cer]
            print(f"CER <= {args.max_cer}: còn {len(rows)}")
        scores = [r["utmos"] for r in rows if "utmos" in r]
        if scores:
            cut = float(np.quantile(scores, args.drop_quality))
            rows = [r for r in rows if r.get("utmos", cut) >= cut]
            print(f"UTMOS >= {cut:.2f}: còn {len(rows)}")
        counts = Counter(r["speaker"] for r in rows)
        rows = [r for r in rows if counts[r["speaker"]] >= args.min_utts]
        print(f">= {args.min_utts} câu/người nói: còn {len(rows)}")

    write_jsonl(args.out, rows)
    print(f"Ghi {len(rows)} câu -> {args.out}")


if __name__ == "__main__":
    main()
