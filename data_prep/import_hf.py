"""Xuất một bộ dữ liệu HuggingFace ra wav 24 kHz mono + manifest JSONL thô.

Tên cột khác nhau giữa các bộ, nên truyền qua tham số. Gợi ý (KIỂM TRA LẠI trên trang
dataset trước khi chạy, và ghi license từng bộ vào báo cáo):

  python -m data_prep.import_hf capleaf/viVoice --speaker-col channel --out data/raw/vivoice
  python -m data_prep.import_hf <phoaudiobook repo> --speaker-col speaker --out data/raw/phoaudiobook --max-hours 120
  python -m data_prep.import_hf <vimd repo> --speaker-col speakerID --out data/raw/vimd

--max-hours / --max-per-speaker dùng để cân bằng (vd. không để giọng đọc sách lấn át).
"""

from __future__ import annotations

import argparse
import io
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf

from vidub.audio import resample

from .common import read_jsonl, write_jsonl

TARGET_SR = 24000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--config", default=None)
    ap.add_argument("--split", default="train")
    ap.add_argument("--audio-col", default="audio")
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--speaker-col", required=True)
    ap.add_argument("--name", help="tên ngắn của bộ dữ liệu (mặc định lấy từ repo)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-hours", type=float, default=None)
    ap.add_argument("--max-per-speaker", type=float, default=None, help="giờ tối đa mỗi người nói")
    ap.add_argument("--streaming", action="store_true", help="không tải cả bộ về trước")
    ap.add_argument("--shuffle", action="store_true",
                    help="xáo thứ tự file + bộ đệm 1000 câu; cần khi bộ dữ liệu xếp theo người nói và có --max-per-speaker")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--existing", nargs="+", default=[],
                    help="raw.jsonl đã tải trước đó: bỏ câu trùng, tính giờ cũ vào --max-hours/--max-per-speaker")
    ap.add_argument("--id-prefix", help="tiền tố id (mặc định = --name); đặt khác khi tải thêm để không trùng id cũ")
    args = ap.parse_args()

    from datasets import Audio, load_dataset

    name = args.name or args.dataset.split("/")[-1].lower()
    out = Path(args.out)
    (out / "wavs").mkdir(parents=True, exist_ok=True)
    ds = load_dataset(args.dataset, args.config, split=args.split, streaming=args.streaming)
    # Tự giải mã bằng soundfile: datasets >= 4 cần torchcodec (gắn chặt phiên bản torch) nếu decode=True
    ds = ds.cast_column(args.audio_col, Audio(decode=False))
    if args.shuffle:
        ds = ds.shuffle(seed=args.seed, buffer_size=1000) if args.streaming else ds.shuffle(seed=args.seed)

    per_spk: Counter = Counter()
    total = 0.0
    seen: set[tuple] = set()
    for m in args.existing:
        for r in read_jsonl(m):
            seen.add((r["speaker"], r["text"], round(r["duration"], 1)))
            per_spk[r["speaker"]] += r["duration"]
            total += r["duration"]
    if seen:
        print(f"Đã có: {len(seen)} câu, {total / 3600:.1f} giờ", flush=True)
    prefix = args.id_prefix or name

    def rows():
        nonlocal total
        for i, ex in enumerate(ds):
            spk = f"{name}:{ex[args.speaker_col]}"
            if args.max_per_speaker and per_spk[spk] >= args.max_per_speaker * 3600:
                continue  # đã đủ giờ: bỏ trước khi giải mã
            a = ex[args.audio_col]
            wav, sr = sf.read(io.BytesIO(a["bytes"]) if a.get("bytes") else a["path"], dtype="float32")
            if wav.ndim > 1:
                wav = wav.mean(axis=-1)
            wav = resample(wav, sr, TARGET_SR)
            dur = len(wav) / TARGET_SR
            if args.max_per_speaker and per_spk[spk] + dur > args.max_per_speaker * 3600:
                continue
            if (spk, str(ex[args.text_col]).strip(), round(dur, 1)) in seen:
                continue
            uid = f"{prefix}_{i:08d}"
            path = out / "wavs" / f"{uid}.wav"
            sf.write(path, wav, TARGET_SR, subtype="PCM_16")
            per_spk[spk] += dur
            total += dur
            if i % 1000 == 0:
                print(f"{i} câu, {total / 3600:.1f} giờ, {len(per_spk)} người nói", flush=True)
            yield {"id": uid, "audio": str(path.resolve()), "text": str(ex[args.text_col]).strip(),
                   "speaker": spk, "dataset": name, "duration": round(dur, 3)}
            if args.max_hours and total >= args.max_hours * 3600:
                break

    n = write_jsonl(out / "raw.jsonl", rows())
    print(f"Xong: {n} câu, {total / 3600:.1f} giờ, {len(per_spk)} người nói -> {out / 'raw.jsonl'}")


if __name__ == "__main__":
    main()
