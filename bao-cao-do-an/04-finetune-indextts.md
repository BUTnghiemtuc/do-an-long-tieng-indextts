# Tư liệu Chương 4: Finetune IndexTTS 2.5 cho tiếng Việt

Mọi số dưới đây trích từ log trong repo. Nguồn ghi ở cột hoặc dòng cuối mỗi bảng.

## 4.1 Chọn mô hình và phần cần train

- Chỉ finetune khối **T2S (GPT)** của IndexTTS 2.5. Lý do và bảng module xem [02-co-so-ly-thuyet.md](02-co-so-ly-thuyet.md) mục 2.3.
- Cấu hình chép theo bản finetune tiếng Đức (`sharrnah/index-tts-2.5-german`, `training_config.yaml`), chỉ đổi ngôn ngữ và đường dẫn.
- Hai điểm thay đổi so với kế hoạch đồ án ban đầu, rút ra sau khi đọc mã 2.5:
  - **Không mở rộng tokenizer.** Tokenizer kiểu Whisper đã có `<|vi|>` và không ra UNK. Script `training/extend_tokenizer.py` chỉ giữ cho phương án dự phòng IndexTTS2.
  - **Dùng LoRA thay vì train toàn bộ GPT.**
- Script train **tự viết** (`training/indextts25/`), vì IndexTTS 2.5 chỉ công bố mã suy luận. Script ghép từ ba nguồn:
  - `forward` của `UnifiedVoice` trong `model_v2_5.py`;
  - cách nạp dữ liệu và tính loss của `train_gpt_v2.py` (nhánh JarodMica);
  - LoRA lấy từ ý tưởng của thư viện `peft`, cài lại cho Conv1D của GPT-2 (`lora.py`).

Thứ tự đặt câu hỏi khi viết mục này: vì sao không train toàn bộ, vì sao không mở rộng tokenizer, vì sao không đụng S2M.

## 4.2 Dữ liệu

### Nguồn

| Bộ | Quy mô gốc | Người nói | License | Lấy bao nhiêu | Vai trò |
| --- | --- | --- | --- | --- | --- |
| [viVoice](https://huggingface.co/datasets/capleaf/viVoice) | 1.017 giờ, 887.772 câu, 24 kHz | 186 kênh YouTube | CC BY-NC-SA 4.0, phải xin quyền bằng email trường | 2 đợt × 150 giờ, tối đa ~1 giờ mỗi kênh | Khối chính, giọng tự nhiên |
| [PhoAudiobook](https://huggingface.co/datasets/thivux/phoaudiobook) | 940 giờ gốc (+554 giờ augment) | 710 (train) + 45 | Chỉ dùng cho nghiên cứu, phải trích dẫn paper | 2 đợt × 100 giờ, tối đa ~0,3 giờ mỗi người | Câu dài, đọc rõ |
| [ViMD](https://huggingface.co/datasets/nguyendv02/ViMD_Dataset) | 102,56 giờ, khoảng 19.000 câu | **12.955**, 63 tỉnh | CC BY-NC-ND 4.0 | Toàn bộ phần tải được | Đa dạng giọng ba miền, dùng làm nhãn người nói thật |
| [ESD](https://github.com/HLTSingapore/Emotional-Speech-Data) (`jspaulsen/esd`), người nói tiếng Anh 0012–0020 | — | 9 | CC BY-NC 4.0 | 86 câu (5 cảm xúc) | **Chỉ để đánh giá** chuyển cảm xúc |

Các bộ chỉ được phép dùng phi thương mại hoặc cho nghiên cứu. Checkpoint chỉ công bố kèm điều kiện phi thương mại, giống bản Đức ghi trong `NOTICE.md`.

### Kết quả tải về (`logs/import_*.log`)

| Manifest | Số câu | Giờ | Người nói |
| --- | ---: | ---: | ---: |
| vimd | 15.023 | 81,4 | 10.291 |
| vivoice (đợt 1) | 131.570 | 150,0 | 186 |
| vivoice_more (đợt 2) | 133.981 | ~150* | 186 |
| phoaudiobook (đợt 1) | 86.834 | 100,0 | 432 |
| phoaudiobook_more (đợt 2) | 79.457 | ~100* | 500 (cộng dồn) |

\* Log của đợt 2 in ra số giờ cộng dồn (300 và 200 giờ). Số giờ của riêng đợt 2 suy ra là khoảng 150 và 100 giờ, **cần kiểm lại** bằng `python -m data_prep.stats data/clean/vivoice_more.jsonl` trước khi đưa vào báo cáo.

### Phễu lọc (`data_prep/filter.py`; số trong `so-lieu/pheu-loc-du-lieu.csv`)

Năm bước lọc:

1. Giữ câu dài 1–25 s. Giới hạn 25 s theo paper 2.5.
2. Chuẩn hoá văn bản (`vi_normalize`).
3. ASR kiểm tra transcript bằng `parakeet-ctc-0.6b-vi`. Ngưỡng CER ≤ 10%; riêng PhoAudiobook ≤ 5%.
4. Bỏ 12% câu có UTMOS thấp nhất.
5. Mỗi người nói phải có ít nhất 2 câu, để ghép được cặp giọng mẫu/câu đích.

| Bộ | Đầu vào | Sau lọc độ dài | Sau lọc CER | Sau lọc UTMOS | Sau lọc ≥2 câu | Giữ lại |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ViMD | 15.023 | 11.751 | 7.083 | 6.241 | 2.566 | 17,1% |
| viVoice đợt 1 | 131.570 | 123.476 | 100.171 | 88.169 | 88.169 | 67,0% |
| viVoice đợt 2 | 133.981 | 128.653 | 109.087 | 96.027 | 96.025 | 71,7% |
| PhoAudiobook đợt 1 | 86.834 | 84.406 | 72.940 | 64.194 | 64.182 | 73,9% |
| PhoAudiobook đợt 2 | 79.457 | 77.461 | 67.278 | 59.225 | 59.197 | 74,5% |
| **Tổng** | **446.865** | | | | **310.139** | **69,4%** |

Nhận xét cho báo cáo:

- ViMD mất nhiều nhất. Nguyên nhân thứ nhất: nhiều câu dài 20–30 s. Nguyên nhân thứ hai: rất nhiều người nói chỉ có 1 câu, nên bước "≥2 câu" bỏ 59% số câu còn lại.
- Ngưỡng UTMOS khác nhau giữa các bộ (1,29 / 1,94 / 2,03 / 1,82). Lý do: ngưỡng tính theo phân vị 12% của từng bộ, không phải một ngưỡng cố định.

### Chia tập (`data_prep/split.py`)

| Lần chia | Train | Dev | Test zero-shot |
| --- | --- | --- | --- |
| Run 1 (`data/splits_run1`) | 148.481 câu, 188,3 giờ, 1.709 người nói | 100 câu | 182 câu, 25 người nói |
| Run 2 (`data/splits`) | **298.465 câu, 371,2 giờ, 1.786 người nói** | 100 câu (95 có câu mẫu) | 184 câu → còn **180 câu** sau khi chọn lại câu mẫu, 25 người nói |

- 25 người nói của tập test **không có câu nào trong train**.
- Lần chia Run 2 chia lại từ đầu, nên một số người nói thuộc tập test của Run 2 có thể đã có trong train của Run 1. Bảng kết quả của Run 1 trên tập test đã ghi chú điểm này.

Thống kê tập train của Run 2 (`docs/data_stats.md`):

| Bộ | Số câu | Giờ | Người nói |
| --- | ---: | ---: | ---: |
| phoaudiobook | 122.295 | 146,59 | 466 |
| vimd | 2.514 | 12,06 | 1.142 |
| vivoice | 173.656 | 212,51 | 178 |
| **Tổng** | **298.465** | **371,16** | **1.786** |

- Tốc độ nói trung vị **4,0 âm tiết/giây**, p10–p90 = 2,92–4,98. Lần chia Run 1 đo được 3,98.
- Phân bố độ dài câu: 0–2 s: 69.297 · 2–4 s: 109.046 · 4–6 s: 50.630 · 6–8 s: 24.337 · 8–10 s: 12.611 · 10–15 s: 29.746 · 15–20 s: 2.026 · 20–25 s: 772.

### Ghép cặp giọng mẫu / câu đích và lọc theo độ giống giọng (`training/indextts25/make_pairs.py`)

Mỗi câu đích được ghép với 2 câu khác của cùng người nói, dùng làm giọng mẫu, giống cách bản Đức làm.

**Vấn đề phát hiện được:** nhãn người nói của viVoice là **kênh YouTube**, không phải người thật. Đo cosine CAMPPlus giữa các cặp cùng nhãn:

- viVoice: khoảng **1/3** số cặp cùng kênh có cosine < 0,5, tức là hai người khác nhau;
- ViMD (nhãn là người thật): chỉ 0,3%.

**Cách xử lý:** chỉ giữ cặp có cosine ≥ 0,5. Câu mẫu của dev lấy từ train. Tập test chọn lại câu mẫu cùng giọng thật bằng `data_prep/test_prompts.py`.

Kết quả ghép (`logs/run2.log`):

- Train: **592.951 cặp** cho 298.013 câu đích. 99,8% câu đích còn ít nhất một câu mẫu đạt ngưỡng: phoaudiobook 122.247/122.295, vimd 2.499/2.514, vivoice 173.267/173.656.
- Dev: 199 cặp cho 100 câu.
- Run 1: 293.057 cặp.

### Trích đặc trưng trước (`prepare_features.py`)

Mỗi câu được trích một lần duy nhất:

- token ngữ nghĩa (w2v-BERT 2.0 → codec 25 Hz);
- vector giọng CAMPPlus (192 chiều);
- vector cảm xúc;
- token văn bản.

Các module tạo ra những đặc trưng này đều đóng băng, nên lúc train GPU chỉ còn phải chạy GPT. Trích đặc trưng cho phần dữ liệu thêm của Run 2 mất khoảng 6,5 giờ (21:21 ngày 6/10 → 03:53 ngày 7/10).

## 4.3 Cấu hình huấn luyện (`training/indextts25/config_vi.yaml`)

| Tham số | Bản Đức | Đồ án | Lý do |
| --- | --- | --- | --- |
| LoRA | r 64, α 128, dropout 0, cả 24 lớp | Giữ nguyên | Đã được chứng minh hiệu quả trên tiếng Đức |
| Phần train đầy đủ | Embedding văn bản, output head | Giữ nguyên | Token tiếng Việt cần vector mới |
| Hàng ngôn ngữ | `de`, khởi tạo từ `en`, LR ×5 | `vi` (id 19), khởi tạo từ `en` (id 0), LR ×5 | Cùng là chữ Latin |
| Nhánh speaker / emotion | Đóng băng | Giữ nguyên | Giữ khả năng clone giọng và chuyển cảm xúc |
| Learning rate | 5e-5, warmup 1.000, cosine xuống 8% | **5e-5** (Run 1 so với 2e-5) | Kiểm tra lại trên dữ liệu và mô hình mới |
| Batch | 8 × tích luỹ 4 = 32 | 8 × 4 = 32, bật gradient checkpointing | Bảng 4.x benchmark VRAM bên dưới |
| Epoch | 3 | 3 | — |
| Trọng số loss | text 0,2 / mel (token ngữ nghĩa) 1,0 | Giữ nguyên | dinhthuan cũng dùng text 0,2 |
| Khác | weight decay 0,01; clip 1,0; bf16; seed 1234; nhiễu vector giọng 0,01; emotion dropout 0,1 | Giữ nguyên | — |
| `emotion_from_target_prob` | — | 0 (Run 1, Run 2); **0,5 / 1,0 (Run 3 thử nghiệm)** | Mục 4.5 |

**Tham số được train:** 197,1M trên tổng 843,7M (23,4%).

Ba giả định khi cài đặt, vì config bản Đức chỉ ghi tên tham số mà không ghi cách cài:

- `emotion_dropout` = đưa vector cảm xúc về 0;
- `speaker_noise_std` = nhiễu Gauss cộng vào sau `spk_emb_proj`;
- vị trí gắn LoRA là 4 vị trí mỗi lớp.

### Chọn batch size cho GPU 16 GB (`so-lieu/benchmark-vram.csv`, `logs/bench*.log`)

Batch hiệu dụng luôn là 32, nên kết quả học không đổi; chỉ VRAM và tốc độ thay đổi.

| Dữ liệu đo | batch × tích luỹ | Gradient checkpointing | VRAM đỉnh | Giây/bước |
| --- | --- | --- | ---: | ---: |
| 1.000 cặp dài nhất (trường hợp xấu nhất) | 8 × 4 | bật | 7,59 GB | 3,23 |
| | 16 × 2 | bật | 9,04 GB | 3,21 |
| | 4 × 8 | tắt | **OOM** | — |
| | 2 × 16 | tắt | 11,58 GB | 2,21 |
| 20.000 cặp bình thường | **8 × 4** | **bật** | **6,98 GB** | **0,75** |
| | 2 × 16 | tắt | 11,27 GB | 0,82 |

Chọn 8 × 4 có gradient checkpointing: nhanh nhất trên dữ liệu thật và dùng ít VRAM nhất. Đo trong Run 2 thực tế: VRAM đỉnh 7,41 GB, trung vị **0,748 s/bước**.

## 4.4 Các lần huấn luyện

Phần cứng: 1 × RTX 5070 Ti 16 GB, Intel Core Ultra 7 265KF, 30 GB RAM, PyTorch 2.8.0+cu128, transformers 4.52.1.

| Lần chạy | Ngày | Dữ liệu | Số bước | Thời gian | Mục đích | Kết quả chính |
| --- | --- | --- | --- | --- | --- | --- |
| Overfit | 4–5/10 | 600 câu ViMD | 1.500 (warmup 100) | 1,06 giờ (~2,5 s/bước vì câu ViMD dài) | Chứng minh script train đúng với trọng số thật | CER trên 6 câu đã train: **75,1% → 6,0%**. Dev loss tăng sau bước 500, đúng như dự kiến khi train có 600 câu |
| Run 1, LR 5e-5 | 6/10 | 188 giờ, 293.057 cặp | 9.159 (1 epoch) | ~2 giờ | Chọn LR | Dev loss 5,633; CER dev 4,1% |
| Run 1, LR 2e-5 | 6/10 | như trên | 9.159 | 2,0 giờ | Chọn LR | Dev loss 5,812; CER dev 5,4% → **chọn 5e-5** |
| **Run 2** | 7/10, 04:09–15:51 | 371 giờ, 592.951 cặp | **55.590** (3 epoch) | **11,7 giờ** | Mô hình chính | Chọn bước **28.000** theo CER dev, mục 4.5 |
| Run 3 thử nghiệm (p = 0,5) | 7/10, 17:41–19:47 | như Run 2 | 9.200 | 1,9 giờ | Khắc phục mất cảm xúc | Xem [06](06-thuc-nghiem.md) mục 6.4 |
| Run 3 thử nghiệm 2 (p = 1,0) | 7/10, đang chạy | như Run 2 | 9.200 | — | Kiểm tra hiệu ứng có tăng theo p không | **[ĐANG CHẠY]** (tmux `sweep`) |

Script của từng lần: `data/run1.sh`, `data/run2.sh`, `data/run3_pilot.sh`, `data/sweep_and_pilot2.sh`.

### Đường loss (`so-lieu/duong-loss-*.csv`)

Dev loss của Run 2, chấm mỗi 2.000 bước:

| Bước | 2k | 6k | 10k | 16k | 20k | 24k | **28k** | 36k | 44k | 54k | 55,59k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dev loss | 5,936 | 5,658 | 5,542 | 5,454 | 5,418 | 5,388 | **5,366** | 5,335 | 5,322 | **5,311** (thấp nhất) | 5,312 |
| Dev mel acc | 0,081 | 0,091 | 0,096 | 0,097 | 0,098 | 0,101 | 0,099 | 0,104 | 0,104 | 0,104 | 0,105 |

- Train loss bước 1: 9,75 (text 10,78, mel 7,60). Bước cuối: 5,36 (text 2,90, mel 4,78).
- **Điểm cần nhấn mạnh:** dev loss còn giảm đến bước 54.000, nhưng CER dev tốt nhất lại ở bước 28.000. Đó là lý do chọn checkpoint theo CER chứ không theo loss. Bản Đức cũng chọn ở khoảng 80% số bước chứ không chọn bước cuối. Tuy nhiên chênh lệch CER giữa các checkpoint từ 24k đến 55k nằm trong mức nhiễu đo (xem [06](06-thuc-nghiem.md) mục 6.2).
- So sánh dev loss giữa Run 1 và Run 2 phải cẩn thận: hai lần dùng hai lần chia tập khác nhau, nên tập dev khác nhau.

**Hình cần vẽ:**

- Hình 4.x: train loss (làm trơn) và dev loss của Run 2 theo bước, đánh dấu bước 28k.
- Hình 4.y: dev loss của Run 1 ở 2 mức LR.
- Hình 4.z: CER dev theo checkpoint, có dải nhiễu ±0,5 điểm.

## 4.5 Chọn checkpoint và export

- Export: gộp LoRA vào trọng số gốc → `gpt.pth` (~3 GB). Các file khác của model là liên kết tới bản gốc, nên thư mục nạp thẳng được bằng `IndexTTS2` của 2.5 (`training/indextts25/export.py`).
- Chấm các checkpoint Run 2 từ bước 24k, mỗi 4k một lần, cộng thêm bước cuối, trên 100 câu dev. Chọn theo CER nhỏ nhất, hoà thì lấy SS lớn hơn.
- Kết quả: **bước 028000** (`results/tts/run2_best_step.txt`).

## 4.6 Lệnh tái lập

Xem [docs/huong-dan-may-gpu.md](../docs/huong-dan-may-gpu.md) mục 5–9 và [training/README.md](../training/README.md).

Cập nhật CSV trong `so-lieu/` sau mỗi thí nghiệm mới:

```bash
/home/thor/miniconda3/envs/vidub/bin/python bao-cao-do-an/cap_nhat_so_lieu.py
```
