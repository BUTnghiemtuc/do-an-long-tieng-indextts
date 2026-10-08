"""Chọn lại câu mẫu (prompt) cho bộ test zero-shot sao cho cùng giọng thật với câu đích.

split.py lấy câu mẫu theo nhãn người nói. Với viVoice, nhãn là kênh YouTube, nên câu mẫu có thể
là một người khác trong cùng kênh; khi đó SS đo sai. Script tính vector giọng CAMPPlus (giống hệt
prepare_features.py) cho câu đích và các câu ứng viên 3–10 s cùng nhãn, rồi:
  - giữ câu mẫu cũ nếu cosine với câu đích >= --min-spk-sim;
  - nếu không, chọn ngẫu nhiên (seed cố định) một ứng viên đạt ngưỡng;
  - không có ứng viên nào đạt thì bỏ câu test đó.
Ghi thêm trường prompt_target_sim. Chạy được trên CPU.

  python -m data_prep.test_prompts data/splits/test_zeroshot.jsonl data/clean/*.jsonl \\
      --out data/splits/test_zeroshot.jsonl
"""

from __future__ import annotations

import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path

import torch

from .common import read_jsonl, write_jsonl

PROMPT_MAX_SEC = 15


def load_campplus(model_dir: str, index_tts_repo: str | None = None):
    from training.indextts25.model import import_indextts

    import_indextts(index_tts_repo)
    from indextts.s2mel.modules.campplus.DTDNN import CAMPPlus

    m = CAMPPlus(feat_dim=80, embedding_size=192)
    m.load_state_dict(torch.load(Path(model_dir) / "hf_cache" / "campplus_cn_common.bin", map_location="cpu"))
    return m.eval()


@torch.no_grad()
def spk_embedding(model, path: str) -> torch.Tensor:
    """Như prepare_features.extract: 16 kHz, cắt 15 s, fbank 80 chiều trừ trung bình."""
    import torchaudio

    audio, sr = torchaudio.load(path)
    audio = torchaudio.functional.resample(audio.mean(0, keepdim=True), sr, 16000)[:, : PROMPT_MAX_SEC * 16000]
    fbank = torchaudio.compliance.kaldi.fbank(audio, num_mel_bins=80, dither=0, sample_frequency=16000)
    fbank = fbank - fbank.mean(dim=0, keepdim=True)
    return torch.nn.functional.normalize(model(fbank.unsqueeze(0)).reshape(-1), dim=0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("testset")
    ap.add_argument("manifests", nargs="+", help="manifest đã lọc (lấy câu ứng viên cùng nhãn người nói)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model-dir", default="checkpoints/IndexTTS-2.5")
    ap.add_argument("--min-spk-sim", type=float, default=0.5)
    ap.add_argument("--max-cands", type=int, default=60, help="số câu ứng viên tối đa mỗi người nói")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    rng = random.Random(args.seed)
    rows = list(read_jsonl(args.testset))
    speakers = {r["speaker"] for r in rows}
    cands: dict[str, list[dict]] = defaultdict(list)
    for m in args.manifests:
        for r in read_jsonl(m):
            if r["speaker"] in speakers and 3.0 <= r["duration"] <= 10.0:
                cands[r["speaker"]].append(r)
    for s in cands:
        rng.shuffle(cands[s])
        cands[s] = cands[s][: args.max_cands]

    model = load_campplus(args.model_dir)
    emb: dict[str, torch.Tensor] = {}

    def e(path: str) -> torch.Tensor:
        if path not in emb:
            emb[path] = spk_embedding(model, path)
        return emb[path]

    out, kept, replaced = [], 0, 0
    for i, r in enumerate(rows):
        t = e(r["ref_audio"])
        sim = float(t @ e(r["prompt_audio"]))
        if sim < args.min_spk_sim:
            ok = [c for c in cands[r["speaker"]] if c["audio"] != r["ref_audio"] and float(t @ e(c["audio"])) >= args.min_spk_sim]
            if not ok:
                continue
            c = rng.choice(ok)
            r = {**r, "prompt_audio": c["audio"], "prompt_text": c.get("text_norm", c["text"])}
            sim = float(t @ e(c["audio"]))
            replaced += 1
        else:
            kept += 1
        out.append({**r, "prompt_target_sim": round(sim, 4)})
        if i % 20 == 0:
            print(f"{i}/{len(rows)}", flush=True)

    if Path(args.out).resolve() == Path(args.testset).resolve():
        shutil.copy(args.testset, Path(args.testset).with_suffix(".orig.jsonl"))
    write_jsonl(args.out, out)
    by_ds = defaultdict(lambda: [0, 0])
    for r in rows:
        by_ds[r["speaker"].split(":")[0]][1] += 1
    for r in out:
        by_ds[r["speaker"].split(":")[0]][0] += 1
    print(f"giữ câu mẫu cũ: {kept}, thay: {replaced}, bỏ: {len(rows) - len(out)}")
    for k, (a, b) in sorted(by_ds.items()):
        print(f"  {k}: còn {a}/{b} câu")
    print(f"{len(out)} câu, {len({r['speaker'] for r in out})} người nói -> {args.out}")


if __name__ == "__main__":
    main()
