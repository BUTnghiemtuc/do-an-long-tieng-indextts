"""LoRA tối giản cho lớp Conv1D của GPT-2 (transformers): y = x @ W + b, với W có shape [in, out].

Tự viết thay vì dùng peft để: (1) không phụ thuộc phiên bản peft, (2) gộp (merge) ra đúng
tên tensor gốc, nên checkpoint xuất ra nạp thẳng bằng load_checkpoint của IndexTTS.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn

DEFAULT_TARGETS = ("attn.c_attn", "attn.c_proj", "mlp.c_fc", "mlp.c_proj")


class LoRAConv1D(nn.Module):
    def __init__(self, base: nn.Module, r: int, alpha: float, dropout: float = 0.0):
        super().__init__()
        self.base = base
        in_features, out_features = base.weight.shape
        self.r = r
        self.scaling = alpha / r
        self.lora_A = nn.Parameter(torch.empty(r, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, r))   # B = 0: lúc đầu y hệt model gốc
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        self.dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        delta = self.dropout(x).to(self.lora_A.dtype) @ self.lora_A.t() @ self.lora_B.t()
        return self.base(x) + (delta * self.scaling).to(x.dtype)

    @torch.no_grad()
    def merged(self) -> nn.Module:
        """Trả về Conv1D gốc với W' = W + (B A)^T * scaling."""
        base = self.base
        delta = (self.lora_B @ self.lora_A).t() * self.scaling
        base.weight.data += delta.to(base.weight.dtype)
        return base


def _get_parent(root: nn.Module, dotted: str) -> tuple[nn.Module, str]:
    parts = dotted.split(".")
    parent = root
    for p in parts[:-1]:
        parent = getattr(parent, p)
    return parent, parts[-1]


def apply_lora(gpt2: nn.Module, r: int, alpha: float, dropout: float = 0.0,
               targets: tuple[str, ...] = DEFAULT_TARGETS, layers: int | None = None) -> list[str]:
    """Gắn LoRA vào `layers` khối đầu tiên của gpt2.h (None = tất cả). Trả về tên các module đã gắn."""
    blocks = gpt2.h if layers is None else gpt2.h[:layers]
    names = []
    for i, block in enumerate(blocks):
        for t in targets:
            parent, attr = _get_parent(block, t)
            base = getattr(parent, attr)
            if isinstance(base, LoRAConv1D):
                continue
            setattr(parent, attr, LoRAConv1D(base, r, alpha, dropout))
            names.append(f"h.{i}.{t}")
    return names


def merge_lora(module: nn.Module) -> int:
    """Gộp mọi LoRAConv1D bên trong `module` vào trọng số gốc. Trả về số lớp đã gộp."""
    count = 0
    for name, child in list(module.named_modules()):
        for attr, sub in list(child.named_children()):
            if isinstance(sub, LoRAConv1D):
                setattr(child, attr, sub.merged())
                count += 1
    return count


def lora_parameters(module: nn.Module):
    for m in module.modules():
        if isinstance(m, LoRAConv1D):
            yield m.lora_A
            yield m.lora_B
