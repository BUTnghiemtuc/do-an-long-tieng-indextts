"""Finetune GPT của IndexTTS 2.5 cho tiếng Việt bằng LoRA.

  python -m training.indextts25.train -c training/indextts25/config_vi.yaml
  python -m training.indextts25.train -c ... --set train.max_steps=300 --set data.train_limit=500   # overfit thử

Checkpoint chỉ chứa phần được train (LoRA + embedding + head + hàng ngôn ngữ, ~0,8 GB với
cấu hình mặc định); dùng export.py để gộp thành gpt.pth nạp thẳng vào IndexTTS.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from vidub.config import deep_merge, parse_override

from .data import BucketBatchSampler, PairDataset, collate, load_features, load_pairs
from .model import (TrainSetup, forward_train, import_indextts, lang_id, load_gpt_from_config,
                    prepare_for_training, trainable_state_dict)

import yaml


def load_cfg(paths: list[str], overrides: list[str]) -> dict:
    cfg: dict = {}
    for p in paths:
        cfg = deep_merge(cfg, yaml.safe_load(Path(p).read_text(encoding="utf-8")))
    for o in overrides:
        cfg = deep_merge(cfg, parse_override(o))
    return cfg


def lr_lambda(warmup: int, total: int, min_ratio: float):
    def f(step: int) -> float:
        if step < warmup:
            return (step + 1) / warmup
        progress = min(1.0, (step - warmup) / max(1, total - warmup))
        return min_ratio + (1 - min_ratio) * 0.5 * (1 + math.cos(math.pi * progress))
    return f


def build_optimizer(groups: dict, t: dict) -> torch.optim.Optimizer:
    lr, wd = t["learning_rate"], t["weight_decay"]
    param_groups = [
        {"params": groups["lora"], "lr": lr, "weight_decay": wd, "name": "lora"},
        {"params": groups["head"], "lr": lr, "weight_decay": wd, "name": "head"},
        # Embedding: không weight decay, để các hàng zh/en không có gradient không bị co lại.
        {"params": groups["embed"], "lr": lr, "weight_decay": 0.0, "name": "embed"},
        {"params": groups["lang"], "lr": lr * t.get("language_learning_rate_multiplier", 1.0),
         "weight_decay": 0.0, "name": "lang"},
    ]
    return torch.optim.AdamW([g for g in param_groups if g["params"]], betas=(0.9, 0.98), eps=1e-8)


@torch.no_grad()
def evaluate(model, loader, lang: int, t: dict, device, autocast) -> dict:
    model.eval()
    sums = {"loss": 0.0, "text_loss": 0.0, "mel_loss": 0.0, "mel_acc": 0.0}
    n_tok = 0
    for batch in loader:
        with autocast():
            out = forward_train(model, batch.to(device), lang, t["text_loss_weight"], t["mel_loss_weight"])
        k = int(out["mel_tokens"])
        for key in sums:
            sums[key] += float(out[key]) * k
        n_tok += k
    model.train()
    return {k: v / max(1, n_tok) for k, v in sums.items()}


def save_checkpoint(path: Path, model, optimizer, scheduler, step: int, epoch: int, cfg: dict, metrics: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "trainable": trainable_state_dict(model),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "step": step, "epoch": epoch, "config": cfg, "metrics": metrics,
        "rng": {"torch": torch.get_rng_state(), "python": random.getstate(), "numpy": np.random.get_state()},
    }, path)


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", action="append", required=True)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--resume", help="checkpoint step_*.pt để chạy tiếp")
    args = ap.parse_args(argv)
    cfg = load_cfg(args.config, args.set)
    t, d, run = cfg["train"], cfg["data"], cfg["run"]

    seed = t.get("seed", 1234)
    random.seed(seed), np.random.seed(seed), torch.manual_seed(seed)
    import_indextts(cfg.get("index_tts_repo"))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_bf16 = t.get("precision") == "bf16" and device.type == "cuda"

    def autocast():
        return torch.autocast(device.type, dtype=torch.bfloat16, enabled=use_bf16)

    # ---- model
    m = cfg["model"]
    if "gpt_kwargs" in m:                       # dùng cho test với model tí hon
        from .model import build_gpt
        model = build_gpt(m["gpt_kwargs"], m.get("checkpoint"))
    else:
        model = load_gpt_from_config(m["config"], m["checkpoint"])
    setup = TrainSetup(**{k: v for k, v in t.items() if k in TrainSetup.__dataclass_fields__})
    groups = prepare_for_training(model, setup)
    model.to(device).train()
    lang = lang_id(setup.language)
    n_train = sum(p.numel() for g in groups.values() for p in g)
    n_all = sum(p.numel() for p in model.parameters())
    print(f"Tham số train: {n_train / 1e6:.1f}M / {n_all / 1e6:.1f}M")

    # ---- data
    feats = load_features(d["features"])
    if d.get("dev_features") and d["dev_features"] != d["features"]:
        feats.update(load_features(d["dev_features"]))
    train_pairs = load_pairs(d["train_pairs"])[: d.get("train_limit")]
    ds = PairDataset(feats, train_pairs, model.max_text_tokens, model.max_mel_tokens)
    sampler = BucketBatchSampler(ds, t["batch_size"], seed)
    loader = DataLoader(ds, batch_sampler=sampler, collate_fn=collate, num_workers=d.get("num_workers", 0))
    dev_loader = None
    if d.get("dev_pairs"):
        dev_ds = PairDataset(feats, load_pairs(d["dev_pairs"])[: d.get("dev_limit")],
                             model.max_text_tokens, model.max_mel_tokens)
        dev_loader = DataLoader(dev_ds, batch_size=t["batch_size"], collate_fn=collate)
    print(f"Cặp train: {len(ds)} (bỏ {ds.dropped} vì thiếu/dài quá)")

    accum = t["gradient_accumulation"]
    steps_per_epoch = math.ceil(len(sampler) / accum)
    total = t.get("max_steps") or t["epochs"] * steps_per_epoch
    optimizer = build_optimizer(groups, t)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lr_lambda(t["warmup_steps"], total, t.get("minimum_learning_rate_ratio", 0.0)))

    out_dir = Path(run["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    step, epoch = 0, 0
    if args.resume:
        ck = torch.load(args.resume, map_location="cpu", weights_only=False)
        missing = model.load_state_dict(ck["trainable"], strict=False)
        assert not missing.unexpected_keys, missing.unexpected_keys
        optimizer.load_state_dict(ck["optimizer"])
        scheduler.load_state_dict(ck["scheduler"])
        step, epoch = ck["step"], ck["epoch"]
        torch.set_rng_state(ck["rng"]["torch"]), random.setstate(ck["rng"]["python"]), np.random.set_state(ck["rng"]["numpy"])
        print(f"Chạy tiếp từ bước {step}")

    writer = None
    if run.get("tensorboard", True):
        try:
            from torch.utils.tensorboard import SummaryWriter
            writer = SummaryWriter(out_dir / "tb")
        except ImportError:
            pass
    log_path = out_dir / "log.jsonl"

    params = [p for g in groups.values() for p in g]
    best = float("inf")
    history: list[dict] = []
    t0 = time.time()
    micro = step * accum
    # Chạy tiếp: bỏ qua các micro-batch của epoch hiện tại đã train (thứ tự batch cố định theo seed + epoch).
    resume_skip = max(0, micro - epoch * len(sampler)) if args.resume else 0
    acc = {"loss": 0.0, "text_loss": 0.0, "mel_loss": 0.0, "mel_acc": 0.0}
    while step < total:
        sampler.set_epoch(epoch)
        for batch in loader:
            if resume_skip > 0:
                resume_skip -= 1
                continue
            with autocast():
                out = forward_train(model, batch.to(device), lang, t["text_loss_weight"], t["mel_loss_weight"],
                                    t.get("speaker_noise_std", 0.0), t.get("emotion_dropout", 0.0))
            (out["loss"] / accum).backward()
            for k in acc:
                acc[k] += float(out[k].detach()) / accum
            micro += 1
            if micro % accum:
                continue

            grad_norm = torch.nn.utils.clip_grad_norm_(params, t["gradient_clip"])
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            step += 1

            if step % run.get("log_every", 50) == 0 or step == 1:
                rec = {"step": step, "epoch": epoch, "lr": scheduler.get_last_lr()[0], "grad_norm": float(grad_norm),
                       **{k: round(v, 4) for k, v in acc.items()}, "elapsed_s": round(time.time() - t0, 1)}
                print(json.dumps(rec), flush=True)
                history.append(rec)
                with open(log_path, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                if writer:
                    for k, v in rec.items():
                        if k not in ("step", "epoch"):
                            writer.add_scalar(f"train/{k}", v, step)
            acc = {k: 0.0 for k in acc}

            is_eval = step % run.get("eval_every", 1000) == 0 or step == total
            if is_eval:
                metrics = evaluate(model, dev_loader, lang, t, device, autocast) if dev_loader else {}
                if metrics:
                    print(json.dumps({"step": step, **{f"dev_{k}": round(v, 4) for k, v in metrics.items()}}), flush=True)
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"step": step, "dev": metrics}) + "\n")
                    if writer:
                        for k, v in metrics.items():
                            writer.add_scalar(f"dev/{k}", v, step)
                save_checkpoint(out_dir / f"step_{step:06d}.pt", model, optimizer, scheduler, step, epoch, cfg, metrics)
                if metrics and metrics["loss"] < best:
                    best = metrics["loss"]
                    (out_dir / "best.txt").write_text(f"step_{step:06d}.pt\n{json.dumps(metrics)}\n")
                keep = run.get("keep_checkpoints")
                if keep:
                    for old in sorted(out_dir.glob("step_*.pt"))[:-keep]:
                        old.unlink()
            if step >= total:
                break
        else:
            epoch += 1

    if writer:
        writer.close()
    return {"steps": step, "history": history, "output_dir": str(out_dir)}


if __name__ == "__main__":
    main()
