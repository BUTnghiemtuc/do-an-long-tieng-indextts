# Tư liệu Chương 3: Phân tích và thiết kế hệ thống

**Dàn ý chi tiết đã viết xong** tại [docs/ke-hoach-chuong-3-thiet-ke-he-thong.md](../docs/ke-hoach-chuong-3-thiet-ke-he-thong.md). Dàn ý đó gồm 20 FR, 10 NFR, 8 quyết định kiến trúc, 6 thuật toán, danh sách khoảng 33 hình và 26 bảng, lịch viết và checklist nghiệm thu. File này không chép lại dàn ý, chỉ bổ sung những thứ cần tra nhanh khi viết.

## 3.1 Pipeline 8 bước (khớp với `vidub/steps/`)

| # | Bước | Công cụ | Backend chạy CPU để test |
| --- | --- | --- | --- |
| 1 | `extract` | ffmpeg | — |
| 2 | `separate` | Demucs htdemucs | `none` |
| 3 | `diarize` | pyannote 3.1 | `single` (VAD năng lượng) |
| 4 | `transcribe` | WhisperX large-v3 | `srt` |
| 5 | `translate` | Gemini 2.5 Flash qua OpenRouter (`google/gemini-2.5-flash`) | `copy` |
| 6 | `synthesize` | IndexTTS2 / 2.5 / bản finetune | `mock` |
| 7 | `align` | duration_factor → co giãn ±10% → mượn khoảng lặng | — |
| 8 | `mix` | pyloudnorm, ffmpeg | — |

Cache hai tầng:

- Bước 1–4 bỏ qua nếu đầu vào và cấu hình không đổi.
- Bước 5–7 có key riêng cho từng câu.
- Câu đã sửa tay (`vi_locked`) không bao giờ bị LLM dịch đè.

## 3.2 Tham số dùng trong công thức của chương

Lấy từ [configs/default.yaml](../configs/default.yaml) và [configs/indextts25_vi.yaml](../configs/indextts25_vi.yaml). Checklist chương yêu cầu số trong báo cáo phải trùng với config.

| Nhóm | Khoá | Giá trị | Dùng trong |
| --- | --- | --- | --- |
| diarize | `merge_gap` | 0,5 s | Gộp hai lượt cùng người nói |
| transcribe | `max_sentence_dur` / `pause_split` | 12 s / 0,6 s | Thuật toán 3.2 cắt câu |
| translate | `vi_syllables_per_sec` | **5,0 trong config, nhưng đo được 3,98** → phải sửa config | Ngân sách âm tiết N = max(1, round(d·r)) |
| translate | `length_tolerance` / `max_shorten_rounds` | 0,15 / 2 | Rút gọn khi n > N·1,15 |
| translate | `scene_gap` / `max_lines_per_scene` | 2 s / 25 câu | Chia cảnh |
| synthesize | `timbre_min_dur` / `timbre_max_dur` | 3 s / 10 s | Chọn giọng mẫu |
| synthesize | `emo_alpha` | 0,8 | Cường độ cảm xúc |
| synthesize (2.5) | `temperature` / `top_p` / `top_k` / `num_beams` / `repetition_penalty` | 0,7 / 0,8 / 30 / 1 / 10,0 | Như lúc chấm bản tiếng Đức |
| align | `duration_factor_min/max` | 0,75 / 1,25 | Bước 1 căn thời lượng |
| align | `ratio_tolerance` | 0,05 | Lệch dưới 5% thì không chỉnh |
| align | `max_stretch` | 0,10 | Co giãn ±10% |
| align | `max_borrow` / `min_gap` | 0,6 s / 0,08 s | Mượn khoảng lặng |
| align | `warn_ratio` | 0,10 | Gắn cảnh báo |
| mix | `dialog_lufs` | −20 LUFS | Chuẩn hoá loudness |

## 3.3 Phân hệ dữ liệu và huấn luyện (mục 3.7 của dàn ý)

Luồng dữ liệu (Hình 3.29):

```
import_hf → filter (độ dài, chuẩn hoá, ASR, UTMOS, ≥2 câu/người) → split → stats
→ prepare_features → make_pairs (lọc độ giống giọng ≥ 0,5) → train → export → eval_tts
→ configs/indextts25_vi.yaml
```

- **Tham số train:** 197,1M / 843,7M (23,4%). Gồm LoRA, embedding văn bản, hai head và bảng ngôn ngữ (log `Tham số train` trong `logs/run1.log`).
- **Bố cục chuỗi đầu vào GPT:** `[cond×3][start_text, <|vi|>, token…, stop_text][start_mel, code…, stop_mel]`.
- **Bất biến có test kiểm chứng** (`tests/test_indextts25.py`):
  - logit lúc train trùng đường suy luận chính thức, sai khác < 1e-4;
  - đệm batch không làm đổi loss;
  - gộp LoRA cho cùng kết quả với chưa gộp;
  - chạy tiếp từ checkpoint cho cùng kết quả với chạy liền một mạch;
  - model sau export nạp bằng `load_checkpoint` cho cùng logit.

## 3.4 Ví dụ xuyên suốt chương

**[CHƯA CÓ]**: cần số thật của một câu trong *Tears of Steel*, lấy sau lần chạy pipeline GPU đầu tiên. Khung đã có ở mục 2 của dàn ý chương 3.

## 3.5 Bảy điểm lệch giữa plan và code cần chốt trước khi vẽ

Xem mục 0 của dàn ý chương 3. Tình trạng 07/10:

| Điểm | Tình trạng |
| --- | --- |
| Tốc độ nói | Đã có số đo 3,98 âm tiết/s (bản thống kê mới nhất ghi 4,0; p10–p90 = 2,92–4,98). **Chưa sửa** `configs/default.yaml` (vẫn là 5,0) |
| React | **Đã làm** (08/10): giao diện mới ở `web/` (React + Vite + Tailwind + wavesurfer.js). Viết Chương 3 theo giao diện này |
| SQLite / xác thực | **Đã làm** (08/10): SQLite (`server/db.py`) giữ người dùng, phiên, quyền sở hữu job, nhật ký, cài đặt. `project.json` vẫn là nguồn dữ liệu duy nhất của từng clip (AD2 giữ nguyên). Cần thêm tác nhân "Quản trị viên", các use case đăng nhập/quản trị và một quyết định kiến trúc về bảo mật |
| Gộp người nói / trang MOS / huỷ job | Chưa chốt |
