# Finetune IndexTTS 2.5 cho tiếng Việt — runbook

Kế hoạch chi tiết (lý do chọn module, dữ liệu, chi phí GPU) nằm trong tài liệu
[Kế hoạch finetune IndexTTS 2.5 cho tiếng Việt](https://claude.ai/code/artifact/7366d741-b2d8-4944-b6e6-06a47ad8c5d1).
Thư mục này là phần mã.

| File | Việc |
| --- | --- |
| [indextts25/model.py](indextts25/model.py) | Dựng GPT (`UnifiedVoice`, chế độ `campplus` như `infer_v2_5.py`), gắn LoRA, forward + loss |
| [indextts25/lora.py](indextts25/lora.py) | LoRA cho Conv1D của GPT-2, gộp ra đúng tên tensor gốc |
| [indextts25/prepare_features.py](indextts25/prepare_features.py) | Trích trước semantic code, vector giọng CAMPPlus, vector cảm xúc, token văn bản (GPU) |
| [indextts25/data.py](indextts25/data.py) | Dataset cặp giọng mẫu/câu đích, batch theo độ dài, tạo cặp cùng người nói |
| [indextts25/train.py](indextts25/train.py) | Vòng train: bf16, tích luỹ gradient, warmup + cosine, chấm dev, lưu và chạy tiếp |
| [indextts25/export.py](indextts25/export.py) | Gộp LoRA → `gpt.pth`, tạo thư mục model nạp thẳng bằng `IndexTTS2` của 2.5 |
| [indextts25/config_vi.yaml](indextts25/config_vi.yaml) | Cấu hình, chép từ bản finetune tiếng Đức |

## Những gì đã kiểm chứng (CPU, GPT tí hon, `pytest tests/test_indextts25.py`)

- Logit lúc train **trùng** logit của đường suy luận chính thức (`prepare_gpt_inputs` + `GPT2InferenceModel`), sai khác < 1e-4. Tức là thứ tự, vị trí và embedding ngôn ngữ ghép đúng như lúc model chạy thật.
- Đệm batch không làm đổi loss.
- Gộp LoRA cho ra đúng kết quả của model chưa gộp. Chỉ LoRA, embedding văn bản, hai head và bảng ngôn ngữ được train; nhánh speaker và emotion đứng yên.
- Model tí hon học thuộc dữ liệu giả (độ chính xác dev > 90%).
- Chạy tiếp từ checkpoint cho cùng kết quả với chạy liền một mạch.
- Model sau export, nạp bằng `load_checkpoint` của IndexTTS, cho cùng logit.

Chưa kiểm chứng: chạy với trọng số thật của IndexTTS 2.5 (cần GPU). Bước 2 dưới đây là phép thử đó.

## Chạy trên máy GPU thuê (Vast.ai / RunPod, RTX 4090)

```bash
# 1. Môi trường (image có CUDA 12.x, Python 3.10–3.11)
git clone git@github.com:BUTnghiemtuc/do-an-long-tieng-indextts.git vidub && cd vidub
git clone https://github.com/index-tts/index-tts third_party/index-tts   # đã đối chiếu ở commit d9e41aa
pip install -e third_party/index-tts        # hoặc: cd third_party/index-tts && uv sync
pip install -e ".[train]"
huggingface-cli download IndexTeam/IndexTTS-2.5 --local-dir checkpoints/IndexTTS-2.5

# 2. Phép thử nhanh: model gốc nói tiếng Việt ra sao (mốc "trước finetune")
python -m vidub.cli run clip.mp4 -c configs/gpu.yaml -c configs/indextts25_vi.yaml \
    --set synthesize.indextts.model_dir=checkpoints/IndexTTS-2.5 \
    --set synthesize.indextts.cfg_path=checkpoints/IndexTTS-2.5/config.yaml

# 3. Trích đặc trưng (manifest từ data_prep/split.py)
python -m training.indextts25.prepare_features data/splits/train.jsonl data/features/train \
    --model-dir checkpoints/IndexTTS-2.5 --split-name train
python -m training.indextts25.prepare_features data/splits/dev.jsonl data/features/dev \
    --model-dir checkpoints/IndexTTS-2.5 --split-name dev

# 4. Overfit (~1 giờ dữ liệu): loss phải giảm, câu đã train phải đọc đúng
python -m training.indextts25.train -c training/indextts25/config_vi.yaml \
    --set data.train_limit=600 --set train.max_steps=1500 --set train.warmup_steps=100 \
    --set run.eval_every=500 --set run.output_dir=runs/overfit

# 5. Run 1 (150 giờ, 1 epoch, so 2 mức LR) rồi Run 2 (toàn bộ, 3 epoch)
python -m training.indextts25.train -c training/indextts25/config_vi.yaml \
    --set train.epochs=1 --set train.learning_rate=5e-5 --set run.output_dir=runs/run1_lr5e-5
python -m training.indextts25.train -c training/indextts25/config_vi.yaml --set run.output_dir=runs/run2
# máy bị ngắt: thêm --resume runs/run2/step_XXXXXX.pt

# 6. Xuất checkpoint và chấm CER/SS trên dev (chọn theo CER, không theo loss)
python -m training.indextts25.export runs/run2/step_016000.pt \
    --base-dir checkpoints/IndexTTS-2.5 --out checkpoints/IndexTTS-2.5-vi-16k
python -m eval.eval_tts data/splits/dev_tts.jsonl --name vi_16k -c configs/indextts25_vi.yaml \
    --set synthesize.indextts.model_dir=checkpoints/IndexTTS-2.5-vi-16k \
    --set synthesize.indextts.cfg_path=checkpoints/IndexTTS-2.5-vi-16k/config.yaml
```

Theo dõi bằng `tensorboard --logdir runs/`. Thiếu VRAM: `--set train.batch_size=4 --set train.gradient_accumulation=8`.

## Các điểm khác IndexTTS2 cần nhớ

- **Tokenizer**: 2.5 dùng tokenizer kiểu Whisper, đã có `<|vi|>`. Không mở rộng vocab.
- **Embedding ngôn ngữ**: hàng `vi` (id 19) có sẵn, được khởi tạo từ `en` (id 0) và train với LR gấp 5.
- **Thời lượng**: GPT của 2.5 không có embedding thời lượng (hai vị trí sau cond luôn bằng 0). `duration_factor` co giãn ở S2M, nên không cần xử lý gì khi train.
- **Văn bản**: mọi chỗ đưa văn bản vào model đều phải qua `data_prep.vi_normalize.tts_frontend` (chuẩn hoá + viết thường) và đặt `text_normalization=False`. `prepare_features.py` và backend `indextts` (với `text_frontend: vi`) đã làm việc này.
- Script giả định `emotion_dropout` = vector cảm xúc về 0, còn `speaker_noise_std` = nhiễu Gauss cộng vào vector giọng sau `spk_emb_proj`. Cấu hình của bản Đức chỉ ghi tên tham số, không ghi cách cài đặt.

## Phương án dự phòng: IndexTTS2

`extend_tokenizer.py` và `resize_embeddings.py` dành cho IndexTTS2 (tokenizer SentencePiece). Chỉ dùng khi phải chuyển sang finetune IndexTTS2 bằng nhánh JarodMica `training_v2` (xem mục Rủi ro trong tài liệu kế hoạch).
