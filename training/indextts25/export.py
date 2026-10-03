"""Gộp LoRA vào GPT và xuất một thư mục model IndexTTS 2.5 dùng được ngay.

  python -m training.indextts25.export runs/vi_run2/step_016000.pt \
      --base-dir checkpoints/IndexTTS-2.5 --out checkpoints/IndexTTS-2.5-vi

Thư mục xuất ra: gpt.pth mới (đã gộp) + liên kết tới mọi file khác của model gốc.
Dùng trong pipeline: synthesize.indextts.entry=indextts.infer_v2_5:IndexTTS2,
model_dir=checkpoints/IndexTTS-2.5-vi, lang=vi.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import torch

from .lora import merge_lora
from .model import TrainSetup, import_indextts, load_gpt_from_config, prepare_for_training


def export(ckpt_path: str, base_dir: str, out_dir: str, dtype: str = "keep", index_tts_repo: str | None = None) -> Path:
    import_indextts(index_tts_repo)
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    t = ck["config"]["train"]
    base = Path(base_dir)
    base_gpt = base / "gpt.pth"

    model = load_gpt_from_config(str(base / "config.yaml"), str(base_gpt))
    setup = TrainSetup(**{k: v for k, v in t.items() if k in TrainSetup.__dataclass_fields__})
    setup.language_initialization = None          # hàng ngôn ngữ lấy từ checkpoint, không khởi tạo lại
    setup.gradient_checkpointing = False
    prepare_for_training(model, setup)
    result = model.load_state_dict(ck["trainable"], strict=False)
    assert not result.unexpected_keys, result.unexpected_keys
    n = merge_lora(model)

    state = model.state_dict()
    if dtype != "keep":
        state = {k: v.to(getattr(torch, dtype)) if v.is_floating_point() else v for k, v in state.items()}
    else:
        raw = torch.load(base_gpt, map_location="cpu", mmap=True)   # chỉ để đọc dtype, không nạp 3 GB vào RAM
        raw = raw.get("model", raw)
        ref = next(v for v in raw.values() if torch.is_tensor(v) and v.is_floating_point())
        state = {k: v.to(ref.dtype) if v.is_floating_point() else v for k, v in state.items()}

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(state, out / "gpt.pth")
    for item in base.iterdir():
        target = out / item.name
        if item.name != "gpt.pth" and not target.exists():
            os.symlink(item.resolve(), target)
    (out / "finetune_info.json").write_text(json.dumps({
        "base_model": str(base), "checkpoint": ckpt_path, "step": ck["step"], "metrics": ck.get("metrics"),
        "merged_lora_layers": n, "language": t.get("language", "vi"),
    }, indent=2, ensure_ascii=False))
    print(f"Đã gộp {n} lớp LoRA -> {out / 'gpt.pth'}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoint")
    ap.add_argument("--base-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dtype", default="keep", choices=["keep", "float32", "bfloat16", "float16"])
    ap.add_argument("--index-tts-repo")
    args = ap.parse_args()
    export(args.checkpoint, args.base_dir, args.out, args.dtype, args.index_tts_repo)


if __name__ == "__main__":
    main()
