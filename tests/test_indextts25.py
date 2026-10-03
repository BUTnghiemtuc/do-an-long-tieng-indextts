"""Test script finetune IndexTTS 2.5 trên CPU với GPT tí hon (2 lớp, 64 chiều).

Cần mã IndexTTS ở third_party/index-tts (hoặc INDEX_TTS_REPO) và torch, transformers==4.52.1.
"""

import json
import random
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
F = torch.nn.functional

from training.indextts25 import model as M  # noqa: E402

try:
    M.import_indextts()
except FileNotFoundError:
    pytest.skip("không có mã IndexTTS (third_party/index-tts)", allow_module_level=True)

from training.indextts25.lora import LoRAConv1D, merge_lora  # noqa: E402

CM = dict(output_size=64, linear_units=128, attention_heads=2, num_blocks=1, input_layer="conv2d2", perceiver_mult=2)
GPT_KW = dict(layers=2, model_dim=64, heads=2, max_text_tokens=60, max_mel_tokens=80, number_text_tokens=500,
              number_mel_codes=8194, start_mel_token=8192, stop_mel_token=8193, start_text_token=0,
              stop_text_token=1, condition_type="conformer_perceiver", condition_module=CM, emo_condition_module=CM)


def tiny(seed=0):
    torch.manual_seed(seed)
    m = M.build_gpt(GPT_KW)
    for p in (m.lang_embedding.weight, m.text_pos_embedding.emb.weight, m.mel_pos_embedding.emb.weight):
        torch.nn.init.normal_(p, std=0.5)   # để test nhạy với sai vị trí / sai ngôn ngữ
    return m


def randomize_lora(model):
    for mod in model.modules():
        if isinstance(mod, LoRAConv1D):
            torch.nn.init.normal_(mod.lora_B, std=0.05)


def sample(n_text=7, n_code=12):
    return (torch.randint(2, 500, (n_text,)), torch.randint(0, 8192, (n_code,)), torch.randn(1, 192), torch.randn(1, 64))


def train_mel_logits(model, txt, codes, spk, emo, lang):
    conds = M.conditioning(model, spk, emo)
    t = F.pad(F.pad(txt, (1, 0), value=0), (0, 1), value=1)
    mm = F.pad(F.pad(codes, (1, 0), value=8192), (0, 1), value=8193)
    seq = torch.cat([conds[0],
                     model.text_embedding(t) + model.text_pos_embedding.emb(torch.arange(len(t)))
                     + model.lang_embedding(torch.tensor(lang)),
                     model.mel_embedding(mm) + model.mel_pos_embedding.emb(torch.arange(len(mm)))])[None]
    h = model.final_norm(model.gpt(inputs_embeds=seq, return_dict=True).last_hidden_state)
    return model.mel_head(h[0, 3 + len(t):3 + len(t) + len(mm) - 1])


def inference_mel_logits(model, txt, codes, spk, emo, lang):
    """Đường suy luận chính thức: prepare_gpt_inputs + GPT2InferenceModel (như inference_speech)."""
    conds = M.conditioning(model, spk, emo)
    model.post_init_gpt2_config(use_deepspeed=False, kv_cache=False, half=False)
    input_ids, embeds, attn = model.prepare_gpt_inputs(conds, F.pad(txt[None], (0, 1), value=1), torch.tensor([lang]))
    model.inference_model.store_mel_emb(embeds)
    out = model.inference_model(input_ids=torch.cat([input_ids, codes[None]], 1),
                                attention_mask=F.pad(attn, (0, len(codes)), value=1), return_dict=True)
    return out.logits[0, embeds.shape[1]:]


def test_training_layout_matches_inference():
    model = tiny().eval()
    M.prepare_for_training(model, M.TrainSetup(lora_rank=4, lora_alpha=8, gradient_checkpointing=False))
    randomize_lora(model)
    model.eval()
    vi = M.lang_id("vi")
    txt, codes, spk, emo = sample()
    with torch.no_grad():
        a = train_mel_logits(model, txt, codes, spk, emo, vi)
        b = inference_mel_logits(model, txt, codes, spk, emo, vi)
        out = M.forward_train(model, M.Batch([txt], [codes], spk, emo), vi)
    assert a.shape == b.shape == (len(codes) + 1, 8194)
    assert torch.allclose(a, b, atol=1e-4)
    # loss của forward_train khớp CE tính từ logits của đường suy luận
    tgt = torch.cat([codes, torch.tensor([8193])])
    assert torch.isclose(out["mel_loss"], F.cross_entropy(b, tgt), atol=1e-4)


def test_batch_padding_does_not_change_loss():
    model = tiny().eval()
    vi = M.lang_id("vi")
    s1, s2 = sample(5, 9), sample(11, 20)
    with torch.no_grad():
        alone = M.forward_train(model, M.Batch([s1[0]], [s1[1]], s1[2], s1[3]), vi)
        both = M.forward_train(model, M.Batch([s1[0], s2[0]], [s1[1], s2[1]], torch.cat([s1[2], s2[2]]),
                                              torch.cat([s1[3], s2[3]])), vi)
        other = M.forward_train(model, M.Batch([s2[0]], [s2[1]], s2[2], s2[3]), vi)
    n1, n2 = len(s1[1]) + 1, len(s2[1]) + 1
    expected = (alone["mel_loss"] * n1 + other["mel_loss"] * n2) / (n1 + n2)
    assert torch.isclose(both["mel_loss"], expected, atol=1e-4)


def test_lora_merge_is_exact_and_freezing():
    model = tiny()
    groups = M.prepare_for_training(model, M.TrainSetup(lora_rank=4, lora_alpha=8, gradient_checkpointing=False))
    randomize_lora(model)
    model.eval()
    # chỉ LoRA, embedding văn bản, 2 head và bảng ngôn ngữ được train
    names = {n for n, p in model.named_parameters() if p.requires_grad}
    assert all("lora_" in n or n.split(".")[0] in ("text_embedding", "text_head", "mel_head", "lang_embedding")
               for n in names)
    assert not any(n.startswith(("spk_emb_proj", "emo_", "emovec", "mel_embedding")) for n in names)
    assert len(groups["lora"]) == 2 * 4 * 2   # A, B x 4 lớp con x 2 khối
    vi = M.lang_id("vi")
    txt, codes, spk, emo = sample()
    with torch.no_grad():
        before = train_mel_logits(model, txt, codes, spk, emo, vi)
        assert merge_lora(model) == 8
        after = train_mel_logits(model, txt, codes, spk, emo, vi)
    assert torch.allclose(before, after, atol=1e-4)
    assert not any(isinstance(m, LoRAConv1D) for m in model.modules())


def test_language_row_initialised_from_en():
    model = tiny()
    en = model.lang_embedding.weight[M.lang_id("en")].clone()
    M.prepare_for_training(model, M.TrainSetup(lora_rank=4, lora_alpha=8, gradient_checkpointing=False))
    assert torch.equal(model.lang_embedding.weight[M.lang_id("vi")], en)


# ---------------------------------------------------------------------- train end-to-end
def make_fake_features(tmp: Path, n_utts=8, n_spk=2):
    """Codes là hàm tất định của văn bản, nên model tí hon học thuộc được."""
    rng = random.Random(0)
    feats, manifest = {}, []
    for i in range(n_utts):
        L = rng.randint(4, 8)
        txt = torch.tensor([rng.randint(2, 499) for _ in range(L)], dtype=torch.int32)
        codes = torch.tensor([(int(x) * 37) % 8192 for x in txt for _ in range(2)], dtype=torch.int16)
        uid = f"u{i}"
        feats[uid] = {"text_ids": txt, "codes": codes, "spk": torch.randn(192).half(), "emo": torch.randn(64).half()}
        manifest.append({"id": uid, "speaker": f"s{i % n_spk}", "duration": 5.0})
    d = tmp / "feats"
    d.mkdir()
    torch.save(feats, d / "feats_00000.pt")
    from training.indextts25.data import make_pairs
    pairs = make_pairs(manifest, pairs_per_utt=2)
    (d / "pairs_train.jsonl").write_text("\n".join(json.dumps(p) for p in pairs))
    return d


def write_base_model(tmp: Path) -> Path:
    base = tmp / "base"
    base.mkdir()
    import yaml
    (base / "config.yaml").write_text(yaml.safe_dump({"gpt": GPT_KW}))
    torch.save(tiny(seed=3).state_dict(), base / "gpt.pth")
    (base / "s2mel.pth").write_bytes(b"x")       # file khác của model gốc -> export tạo symlink
    return base


def test_overfit_resume_and_export(tmp_path):
    from training.indextts25 import export as E
    from training.indextts25 import train as T

    feats = make_fake_features(tmp_path)
    base = write_base_model(tmp_path)
    cfg = {
        "model": {"config": str(base / "config.yaml"), "checkpoint": str(base / "gpt.pth")},
        "data": {"features": str(feats), "train_pairs": str(feats / "pairs_train.jsonl"),
                 "dev_pairs": str(feats / "pairs_train.jsonl")},
        "train": {"lora_rank": 16, "lora_alpha": 32.0, "language": "vi", "language_initialization": "en",
                  "language_learning_rate_multiplier": 5.0, "batch_size": 4, "gradient_accumulation": 2,
                  "epochs": 1, "max_steps": 300, "learning_rate": 1e-2, "weight_decay": 0.01, "warmup_steps": 10,
                  "minimum_learning_rate_ratio": 0.1, "gradient_clip": 1.0, "precision": "bf16", "seed": 1,
                  "text_loss_weight": 0.2, "mel_loss_weight": 1.0, "speaker_noise_std": 0.01,
                  "emotion_dropout": 0.0, "gradient_checkpointing": True},
        "run": {"output_dir": str(tmp_path / "run"), "log_every": 10, "eval_every": 150, "tensorboard": False},
    }
    cfg_path = tmp_path / "cfg.yaml"
    import yaml
    cfg_path.write_text(yaml.safe_dump(cfg))

    res = T.main(["-c", str(cfg_path)])
    hist = res["history"]
    assert res["steps"] == 300
    assert hist[-1]["mel_loss"] < 0.1 * hist[0]["mel_loss"], (hist[0], hist[-1])
    dev = [json.loads(l) for l in (tmp_path / "run" / "log.jsonl").read_text().splitlines() if '"dev"' in l]
    assert dev and dev[-1]["dev"]["mel_acc"] > 0.9

    # Chạy tiếp từ bước 150 tới 300: kết quả phải trùng lần chạy liền một mạch
    ck = tmp_path / "run" / "step_000150.pt"
    assert ck.exists()
    res2 = T.main(["-c", str(cfg_path), "--resume", str(ck), "--set", f"run.output_dir={tmp_path / 'run2'}"])
    assert res2["steps"] == 300
    assert abs(res2["history"][-1]["mel_loss"] - hist[-1]["mel_loss"]) < 0.05

    # Export: gộp LoRA, nạp lại bằng load_checkpoint của IndexTTS -> cùng kết quả với model đang train
    out = E.export(str(tmp_path / "run" / "step_000300.pt"), str(base), str(tmp_path / "exported"))
    assert (out / "s2mel.pth").is_symlink() and (out / "gpt.pth").exists()
    fresh = M.load_gpt_from_config(str(out / "config.yaml"), str(out / "gpt.pth")).eval()

    trained = M.load_gpt_from_config(str(base / "config.yaml"), str(base / "gpt.pth"))
    setup = M.TrainSetup(lora_rank=16, lora_alpha=32.0, language_initialization=None, gradient_checkpointing=False)
    M.prepare_for_training(trained, setup)
    trained.load_state_dict(torch.load(tmp_path / "run" / "step_000300.pt", weights_only=False)["trainable"],
                            strict=False)
    trained.eval()
    f = torch.load(feats / "feats_00000.pt")["u0"]
    vi = M.lang_id("vi")
    args = (f["text_ids"].long(), f["codes"].long(), f["spk"].float()[None], f["emo"].float()[None], vi)
    with torch.no_grad():
        assert torch.allclose(train_mel_logits(trained, *args), train_mel_logits(fresh, *args), atol=1e-3)
        # model xuất ra đọc thuộc câu đã train qua đường suy luận chính thức
        logits = inference_mel_logits(fresh, *args)
    acc = (logits[:-1].argmax(-1) == f["codes"].long()).float().mean()
    assert acc > 0.9
