"""Mở rộng embedding văn bản (và đầu ra text_head nếu có) của checkpoint GPT theo vocab mới.

Hàng mới khởi tạo bằng TRUNG BÌNH các hàng cũ (theo kế hoạch), hàng cũ giữ nguyên.

Tên tensor trong checkpoint phụ thuộc phiên bản mã. Chạy --list trước để xem các tensor
có chiều bằng kích thước vocab cũ, rồi truyền đúng tên qua --keys:

  python training/resize_embeddings.py checkpoints/indextts/gpt.pth --list --old-vocab 12000
  python training/resize_embeddings.py checkpoints/indextts/gpt.pth \
      --out checkpoints/indextts_vi/gpt.pth --old-vocab 12000 --new-vocab 16234 \
      --keys text_embedding.weight text_head.weight text_head.bias

Lưu ý: một số bản cài đặt dùng kích thước vocab + vài token đặc biệt (start/stop text);
--extra cho biết số hàng đặc biệt nằm SAU vocab, sẽ được dời xuống cuối bảng mới.
Nhớ sửa number_text_tokens trong config.yaml cho khớp.
"""

from __future__ import annotations

import argparse


def unwrap(ckpt):
    for k in ("model", "state_dict", "module"):
        if isinstance(ckpt, dict) and k in ckpt and isinstance(ckpt[k], dict):
            return ckpt[k], k
    return ckpt, None


def main() -> None:
    import torch

    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("--out")
    ap.add_argument("--old-vocab", type=int, required=True)
    ap.add_argument("--new-vocab", type=int)
    ap.add_argument("--extra", type=int, default=0, help="số token đặc biệt nằm sau vocab")
    ap.add_argument("--keys", nargs="*", default=[])
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    sd, wrapper = unwrap(ckpt)
    rows_old = args.old_vocab + args.extra

    if args.list:
        for k, v in sd.items():
            if hasattr(v, "shape") and rows_old in tuple(v.shape):
                print(f"{k:60s} {tuple(v.shape)}")
        return

    added = args.new_vocab - args.old_vocab
    assert added > 0, "--new-vocab phải lớn hơn --old-vocab"
    for k in args.keys:
        w = sd[k]
        assert w.shape[0] == rows_old, f"{k}: chiều 0 = {w.shape[0]}, mong đợi {rows_old}"
        vocab, special = w[: args.old_vocab], w[args.old_vocab:]
        new_rows = vocab.mean(dim=0, keepdim=True).expand(added, *vocab.shape[1:]).clone()
        if w.dim() == 2:   # nhiễu nhỏ để các hàng mới không giống hệt nhau
            new_rows += torch.randn_like(new_rows) * vocab.std() * 0.01
        sd[k] = torch.cat([vocab, new_rows, special], dim=0)
        print(f"{k}: {tuple(w.shape)} -> {tuple(sd[k].shape)}")

    if wrapper:
        ckpt[wrapper] = sd
    torch.save(ckpt if wrapper else sd, args.out)
    print(f"Đã lưu {args.out}")


if __name__ == "__main__":
    main()
