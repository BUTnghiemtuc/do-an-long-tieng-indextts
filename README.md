# vidub — lồng tiếng phim tự động sang tiếng Việt với IndexTTS

Mã nguồn đồ án theo [kế hoạch 8 tuần](https://claude.ai/code/artifact/4d983aba-1013-4f99-850e-6a397bf85737).
Đầu vào là clip phim 1–5 phút, thoại tiếng Anh. Đầu ra là video lồng tiếng Việt: mỗi nhân vật giữ giọng gốc, thời lượng khớp, nhạc nền giữ nguyên, kèm phụ đề SRT.

## Pipeline

Mỗi clip có một thư mục dự án chứa `project.json`. Cả 8 bước đọc và ghi file này:

| # | Bước | Công cụ | Backend thử nghiệm (không cần GPU) |
| --- | --- | --- | --- |
| 1 | `extract` tách audio | ffmpeg | — |
| 2 | `separate` giọng ↔ nhạc nền | Demucs htdemucs | `none` |
| 3 | `diarize` ai nói khi nào | pyannote 3.1 | `single` (VAD năng lượng) |
| 4 | `transcribe` lời thoại + cắt câu | WhisperX large-v3 | `srt` (phụ đề gốc cạnh video) |
| 5 | `translate` dịch theo cảnh, ràng buộc số âm tiết | Claude (`claude-opus-5-5`) | `copy` |
| 6 | `synthesize` sinh giọng (timbre = nhân vật, style = câu gốc) | IndexTTS2 / 2.5 / bản finetune | `mock` |
| 7 | `align` căn thời lượng | duration_factor → co giãn ±10% → mượn khoảng lặng | — |
| 8 | `mix` loudness, trộn M&E, ghép video, SRT | pyloudnorm, ffmpeg | — |

Cache có hai tầng:

- Bước 1–4 bỏ qua nếu đầu vào và cấu hình không đổi.
- Bước 5–7 có key riêng cho từng câu. Sửa một câu trên web thì chỉ câu đó được dịch hoặc sinh lại.
- Câu đã sửa tay (`vi_locked`) không bao giờ bị LLM dịch đè.

## Cài đặt

```bash
conda create -n vidub python=3.11 && conda activate vidub
pip install -e ".[server,dev]"           # đủ để chạy thử toàn bộ với backend giả lập
pytest                                    # 36 test, chạy trên CPU (test finetune cần third_party/index-tts)

# Máy GPU NVIDIA:
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -e ".[gpu,llm,server,eval]"
git clone https://github.com/index-tts/index-tts && pip install -e index-tts
export ANTHROPIC_API_KEY=...  HF_TOKEN=...   # HF: chấp nhận điều khoản pyannote/speaker-diarization-3.1
```

## Dùng

```bash
# Chạy thật (GPU)
vidub run clip.mp4 -c configs/gpu.yaml                 # -> runs/clip/output/clip.vi.mp4 + .srt
vidub show runs/clip                                   # bảng câu thoại, tỉ lệ thời lượng, cảnh báo
vidub regen runs/clip --segment 12 --text "Anh chưa bao giờ nghe em cả."
vidub run runs/clip --from translate                   # chạy lại từ một bước
vidub rtf runs/clip                                    # thời gian từng bước, RTF

# Chạy thử không GPU / API key (cần clip.srt cạnh clip.mp4)
vidub run clip.mp4 -c configs/mock.yaml

# Ghi đè cấu hình từng khoá
vidub run clip.mp4 -c configs/gpu.yaml --set align.max_stretch=0.15 --set translate.effort=high
```

### Website

```bash
VIDUB_CONFIG=configs/mock.yaml uvicorn server.app:app --reload   # http://localhost:8000
docker compose up --build                                         # bản GPU: api + worker + redis
```

Website cho phép:

- tải clip lên (kèm phụ đề nếu có) và theo dõi tiến độ từng bước qua SSE;
- đổi tên nhân vật và ghi chú xưng hô;
- đổi giọng mẫu sang câu khác;
- sửa bản dịch, "tạo lại câu này";
- so sánh gốc ↔ lồng tiếng cạnh nhau, tải MP4 và SRT.

Không có `REDIS_URL` thì job chạy trong luồng nền của API. Như vậy là đủ cho buổi demo trên một máy.

Giao diện hiện là một trang HTML/JS thuần ([server/static/index.html](server/static/index.html)) dùng chung API. Có thể thay bằng React + wavesurfer.js sau mà không phải sửa backend.

## Theo giai đoạn của kế hoạch

| Giai đoạn | Thư mục | Lệnh chính |
| --- | --- | --- |
| 1. Dữ liệu (đến 14/10) | [data_prep/](data_prep/) | `import_hf` → `filter` (duration, normalize, asr, quality, select) → `split` → `stats` |
| 2. Finetune IndexTTS 2.5 (đến 28/10) | [training/indextts25/](training/indextts25/) | [runbook](training/README.md): `prepare_features` → `train` → `export` |
| 3. Pipeline (đến 1/11) | [vidub/](vidub/) | `vidub run` |
| 4. Website (đến 13/11) | [server/](server/) | `uvicorn server.app:app` |
| 5. Đánh giá (đến 18/11) | [eval/](eval/) | `eval_tts` (CER/WER, SS, UTMOS, ES, RTF), `eval_dubbing` (sai số thời lượng, nhất quán giọng, COMET-kiwi, CSV chấm tay) |

Ví dụ giai đoạn 1:

```bash
python -m data_prep.import_hf capleaf/viVoice --speaker-col channel --out data/raw/vivoice
python -m data_prep.filter data/raw/vivoice/raw.jsonl data/clean/vivoice.jsonl
python -m data_prep.split data/clean/*.jsonl data/splits --test-speakers 25
python -m data_prep.stats data/splits/train.jsonl --md docs/data_stats.md
```

Tên cột của từng bộ dữ liệu cần kiểm tra lại trên trang HuggingFace.

`stats` in tốc độ nói trung vị (âm tiết/giây). Đặt giá trị này vào `translate.vi_syllables_per_sec` trong [configs/default.yaml](configs/default.yaml).

## Đã kiểm chứng / chưa kiểm chứng

Đã chạy trên CPU (test tự động):

- toàn bộ pipeline với backend giả lập;
- cache và tạo lại từng câu;
- API web: tải lên → sửa → tạo lại;
- bộ chuẩn hoá số tiếng Việt;
- chia tập và thống kê dữ liệu;
- mở rộng tokenizer SentencePiece;
- chỉ số thời lượng.

Các backend thật đã viết theo API công khai nhưng **chưa chạy trên GPU**: Demucs, pyannote, WhisperX, IndexTTS, parakeet, UTMOS, WavLM-SV, emotion2vec, COMET.

Cần chạy thử từng backend ngay khi có máy GPU. `IndexTTSBackend` chỉ truyền những tham số mà `infer()` thật sự có, nên dùng được cho cả IndexTTS2 lẫn 2.5. Riêng tên lớp của 2.5 phải đặt qua `synthesize.indextts.entry`.
