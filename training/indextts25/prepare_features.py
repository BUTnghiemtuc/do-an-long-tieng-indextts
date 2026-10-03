"""Trích trước đặc trưng cho mọi câu bằng các module ĐÓNG BĂNG của IndexTTS 2.5 (chạy trên GPU).

Mỗi câu -> {"text_ids", "codes", "spk", "emo"}, tính y hệt infer_v2_5.py:
  codes : semantic_codec.quantize(w2v-BERT 2.0 tầng 17, chuẩn hoá)   -> đáp án T2S (25 Hz)
  spk   : CAMPPlus(fbank 80 chiều, trừ trung bình)                   -> 192 chiều
  emo   : gpt.get_emovec(...) trên cùng đặc trưng w2v-BERT, cắt 15 s  -> vector cảm xúc
  text_ids : tokenizer("<|vi|> " + văn bản đã qua front-end)
Câu nào cũng có thể làm giọng mẫu cho câu khác, nên spk/emo tính cho mọi câu.

  python -m training.indextts25.prepare_features data/splits/train.jsonl data/features/train \
      --model-dir checkpoints/IndexTTS-2.5 --pairs-per-utt 2
Chạy lại được: bỏ qua các câu đã có trong feats_*.pt.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import torch

from data_prep.common import read_jsonl, write_jsonl
from data_prep.vi_normalize import tts_frontend

from .data import make_pairs
from .model import import_indextts

PROMPT_MAX_SEC = 15


def text_to_ids(tts, text: str, lang: str = "vi") -> list[int]:
    """Đúng đường xử lý văn bản của infer_v2_5 (lang ngoài zh/en/ja/es: không chuẩn hoá thêm)."""
    from indextts.infer_v2_5 import apply_pronunciation_annotations

    tp = tts.text_process
    text = tp.clean_pattern.sub(lambda x: tp.char_rep_map[x.group()], text)
    text = apply_pronunciation_annotations(text)
    text = re.sub(r"<\|([^|]+)\|>", lambda m: f"<|{m.group(1).upper()}|>", text)
    return tts.tokenizer.encode(f"<|{lang}|> " + text, allowed_special="all")


@torch.no_grad()
def extract(tts, wav_path: str) -> dict:
    import torchaudio

    audio, sr = torchaudio.load(wav_path)
    audio = audio.mean(0, keepdim=True)
    audio_16k = torchaudio.functional.resample(audio, sr, 16000)

    def w2v(a):
        inp = tts.extract_features(a, sampling_rate=16000, return_tensors="pt")
        return tts.get_emb(inp["input_features"].to(tts.device), inp["attention_mask"].to(tts.device))

    emb = w2v(audio_16k)
    codes = tts.get_scode(emb).reshape(-1)

    prompt = audio_16k[:, : PROMPT_MAX_SEC * 16000]                 # infer cắt giọng mẫu ở 15 s
    p_emb = emb if prompt.shape[1] == audio_16k.shape[1] else w2v(prompt)
    fbank = torchaudio.compliance.kaldi.fbank(prompt.to(tts.device), num_mel_bins=80, dither=0,
                                              sample_frequency=16000)
    fbank = fbank - fbank.mean(dim=0, keepdim=True)
    spk = tts.campplus_model(fbank.unsqueeze(0)).reshape(-1)
    # giống merge_emovec(...) khi không có giọng cảm xúc riêng (alpha = 1)
    emo = tts.gpt.get_emovec(p_emb, torch.tensor([p_emb.shape[-1]], device=tts.device)).reshape(-1)
    return {"codes": codes.to(torch.int16).cpu(), "spk": spk.half().cpu(), "emo": emo.half().cpu()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", help="JSONL: id, audio, text/text_norm, speaker, duration")
    ap.add_argument("out_dir")
    ap.add_argument("--model-dir", required=True, help="thư mục IndexTTS-2.5 (config.yaml, gpt.pth, ...)")
    ap.add_argument("--index-tts-repo")
    ap.add_argument("--lang", default="vi")
    ap.add_argument("--shard-size", type=int, default=2000)
    ap.add_argument("--pairs-per-utt", type=int, default=2)
    ap.add_argument("--split-name", default=None, help="tên file pairs_<split>.jsonl (mặc định = tên thư mục)")
    args = ap.parse_args()

    import_indextts(args.index_tts_repo)
    from indextts.infer_v2_5 import IndexTTS2

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = list(read_jsonl(args.manifest))
    done = set()
    for f in out.glob("feats_*.pt"):
        done |= set(torch.load(f, map_location="cpu"))
    todo = [r for r in rows if r["id"] not in done]
    print(f"{len(rows)} câu, đã có {len(done)}, cần trích {len(todo)}")

    if todo:
        tts = IndexTTS2(cfg_path=str(Path(args.model_dir) / "config.yaml"), model_dir=args.model_dir,
                        use_bf16=False, use_qwen_emo=False)
        shard_id = len(list(out.glob("feats_*.pt")))
        buf: dict[str, dict] = {}
        for i, r in enumerate(todo):
            try:
                feat = extract(tts, r["audio"])
            except Exception as e:  # file hỏng: ghi lại rồi bỏ qua
                print(f"  bỏ {r['id']}: {e}")
                continue
            feat["text_ids"] = torch.tensor(text_to_ids(tts, tts_frontend(r.get("text_norm") or r["text"]), args.lang),
                                            dtype=torch.int32)
            buf[r["id"]] = feat
            if len(buf) >= args.shard_size or i == len(todo) - 1:
                torch.save(buf, out / f"feats_{shard_id:05d}.pt")
                print(f"  {i + 1}/{len(todo)} -> feats_{shard_id:05d}.pt", flush=True)
                shard_id, buf = shard_id + 1, {}

    split = args.split_name or out.name
    pairs = make_pairs(rows, args.pairs_per_utt)
    write_jsonl(out / f"pairs_{split}.jsonl", pairs)
    (out / "meta.json").write_text(json.dumps({
        "manifest": args.manifest, "model_dir": args.model_dir, "lang": args.lang,
        "utterances": len(rows), "pairs": len(pairs), "pairs_per_utt": args.pairs_per_utt,
    }, indent=2, ensure_ascii=False))
    print(f"{len(pairs)} cặp -> {out / f'pairs_{split}.jsonl'}")


if __name__ == "__main__":
    main()
