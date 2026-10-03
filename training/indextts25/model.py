"""Dựng GPT của IndexTTS 2.5, chọn phần được train, và forward lúc train.

Chuỗi đầu vào lúc train phải giống hệt lúc suy luận (UnifiedVoice.inference_speech +
prepare_gpt_inputs, chế độ campplus):

    [cond: spk_emb_proj(CAMPPlus 192d) + emo_vec, 0, 0]                      3 vị trí
    [start_text, <|vi|>, token..., stop_text] + text_pos + lang_embedding(vi)
    [start_mel, semantic code..., stop_mel]   + mel_pos

Ở bản 2.5, hai vị trí sau cond luôn bằng 0 (không có embedding thời lượng trong GPT);
duration_factor được áp ở S2M. Mỗi mẫu được ghép liền rồi đệm bên phải, nên vị trí
của từng token trùng với lúc suy luận (test_indextts25 kiểm tra điều này).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

from .lora import apply_lora, lora_parameters

DEFAULT_REPO = Path(__file__).resolve().parents[2] / "third_party" / "index-tts"


def import_indextts(repo: str | Path | None = None) -> None:
    repo = Path(repo or os.environ.get("INDEX_TTS_REPO") or DEFAULT_REPO)
    if not (repo / "indextts" / "gpt" / "model_v2.py").exists():
        raise FileNotFoundError(f"Không thấy mã IndexTTS ở {repo}. Clone https://github.com/index-tts/index-tts "
                                "vào third_party/index-tts hoặc đặt INDEX_TTS_REPO.")
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))


def lang_id(lang: str) -> int:
    from indextts.utils.tokenizer import lang_to_token
    return lang_to_token(lang)


def build_gpt(gpt_kwargs: dict, checkpoint: str | None = None):
    """UnifiedVoice ở chế độ campplus — đúng như IndexTTS2 trong infer_v2_5.py khởi tạo."""
    from indextts.gpt.model_v2 import UnifiedVoice

    model = UnifiedVoice(**gpt_kwargs, spk_cond_mode="campplus")
    if checkpoint:
        from indextts.utils.checkpoint import load_checkpoint
        load_checkpoint(model, checkpoint)
    return model


def load_gpt_from_config(cfg_path: str, checkpoint: str | None = None):
    from omegaconf import OmegaConf

    cfg = OmegaConf.load(cfg_path)
    return build_gpt(OmegaConf.to_container(cfg.gpt, resolve=True), checkpoint)


@dataclass
class TrainSetup:
    lora_rank: int = 64
    lora_alpha: float = 128.0
    lora_dropout: float = 0.0
    lora_layers: int | None = None           # None = mọi lớp GPT
    train_text_embedding: bool = True
    train_output_heads: bool = True
    language: str = "vi"
    language_initialization: str | None = "en"
    language_initialization_noise: float = 0.0
    gradient_checkpointing: bool = True


def prepare_for_training(model: nn.Module, setup: TrainSetup) -> dict[str, list[nn.Parameter]]:
    """Đóng băng toàn bộ, gắn LoRA, mở các phần cần train. Trả về nhóm tham số cho optimizer."""
    for p in model.parameters():
        p.requires_grad_(False)

    apply_lora(model.gpt, setup.lora_rank, setup.lora_alpha, setup.lora_dropout, layers=setup.lora_layers)
    groups: dict[str, list[nn.Parameter]] = {"lora": list(lora_parameters(model.gpt)), "embed": [], "head": [], "lang": []}
    for p in groups["lora"]:
        p.requires_grad_(True)

    if setup.train_text_embedding:
        model.text_embedding.weight.requires_grad_(True)
        groups["embed"].append(model.text_embedding.weight)
    if setup.train_output_heads:
        for head in (model.text_head, model.mel_head):
            for p in head.parameters():
                p.requires_grad_(True)
                groups["head"].append(p)

    vi = lang_id(setup.language)
    if setup.language_initialization:
        with torch.no_grad():
            src = model.lang_embedding.weight[lang_id(setup.language_initialization)]
            noise = torch.randn_like(src) * setup.language_initialization_noise
            model.lang_embedding.weight[vi] = src + noise
    model.lang_embedding.weight.requires_grad_(True)   # chỉ hàng `vi` có gradient
    groups["lang"].append(model.lang_embedding.weight)

    if setup.gradient_checkpointing:
        model.gpt.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    else:
        model.gpt.gradient_checkpointing_disable()
    return groups


def trainable_state_dict(model: nn.Module) -> dict[str, torch.Tensor]:
    """Chỉ những tensor được train (LoRA, embedding, head, hàng ngôn ngữ) — checkpoint nhỏ."""
    return {n: p.detach().cpu().clone() for n, p in model.named_parameters() if p.requires_grad}


def conditioning(model: nn.Module, spk: torch.Tensor, emo: torch.Tensor,
                 spk_noise_std: float = 0.0, emo_dropout: float = 0.0) -> torch.Tensor:
    """(B,192) CAMPPlus + (B,D) emo_vec -> (B,3,D) như inference_speech (campplus)."""
    lat = model.spk_emb_proj(spk)                                   # (B, D)
    if model.training and spk_noise_std > 0:
        lat = lat + torch.randn_like(lat) * spk_noise_std
    if model.training and emo_dropout > 0:
        keep = (torch.rand(emo.shape[0], 1, device=emo.device) >= emo_dropout).to(emo.dtype)
        emo = emo * keep
    first = (lat + emo).unsqueeze(1)
    return torch.cat([first, torch.zeros(first.shape[0], 2, first.shape[2], device=first.device, dtype=first.dtype)], 1)


@dataclass
class Batch:
    text_ids: list[torch.Tensor]     # token văn bản (đã có <|vi|> ở đầu), chưa có start/stop
    codes: list[torch.Tensor]        # semantic code, chưa có start/stop
    spk: torch.Tensor                # (B, 192)
    emo: torch.Tensor                # (B, D)

    def to(self, device):
        return Batch([t.to(device) for t in self.text_ids], [c.to(device) for c in self.codes],
                     self.spk.to(device), self.emo.to(device))


def forward_train(model: nn.Module, batch: Batch, lang: int, text_loss_weight: float = 0.2,
                  mel_loss_weight: float = 1.0, spk_noise_std: float = 0.0, emo_dropout: float = 0.0) -> dict:
    device = batch.spk.device
    conds = conditioning(model, batch.spk, batch.emo, spk_noise_std, emo_dropout)
    n_cond = conds.shape[1]
    lang_vec = model.lang_embedding(torch.tensor(lang, device=device))

    seqs, text_pos, text_tgt, mel_pos, mel_tgt = [], [], [], [], []
    for i, (txt, code) in enumerate(zip(batch.text_ids, batch.codes)):
        t = F.pad(F.pad(txt.long(), (1, 0), value=model.start_text_token), (0, 1), value=model.stop_text_token)
        m = F.pad(F.pad(code.long(), (1, 0), value=model.start_mel_token), (0, 1), value=model.stop_mel_token)
        t_emb = model.text_embedding(t) + model.text_pos_embedding.emb(torch.arange(len(t), device=device)) + lang_vec
        m_emb = model.mel_embedding(m) + model.mel_pos_embedding.emb(torch.arange(len(m), device=device))
        seqs.append(torch.cat([conds[i], t_emb, m_emb], 0))
        # vị trí j dự đoán token j+1 (causal LM)
        t0, m0 = n_cond, n_cond + len(t)
        text_pos.append(torch.stack([torch.full((len(t) - 1,), i, device=device),
                                     torch.arange(t0, t0 + len(t) - 1, device=device)], 1))
        text_tgt.append(t[1:])
        mel_pos.append(torch.stack([torch.full((len(m) - 1,), i, device=device),
                                    torch.arange(m0, m0 + len(m) - 1, device=device)], 1))
        mel_tgt.append(m[1:])

    lengths = torch.tensor([len(s) for s in seqs], device=device)
    emb = nn.utils.rnn.pad_sequence(seqs, batch_first=True)               # đệm bên phải
    mask = (torch.arange(emb.shape[1], device=device)[None] < lengths[:, None]).long()
    hidden = model.gpt(inputs_embeds=emb, attention_mask=mask, return_dict=True).last_hidden_state
    hidden = model.final_norm(hidden)

    tp, mp = torch.cat(text_pos), torch.cat(mel_pos)
    tt, mt = torch.cat(text_tgt), torch.cat(mel_tgt)
    text_logits = model.text_head(hidden[tp[:, 0], tp[:, 1]])
    mel_logits = model.mel_head(hidden[mp[:, 0], mp[:, 1]])
    text_loss = F.cross_entropy(text_logits.float(), tt)
    mel_loss = F.cross_entropy(mel_logits.float(), mt)
    with torch.no_grad():
        mel_acc = (mel_logits.argmax(-1) == mt).float().mean()
    return {
        "loss": text_loss_weight * text_loss + mel_loss_weight * mel_loss,
        "text_loss": text_loss.detach(),
        "mel_loss": mel_loss.detach(),
        "mel_acc": mel_acc,
        "mel_tokens": torch.tensor(len(mt)),
    }
