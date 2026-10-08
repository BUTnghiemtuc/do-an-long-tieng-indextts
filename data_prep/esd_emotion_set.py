"""Bộ test chuyển cảm xúc: câu mẫu tiếng Anh có cảm xúc (ESD) + văn bản tiếng Việt trung tính.

Mô phỏng đúng tình huống lồng tiếng: diễn viên gốc nói tiếng Anh với một cảm xúc, câu tiếng Việt
phải giữ giọng và cảm xúc đó. Câu mẫu vừa là giọng (prompt_audio) vừa là cảm xúc (style_audio).
Cùng một người nói thì mọi cảm xúc dùng cùng các câu văn bản, nên cảm xúc ở đầu ra chỉ có thể
đến từ câu mẫu. ESD: Zhou et al. 2021, CC-BY-NC-4.0 (chỉ dùng để đánh giá).

  python -m data_prep.esd_emotion_set data/esd_en --per-emotion 2
  python -m eval.eval_tts data/esd_en/emotion_test.jsonl --es --name emo_<model> ...
"""

from __future__ import annotations

import argparse
import io
from collections import defaultdict
from pathlib import Path

import soundfile as sf

from .common import write_jsonl

REPO = "jspaulsen/esd"
FILES = [f"data/train-0000{k}-of-00007.parquet" for k in (4, 5, 6)]   # người nói tiếng Anh 0012–0020
TEXTS = [
    "Anh không ngờ mọi chuyện lại thành ra như thế này.",
    "Chúng ta phải rời khỏi đây trước khi trời tối.",
    "Em đã đợi anh ở đây suốt cả buổi chiều.",
    "Tôi vừa nhận được tin từ bệnh viện.",
    "Cậu có biết hôm nay là ngày gì không?",
    "Mọi người đều đã về nhà hết rồi.",
    "Đây là lần đầu tiên tôi nhìn thấy nó.",
    "Bố mẹ sẽ đến thăm chúng ta vào cuối tuần này.",
    "Tôi không muốn nói về chuyện đó nữa.",
    "Cô ấy đã gọi điện cho tôi lúc nửa đêm.",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--per-emotion", type=int, default=2, help="số câu mẫu mỗi (người nói, cảm xúc)")
    ap.add_argument("--min-dur", type=float, default=2.0)
    ap.add_argument("--max-dur", type=float, default=6.0)
    args = ap.parse_args()

    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    out = Path(args.out_dir)
    (out / "wavs").mkdir(parents=True, exist_ok=True)
    picked: dict[tuple[str, str], int] = defaultdict(int)
    rows = []
    for fname in FILES:
        table = pq.read_table(hf_hub_download(REPO, fname, repo_type="dataset"))
        for ex in table.to_pylist():
            if ex["language"] != "en":
                continue
            key = (ex["speaker_id"], ex["emotion"])
            if picked[key] >= args.per_emotion:
                continue
            wav, sr = sf.read(io.BytesIO(ex["audio"]["bytes"]), dtype="float32")
            if not args.min_dur <= len(wav) / sr <= args.max_dur:
                continue
            j = picked[key]
            picked[key] += 1
            uid = f"esd_{ex['speaker_id']}_{ex['emotion']}_{j}"
            path = (out / "wavs" / f"{uid}.wav").resolve()
            sf.write(path, wav, sr)
            spk_idx = int(ex["speaker_id"])
            rows.append({"id": uid, "text": TEXTS[(spk_idx * args.per_emotion + j) % len(TEXTS)],
                         "speaker": f"esd:{ex['speaker_id']}", "gender": ex.get("gender"), "emotion": ex["emotion"],
                         "prompt_audio": str(path), "style_audio": str(path), "prompt_text_en": ex["transcript"]})
    rows.sort(key=lambda r: r["id"])
    write_jsonl(out / "emotion_test.jsonl", rows)
    by_emo = defaultdict(int)
    for r in rows:
        by_emo[r["emotion"]] += 1
    print(f"{len(rows)} câu, {len({r['speaker'] for r in rows})} người nói, theo cảm xúc: {dict(by_emo)}")
    print(f"-> {out / 'emotion_test.jsonl'}")


if __name__ == "__main__":
    main()
