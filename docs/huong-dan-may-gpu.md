# Việc cần làm trên máy GPU (RTX 5090, RAM 16 GB)

Mục tiêu: chạy được bản finetune IndexTTS 2.5 tiếng Việt và qua **gate ngày 28/10**:

- CER ≤ 5% trên người nói chưa từng nghe;
- độ giống giọng (SS) không thấp hơn dinhthuan;
- nghe không thấy lỗi thanh điệu rõ.

Làm lần lượt từ trên xuống. Mỗi bước có mục "Đạt khi" để biết đã xong hay chưa.

Tài liệu liên quan:

- Kế hoạch đầy đủ (lý do, dữ liệu, rủi ro): [Kế hoạch finetune IndexTTS 2.5 cho tiếng Việt](https://claude.ai/code/artifact/7366d741-b2d8-4944-b6e6-06a47ad8c5d1)
- Mô tả mã finetune: [training/README.md](../training/README.md)

---

## 0. Trước khi rời máy cũ

- [ ] Push commit mới nhất lên GitHub: `git push` trong thư mục `vidub`. Commit `0b333fc` (script finetune) hiện mới chỉ có ở máy cũ.
- [ ] Gửi đơn xin quyền truy cập **viVoice** và **PhoAudiobook** trên HuggingFace bằng **email trường**. Email Gmail bị từ chối, và việc duyệt mất vài ngày.

## 1. Kiểm tra máy

```bash
nvidia-smi                 # tên GPU, VRAM, driver
free -h                    # RAM, swap
df -h ~                    # dung lượng trống
```

| Thứ cần kiểm | Yêu cầu | Ghi chú |
| --- | --- | --- |
| Driver NVIDIA | ≥ 570, dòng "CUDA Version" ≥ 12.8 | RTX 5090 (kiến trúc Blackwell) chỉ chạy với PyTorch bản CUDA 12.8 trở lên |
| VRAM | Xem dòng "Memory" của `nvidia-smi` | RTX 5090 bản desktop có 32 GB, bản laptop có 24 GB. Mục 7 chọn batch theo số này |
| RAM | 16 GB | Đủ, nhưng **phải tạo thêm swap 16 GB** (ngay dưới) |
| Ổ đĩa trống | ≥ 400 GB | Dữ liệu thô + WAV ~400 giờ (~70 GB) + đặc trưng + checkpoint (mỗi file ~1 GB) |
| Hệ điều hành | Ubuntu 22.04 / 24.04 | Windows thì dùng WSL2 (Ubuntu) và cài driver NVIDIA bản cho WSL |

Tạo swap. Swap giúp máy không bị treo khi nạp model 3 GB hoặc tải dataset lớn:

```bash
sudo fallocate -l 16G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**Đạt khi:** `nvidia-smi` thấy GPU, driver ≥ 570, `free -h` thấy Swap 16G.

## 2. Lấy mã và cài môi trường

```bash
sudo apt install -y git ffmpeg rubberband-cli tmux
# Miniconda: https://docs.conda.io/en/latest/miniconda.html
conda create -n vidub python=3.11 -y && conda activate vidub

git clone git@github.com:BUTnghiemtuc/do-an-long-tieng-indextts.git vidub && cd vidub
git clone https://github.com/index-tts/index-tts third_party/index-tts
git -C third_party/index-tts checkout d9e41aa      # bản đã đối chiếu khi viết script train

# PyTorch 2.8 bản CUDA 12.8: bắt buộc cho RTX 5090
pip install "torch==2.8.*" "torchaudio==2.8.*" --index-url https://download.pytorch.org/whl/cu128
pip install -e third_party/index-tts
pip install -e ".[train,eval,llm,server,dev]"
```

Cài thêm các mô hình cho pipeline lồng tiếng. Làm sau cùng, vì whisperx và pyannote hay kéo theo phiên bản torch khác:

```bash
pip install -e ".[gpu]"
python -c "import torch; print(torch.__version__, torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))"
```

Nếu dòng trên báo lỗi, hoặc torch bị đổi phiên bản, tạo một môi trường thứ hai riêng cho whisperx/pyannote. Pipeline chạy được từng bước bằng `--steps`, nên hai môi trường không vướng nhau.

Kiểm tra toàn bộ:

```bash
pytest -q                  # phải ra 36 passed
```

**Đạt khi:**

- dòng kiểm tra torch in ra `(12, 0)`;
- `pytest` ra 36 passed.

## 3. Tải model

```bash
huggingface-cli login                       # token đọc: https://huggingface.co/settings/tokens
huggingface-cli download IndexTeam/IndexTTS-2.5 --local-dir checkpoints/IndexTTS-2.5
huggingface-cli download dinhthuan/index-tts-2-vietnamese --local-dir checkpoints/dinhthuan   # baseline + dự phòng
```

Lần chạy đầu tiên, IndexTTS tự tải thêm w2v-BERT 2.0, semantic codec, CAMPPlus và BigVGAN vào `checkpoints/IndexTTS-2.5/hf_cache/`.

## 4. Phép thử nhanh: IndexTTS 2.5 gốc nói tiếng Việt

Chuẩn bị một file `prompt.wav`: 5–10 giây giọng nói rõ, của ai cũng được.

```bash
python - <<'EOF'
import sys; sys.path.insert(0, "third_party/index-tts")
from indextts.infer_v2_5 import IndexTTS2
from data_prep.vi_normalize import tts_frontend
tts = IndexTTS2(cfg_path="checkpoints/IndexTTS-2.5/config.yaml", model_dir="checkpoints/IndexTTS-2.5",
                use_bf16=True, use_qwen_emo=False)
text = tts_frontend("Anh chưa bao giờ nghe em nói cả. Ngày 2/9 chúng ta sẽ gặp lại.")
for lang in ["vi", "en"]:
    tts.infer(spk_audio_prompt="prompt.wav", text=text, output_path=f"base_{lang}.wav", lang=lang,
              text_normalization=False, temperature=0.7, top_p=0.8, top_k=30, num_beams=1,
              repetition_penalty=10.0)
EOF
```

Nghe hai file `base_vi.wav` và `base_en.wav`. Có thể chúng sai nhiều; đó là bình thường vì model chưa học tiếng Việt. Lưu lại hai file này làm mốc "trước finetune" cho báo cáo.

**Đạt khi:** chạy không lỗi và ra file âm thanh.

## 5. Dữ liệu (hạn 14/10)

Chi tiết từng bộ (số giờ, license, lấy bao nhiêu) xem mục "Dữ liệu" trong tài liệu kế hoạch. Trước khi chạy, mở trang dataset trên HuggingFace để kiểm tra tên cột (`--speaker-col`, `--text-col`).

```bash
# 5.1 Tải về WAV 24 kHz + manifest. --streaming để không nạp cả bộ vào RAM 16 GB
python -m data_prep.import_hf nguyendv02/ViMD_Dataset --speaker-col speakerID --name vimd \
    --out data/raw/vimd --streaming
python -m data_prep.import_hf capleaf/viVoice --speaker-col channel --name vivoice \
    --out data/raw/vivoice --streaming --max-hours 150 --max-per-speaker 1.0
python -m data_prep.import_hf thivux/phoaudiobook --speaker-col speaker --name phoaudiobook \
    --out data/raw/phoaudiobook --streaming --max-hours 100 --max-per-speaker 0.3

# 5.2 Lọc: độ dài 1–25 s, chuẩn hoá văn bản, ASR kiểm tra transcript (CER ≤ 10%), bỏ 12% chất lượng thấp nhất
pip install "nemo_toolkit[asr]"           # cho parakeet-ctc-0.6b-vi; không cài được thì thêm --asr whisper
python -m data_prep.filter data/raw/vimd/raw.jsonl data/clean/vimd.jsonl
python -m data_prep.filter data/raw/vivoice/raw.jsonl data/clean/vivoice.jsonl
python -m data_prep.filter data/raw/phoaudiobook/raw.jsonl data/clean/phoaudiobook.jsonl --max-cer 0.05

# 5.3 Chia tập (25 người nói test zero-shot, 100 câu dev) + thống kê cho chương 4
python -m data_prep.split data/clean/*.jsonl data/splits --test-speakers 25
python -m data_prep.stats data/splits/train.jsonl --md docs/data_stats.md
```

Trong lúc chờ duyệt viVoice và PhoAudiobook, làm trước với ViMD (~100 giờ, gần 13.000 người nói). ViMD đủ để chạy bước 6 và 7.

**Đạt khi:**

- `docs/data_stats.md` cho thấy 350–400 giờ, trên 1.000 người nói;
- tốc độ nói trung vị nằm trong khoảng hợp lý (~4–6 âm tiết/giây). Ghi số này vào `translate.vi_syllables_per_sec` trong `configs/default.yaml`.

## 6. Trích đặc trưng

```bash
tmux new -s prep                           # chạy trong tmux để mất kết nối SSH không bị dừng
python -m training.indextts25.prepare_features data/splits/train.jsonl data/features/train \
    --model-dir checkpoints/IndexTTS-2.5 --split-name train
python -m training.indextts25.prepare_features data/splits/dev.jsonl data/features/dev \
    --model-dir checkpoints/IndexTTS-2.5 --split-name dev
```

Script tự chạy tiếp nếu bị ngắt giữa chừng. Chạy lại cùng lệnh là được.

**Đạt khi:**

- `data/features/train/meta.json` có số câu khớp manifest;
- có file `pairs_train.jsonl` (khoảng 2 cặp mỗi câu).

## 7. Overfit (hạn 10/10)

Đây là phép thử quan trọng nhất: chứng minh script train chạy đúng với trọng số thật.

Chọn batch theo VRAM ở mục 1:

| VRAM | Thêm vào mọi lệnh train |
| --- | --- |
| 32 GB (5090 desktop) | Giữ mặc định: `batch_size 8 × gradient_accumulation 4` |
| 24 GB (5090 laptop) | `--set train.batch_size=4 --set train.gradient_accumulation=8` |
| Báo lỗi CUDA out of memory | Giảm `batch_size` một nửa, tăng `gradient_accumulation` gấp đôi (batch hiệu dụng giữ 32) |

Với RAM 16 GB, luôn thêm `--set data.num_workers=0`: mỗi worker sao chép toàn bộ đặc trưng trong RAM.

```bash
python -m training.indextts25.train -c training/indextts25/config_vi.yaml --set data.num_workers=0 \
    --set data.train_limit=600 --set train.max_steps=1500 --set train.warmup_steps=100 \
    --set run.eval_every=500 --set run.output_dir=runs/overfit
tensorboard --logdir runs/                 # mở cổng 6006 để xem đường loss
```

Xuất checkpoint và nghe thử một câu **đã có trong 600 câu train**:

```bash
python -m training.indextts25.export runs/overfit/step_001500.pt \
    --base-dir checkpoints/IndexTTS-2.5 --out checkpoints/overfit
# chạy lại đoạn mã ở mục 4 với model_dir="checkpoints/overfit", câu lấy từ data/splits/train.jsonl
```

**Đạt khi:**

- `mel_loss` giảm rõ, không đi ngang;
- `dev_mel_acc` tăng dần;
- câu đã train nghe ra đúng chữ tiếng Việt.

**Nếu không đạt**, kiểm tra theo thứ tự:

1. văn bản có qua `tts_frontend` không;
2. `lang` đã là `vi` chưa;
3. ba giả định trong `training/README.md`: `emotion_dropout`, nhiễu giọng, vị trí gắn LoRA.

Nếu tới 12/10 vẫn không đạt, chuyển sang phương án IndexTTS2 (mục Rủi ro trong tài liệu kế hoạch).

## 8. Run 1 rồi Run 2

```bash
# Run 1 (đến ~17/10): ~150 giờ, 1 epoch, so 2 mức learning rate
python -m training.indextts25.train -c training/indextts25/config_vi.yaml --set data.num_workers=0 \
    --set train.epochs=1 --set train.learning_rate=5e-5 --set run.output_dir=runs/run1_lr5e-5
python -m training.indextts25.train -c training/indextts25/config_vi.yaml --set data.num_workers=0 \
    --set train.epochs=1 --set train.learning_rate=2e-5 --set run.output_dir=runs/run1_lr2e-5

# Run 2 (đến 28/10): toàn bộ dữ liệu, 3 epoch, learning rate tốt hơn từ Run 1
python -m training.indextts25.train -c training/indextts25/config_vi.yaml --set data.num_workers=0 \
    --set train.learning_rate=<LR tốt hơn> --set run.output_dir=runs/run2
# máy tắt/ngắt: chạy lại cùng lệnh, thêm --resume runs/run2/step_XXXXXX.pt
```

Run 2 có khoảng 25.000 bước. Trên RTX 5090 ước tính 10–20 giờ. Con số chính xác lấy từ tốc độ đo được ở bước 7 (`elapsed_s` trong `runs/overfit/log.jsonl`).

## 9. Chọn checkpoint và đánh giá

Chọn checkpoint theo **CER trên dev**, không theo loss. Bản tiếng Đức chọn checkpoint ở khoảng 80% số bước, không phải bước cuối.

```bash
for s in 012000 016000 020000 024000; do
  python -m training.indextts25.export runs/run2/step_$s.pt --base-dir checkpoints/IndexTTS-2.5 \
      --out checkpoints/vi_$s
  python -m eval.eval_tts data/splits/dev_tts.jsonl --name vi_$s -c configs/indextts25_vi.yaml \
      --set synthesize.indextts.model_dir=checkpoints/vi_$s \
      --set synthesize.indextts.cfg_path=checkpoints/vi_$s/config.yaml
done
python -m eval.eval_tts --compare results/tts/*/summary.json
```

Mỗi thư mục `checkpoints/vi_*` chỉ chứa `gpt.pth` mới (~3 GB). Các file khác là liên kết tới model gốc. Xoá các bản không chọn để giữ ổ đĩa.

Sau đó chạy bộ test zero-shot (`data/splits/test_zeroshot.jsonl`) cho checkpoint tốt nhất và cho các baseline: IndexTTS 2.5 gốc, dinhthuan, F5-TTS (`configs/f5_vi.yaml`).

**Đạt gate khi:** CER ≤ 5%, SS ≥ dinhthuan, nghe 20 mẫu không thấy lỗi thanh điệu rõ.

## 10. Đưa vào pipeline lồng tiếng

```bash
cp -rL checkpoints/vi_<bước tốt nhất> checkpoints/IndexTTS-2.5-vi
python -m vidub.cli run clip.mp4 -c configs/gpu.yaml -c configs/indextts25_vi.yaml
```

Không đạt gate thì chạy pipeline với `-c configs/gpu.yaml` (TTS là dinhthuan). Phần finetune khi đó viết thành chương thực nghiệm và phân tích lỗi.

---

## Lưu ý riêng cho máy RAM 16 GB

- Không chạy `prepare_features` và `train` cùng lúc: mỗi tiến trình nạp model ~3–6 GB.
- Luôn dùng `--set data.num_workers=0` khi train và `--streaming` khi tải dataset.
- Đóng trình duyệt và các app nặng khi train. Theo dõi bằng `htop` và `nvidia-smi -l 5`.
- `train.py` nạp toàn bộ đặc trưng vào RAM. Với ~400 giờ dữ liệu, phần này chiếm khoảng 1 GB, không đáng lo.

## Lỗi hay gặp

| Lỗi | Cách xử lý |
| --- | --- |
| `no kernel image is available` / `sm_120 is not compatible` | Torch không phải bản CUDA 12.8 → cài lại theo mục 2 |
| `CUDA out of memory` | Giảm `batch_size`, tăng `gradient_accumulation` (mục 7) |
| Máy treo, tiến trình bị `Killed` | Hết RAM → kiểm tra swap (mục 1), `num_workers=0` |
| `401` / `gated repo` khi tải | `huggingface-cli login` và bấm chấp nhận điều khoản trên trang dataset/model |
| Lỗi import trong `transformers` | Phải đúng `transformers==4.52.1` (bản index-tts ghim) |
| WhisperX/CTranslate2 báo lỗi GPU | Cập nhật `ctranslate2` bản mới nhất, hoặc tách môi trường riêng cho bước transcribe (mục 2) |
| Loss không giảm | Xem mục "Nếu không đạt" ở bước 7 |

## Lịch

| Hạn | Việc |
| --- | --- |
| Ngay hôm nay | Mục 0: push code, xin quyền dataset |
| 6/10 | Mục 1–4: máy, môi trường, phép thử nhanh |
| 10/10 | Mục 7: overfit đạt (dùng ViMD nếu chưa có dữ liệu khác) |
| 14/10 | Mục 5–6: đủ dữ liệu, trích xong đặc trưng |
| 17/10 | Run 1 xong, chọn learning rate |
| 28/10 | Run 2 xong, chọn checkpoint, gate |
