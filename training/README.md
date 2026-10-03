# Finetune IndexTTS cho tiếng Việt — runbook (1/10–31/10)

Chỉ finetune khối GPT (Text-to-Semantic) và thêm một hàng điều kiện ngôn ngữ `VI`. Semantic
codec, S2M, BigVGAN và các conditioner giữ đóng băng. Hạn chốt mô hình là **28/10**.

Nhóm tác giả chưa công bố mã train, nên vòng lặp train lấy từ mã cộng đồng: nhánh
JarodMica `training_v2` (`train_bpe.py`, `generate_gpt_pairs.py`, `train_gpt_v2.py`) và
`training_config.yaml` của bản tiếng Đức. Thư mục này chỉ chứa phần dành riêng cho tiếng
Việt; vòng lặp train không viết lại.

## Tuần 1 (1–7/10): dựng khung và kiểm chứng

1. Chạy baseline trên cùng 100 câu dev (cần `data/splits/dev_tts.jsonl`, xem `data_prep/`):
   ```bash
   python -m eval.eval_tts data/splits/dev_tts.jsonl --name indextts_goc   -c configs/gpu.yaml --set synthesize.indextts.model_dir=checkpoints/indextts ...
   python -m eval.eval_tts data/splits/dev_tts.jsonl --name dinhthuan      -c configs/gpu.yaml
   python -m eval.eval_tts data/splits/dev_tts.jsonl --name f5_vi          -c configs/f5_vi.yaml
   python -m eval.eval_tts --compare results/tts/*/summary.json
   ```
   Kết quả của IndexTTS gốc chính là mốc "trước finetune".
2. Đọc mã train cộng đồng, port sang 2.5 (codec 25 Hz, embedding ngôn ngữ).
3. Overfit khoảng 1 giờ dữ liệu: loss phải giảm và suy luận phải ra tiếng Việt nghe được.
   **Nếu tới 10/10 vẫn không đạt** → finetune IndexTTS2 bằng `training_v2` (đã được kiểm chứng).

## Tuần 2 (8–14/10): tokenizer + dữ liệu

```bash
# 1. Mở rộng vocab BPE (giữ token cũ, thêm âm tiết + ký tự có dấu). --case phải khớp front-end của IndexTTS.
python training/extend_tokenizer.py checkpoints/indextts/bpe.model data/splits/train.jsonl \
    checkpoints/indextts_vi/bpe.model --num-syllables 4000 --case upper
#    -> kiểm tra *.report.json: unk_tokens phải bằng 0; tokens_per_syllable phải giảm rõ.

# 2. Mở rộng embedding GPT theo vocab mới (hàng mới = trung bình hàng cũ).
python training/resize_embeddings.py checkpoints/indextts/gpt.pth --list --old-vocab <N cũ>
python training/resize_embeddings.py checkpoints/indextts/gpt.pth --out checkpoints/indextts_vi/gpt.pth \
    --old-vocab <N cũ> --new-vocab <N mới> --extra <số token đặc biệt> --keys <tên tensor từ --list>
#    -> sửa number_text_tokens trong config.yaml.

# 3. Sinh cặp prompt/target cùng người nói và trích trước semantic token, đặc trưng điều kiện
#    (w2v-bert, CAMPPlus) bằng generate_gpt_pairs.py của mã cộng đồng.
```

## Tuần 3–4: Run 1, Run 2, gate

- Cấu hình mẫu: [`train_vi.yaml`](train_vi.yaml). LR 1e-5–5e-5, warmup rồi cosine, bf16, replay zh/en 10–20%.
- **Không tắt** cơ chế điều kiện thời lượng (cho embedding thời lượng bằng 0 với xác suất 30%), vì lồng tiếng cần điều khiển thời lượng.
- Run 1 (đến ~17/10): 100–200 giờ để dò siêu tham số. Run 2 (đến ~28/10): toàn bộ dữ liệu.
- Mỗi checkpoint chấm trên `dev_tts.jsonl` với seed và prompt cố định:
  ```bash
  python -m eval.eval_tts data/splits/dev_tts.jsonl --name run1_step20k -c configs/gpu.yaml \
      --set synthesize.indextts.model_dir=checkpoints/run1/step20k
  ```
  rồi nghe tay 10 mẫu.

### Gate 28/10

Đạt khi cả ba điều kiện đúng: CER ≤ 5%, SS không thấp hơn dinhthuan, nghe không có lỗi thanh điệu rõ.

- **Đạt** → đổi `configs/gpu.yaml` sang checkpoint finetune.
- **Không đạt** → pipeline giữ dinhthuan; phần finetune viết thành chương thực nghiệm và phân tích lỗi.

| Dấu hiệu | Xử lý |
| --- | --- |
| SS giảm mạnh so với baseline (mất khả năng clone giọng) | Tăng số người nói, giảm LR, tăng replay zh/en, giảm số bước |
| Một epoch dài hơn 2 ngày | Cắt còn 200 giờ, dùng LoRA, thuê GPU theo giờ |
| CER dev không giảm sau Run 1 | Kiểm tra tokenizer (UNK, chữ hoa/thường), rồi xét gate sớm |
