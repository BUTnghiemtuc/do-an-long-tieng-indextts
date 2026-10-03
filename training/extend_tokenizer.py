"""Mở rộng vocab BPE (SentencePiece) gốc của IndexTTS cho tiếng Việt.

Giữ nguyên mọi token cũ (giữ khả năng zh/en), chỉ thêm vào cuối:
  1) mọi ký tự xuất hiện trong corpus mà vocab cũ chưa có (chữ có dấu, đ...);
  2) top-N âm tiết tiếng Việt phổ biến mà vocab cũ phải cắt thành >= 2 mảnh.
Sau đó báo tỉ lệ UNK (phải = 0) và số token trung bình mỗi âm tiết trước/sau.

QUAN TRỌNG: văn bản đưa vào đây phải đi qua đúng bước tiền xử lý mà IndexTTS dùng lúc
suy luận (xem TextNormalizer/TextTokenizer trong indextts/utils/front.py: chữ hoa/thường,
dấu câu). Chọn --case cho khớp; train và suy luận lệch nhau là lỗi phổ biến nhất.

  python training/extend_tokenizer.py checkpoints/indextts/bpe.model data/splits/train.jsonl \
      checkpoints/indextts_vi/bpe.model --num-syllables 4000 --case upper
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data_prep.common import read_jsonl  # noqa: E402

SPACE = "▁"


def prep(text: str, case: str) -> str:
    return text.upper() if case == "upper" else text.lower() if case == "lower" else text


def token_stats(sp, texts: list[str]) -> dict:
    n_tok = n_unk = n_syl = 0
    unk = sp.unk_id()
    for t in texts:
        ids = sp.encode(t)
        n_tok += len(ids)
        n_unk += sum(i == unk for i in ids)
        n_syl += len(t.split())
    return {"tokens_per_syllable": round(n_tok / max(1, n_syl), 3), "unk_rate": n_unk / max(1, n_tok), "unk_tokens": n_unk}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("base_model")
    ap.add_argument("manifest", nargs="+")
    ap.add_argument("out_model")
    ap.add_argument("--num-syllables", type=int, default=4000)
    ap.add_argument("--min-count", type=int, default=20)
    ap.add_argument("--case", choices=["keep", "upper", "lower"], default="keep")
    ap.add_argument("--text-field", default="text_norm")
    args = ap.parse_args()

    import sentencepiece as spm
    from sentencepiece import sentencepiece_model_pb2 as pb

    texts = [prep(r.get(args.text_field) or r["text"], args.case) for m in args.manifest for r in read_jsonl(m)]
    old = spm.SentencePieceProcessor(model_file=args.base_model)
    before = token_stats(old, texts)

    proto = pb.ModelProto()
    proto.ParseFromString(Path(args.base_model).read_bytes())
    existing = {p.piece for p in proto.pieces}
    old_size = len(proto.pieces)
    min_score = min(p.score for p in proto.pieces)

    def add(piece: str, score: float) -> None:
        if piece not in existing:
            p = pb.ModelProto.SentencePiece()
            p.piece, p.score = piece, score
            proto.pieces.append(p)
            existing.add(piece)

    chars = Counter(c for t in texts for c in t if not c.isspace())
    for c, _ in chars.most_common():
        add(c, min_score - 1)

    syllables = Counter(w.strip(".,!?;:…\"'") for t in texts for w in t.split())
    added_syl = 0
    for syl, cnt in syllables.most_common():
        if added_syl >= args.num_syllables or cnt < args.min_count:
            break
        if syl and len(old.encode(syl)) >= 2:
            # Encoder BPE chỉ ghép được "▁có" nếu có đường ghép qua các mảnh trung gian,
            # nên thêm cả chuỗi tiền tố "▁c" -> "▁có". Điểm thấp hơn mọi token cũ.
            piece = SPACE + syl
            for k in range(2, len(piece) + 1):
                add(piece[:k], min_score - 1 + cnt / 1e9)
            added_syl += 1

    Path(args.out_model).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_model).write_bytes(proto.SerializeToString())
    new = spm.SentencePieceProcessor(model_file=args.out_model)
    after = token_stats(new, texts)

    report = {"old_vocab": old_size, "new_vocab": len(proto.pieces), "added": len(proto.pieces) - old_size,
              "added_syllables": added_syl, "before": before, "after": after}
    Path(args.out_model).with_suffix(".report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if after["unk_tokens"]:
        print("CẢNH BÁO: vẫn còn UNK — kiểm tra ký tự lạ trong corpus hoặc tham số --case", file=sys.stderr)
    # Thứ tự token cũ không đổi: id 0..old_vocab-1 giữ nguyên nghĩa, nên checkpoint cũ dùng tiếp được.
    assert all(new.id_to_piece(i) == old.id_to_piece(i) for i in range(old_size))


if __name__ == "__main__":
    main()
