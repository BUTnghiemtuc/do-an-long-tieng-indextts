# Kế hoạch viết Chương 3: Phân tích và thiết kế hệ thống

Lập ngày 06/10/2026. Hạn chương: 04/11/2026 (theo [kế hoạch 8 tuần](https://claude.ai/code/artifact/4d983aba-1013-4f99-850e-6a397bf85737)).

Plan này bám đúng hệ thống đang có trong repo, để mọi hình vẽ trong chương đều khớp với code. Khi hội đồng mở code ra hỏi, chỗ nào cũng chỉ được vào hàm hoặc lớp tương ứng.

**Quy mô dự kiến:** 35–45 trang, khoảng 30 hình, 25 bảng, 5–6 thuật toán viết dạng giả mã. Nếu vượt số trang, chuyển từ điển dữ liệu và đặc tả use case phụ sang phụ lục.

**Ranh giới với các chương khác:**

- Chương 2 trình bày lý thuyết (TTS, IndexTTS2/2.5, diarization, isochrony).
- Chương 3 trình bày *hệ thống được thiết kế thế nào và vì sao*.
- Chương 4 trình bày số liệu finetune.
- Chương 5 trình bày ảnh chụp màn hình và cài đặt.
- Chương 6 trình bày kết quả đo.

---

## 0. Cần chốt trước khi vẽ: plan cũ và code đang lệch nhau ở 7 điểm

| Điểm lệch | Plan 8 tuần | Code hiện tại | Đề xuất |
|---|---|---|---|
| Lưu metadata job | SQLite | `status.json` theo từng thư mục job | Viết theo code, giải thích lý do ở bảng quyết định kiến trúc |
| Frontend | React + Vite + wavesurfer | HTML/JS thuần ([index.html](../server/static/index.html)) | Không nâng cấp trước 4/11 thì viết theo code. Nếu có nâng cấp thì wireframe là thiết kế đích |
| Gộp người nói | Có trong bảng rủi ro | Chỉ đổi được người nói của từng câu | Thêm API gộp, hoặc bỏ khỏi use case |
| Trang chấm MOS | "Một trang trong website" | Chưa có | Quyết định sớm. Nếu làm thì thêm tác nhân "Người nghe đánh giá", use case và dữ liệu kết quả |
| Tốc độ nói | `vi_syllables_per_sec: 5.0` ([default.yaml](../configs/default.yaml)) | [data_stats.md](data_stats.md): trung vị **3,98** âm tiết/s | Cập nhật config trước khi chạy thật. Công thức ngân sách âm tiết trong báo cáo dùng giá trị đo được |
| Huỷ job | — | Không có | Ghi vào hạn chế, hoặc thêm vào code |
| Xác thực người dùng | — | Không có | Ghi rõ phạm vi: demo trên một máy |

Nguyên tắc chung: **thiết kế mô tả đúng hệ thống sẽ nộp**. Không vẽ những thứ code không có.

---

## 1. Dàn ý chi tiết

### 3.1 Phân tích yêu cầu (8–10 trang)

**3.1.1 Bài toán và phạm vi**

- Đầu vào: clip 1–5 phút, thoại tiếng Anh. Đầu ra: MP4 lồng tiếng Việt và SRT.
- Giả định: thoại rõ, ít chồng tiếng.
- Ngoài phạm vi: lip-sync, real-time, phim dài.
- Hình 3.1: sơ đồ hộp đen đầu vào → đầu ra.

**3.1.2 Tác nhân** (Bảng 3.1)

- Người dùng biên tập (dùng website).
- Nhà phát triển mô hình (dùng CLI).
- Hệ thống ngoài: Claude API (dịch), HuggingFace Hub (tải model; pyannote là model gated).
- Người nghe đánh giá, nếu làm trang MOS.

**3.1.3 Yêu cầu chức năng** (Bảng 3.2, cột: mã, mô tả, ưu tiên MoSCoW, trạng thái)

| Mã | Mô tả |
|---|---|
| FR-01 | Tải clip lên, kèm SRT nếu có, chọn ngôn ngữ nguồn |
| FR-02 | Lồng tiếng tự động end-to-end qua 8 bước |
| FR-03 | Theo dõi tiến độ theo từng bước |
| FR-04 | Đổi tên nhân vật, ghi chú xưng hô |
| FR-05 | Đổi giọng mẫu sang một câu khác |
| FR-06 | Sửa bản dịch hoặc người nói của một câu. Câu sửa tay bị khoá (`vi_locked`) |
| FR-07 | Tạo lại một câu |
| FR-08 | Áp dụng thay đổi |
| FR-09 | Chạy lại từ một bước, có tuỳ chọn `force` |
| FR-10 | So sánh bản gốc với bản lồng tiếng, nghe từng câu |
| FR-11 | Tải MP4 và SRT |
| FR-12 | Cảnh báo câu lệch thời lượng, câu dịch dài, lỗi TTS |
| FR-13 | Xem danh sách job |
| FR-14 | CLI `run`, `regen`, `show`, `rtf` |
| FR-15 | Báo cáo RTF từng bước |
| FR-16 | Chuẩn bị dữ liệu: import, lọc, chia tập, thống kê |
| FR-17 | Trích đặc trưng và ghép cặp giọng mẫu/câu đích |
| FR-18 | Finetune LoRA, chạy tiếp được từ checkpoint |
| FR-19 | Export checkpoint nạp thẳng vào IndexTTS |
| FR-20 | Đánh giá tầng TTS và tầng lồng tiếng |

**3.1.4 Yêu cầu phi chức năng** (Bảng 3.3). Mỗi dòng cần chỉ tiêu đo được và cách kiểm chứng, trỏ sang Chương 6.

| Mã | Nhóm | Chỉ tiêu | Kiểm chứng |
|---|---|---|---|
| NFR-01 | Hiệu năng | RTF toàn pipeline, thời gian tạo lại 1 câu. Chốt con số sau lần đo đầu trên RTX 5070 Ti | `vidub rtf` |
| NFR-02 | Tài nguyên | Chạy trên 1 GPU 16 GB, model nạp một lần mỗi worker | Log VRAM đỉnh |
| NFR-03 | Chất lượng | ≥ 90% câu lệch thời lượng dưới 10%; CER ≤ 5% | `eval_dubbing`, `eval_tts` |
| NFR-04 | Tin cậy | Một câu lỗi không làm hỏng cả clip; ghi file nguyên tử; job lỗi lưu traceback | `test_pipeline` |
| NFR-05 | Tái lập | Cấu hình YAML + `--set`, seed, cache theo hash | — |
| NFR-06 | Khả chuyển | Đường dẫn tương đối, chép được cả thư mục dự án; có Docker | — |
| NFR-07 | Mở rộng | Thêm backend mà không sửa các bước | `CommandTTS` + F5 |
| NFR-08 | Kiểm thử được | Toàn bộ pipeline chạy trên CPU bằng backend giả lập | `pytest` |
| NFR-09 | An toàn, đạo đức | Chống path traversal, khoá API qua biến môi trường, nhãn "giọng do AI tạo" | `test_server` |
| NFR-10 | Khả dụng | Giao diện tiếng Việt, tiến độ cập nhật mỗi ≤ 1 s | SSE |

**3.1.5 Biểu đồ use case**

- Hình 3.2: use case tổng quát.
- Hình 3.3: gói Quản lý job (tạo job, xem danh sách, theo dõi tiến độ, chạy lại từ bước, tải kết quả).
- Hình 3.4: gói Biên tập (sửa nhân vật, sửa câu, bỏ khoá câu, tạo lại câu, áp dụng thay đổi, so sánh).
- Hình 3.5: gói Mô hình qua CLI.
- Dùng `<<include>>` và `<<extend>>` cho đúng. Ví dụ: "Theo dõi tiến độ" extend "Tạo job".

**3.1.6 Đặc tả use case** (Bảng 3.4–3.9)

- Đặc tả 6 use case chính: UC01 Tạo job, UC02 Theo dõi tiến độ, UC03 Sửa bản dịch và tạo lại câu, UC04 Cập nhật nhân vật, UC05 Áp dụng thay đổi, UC06 Tải kết quả.
- Mẫu bảng gồm: mã, tên, tác nhân, tiền điều kiện, hậu điều kiện, luồng chính, luồng thay thế, ngoại lệ, FR liên quan.
- Phần ngoại lệ lấy đúng từ code, ví dụ cho UC03:
  - 409 khi job đang chạy.
  - 404 khi không có câu.
  - 400 khi người nói không tồn tại.
  - Khi TTS lỗi: `status=error` và câu được gắn cảnh báo, các câu khác vẫn chạy tiếp.

### 3.2 Thiết kế kiến trúc tổng thể (6–8 trang)

**3.2.1 Quyết định kiến trúc** (Bảng 3.10, kiểu ADR: quyết định, phương án đã cân nhắc, lý do chọn, đánh đổi). Đây là phần ghi điểm nhất của chương.

- **AD1** Pipeline 8 bước theo giao thức `Step` (kiểu Pipes & Filters), thay vì mô hình S2ST end-to-end. Lý do: sửa được từng câu, thay được từng mô-đun.
- **AD2** `project.json` là nguồn dữ liệu duy nhất (kiểu Shared Repository), thay vì CSDL quan hệ.
- **AD3** Cache hai tầng theo hash nội dung.
- **AD4** Backend thay được qua cấu hình (Strategy + Factory): bản giả lập cho CPU, bản thật cho GPU.
- **AD5** Tách API khỏi worker GPU bằng Redis + RQ; không có Redis thì dùng ThreadPool. Chỉ 1 job chạy một lúc vì chỉ có 1 GPU.
- **AD6** Báo tiến độ bằng `status.json` + SSE, thay vì WebSocket hoặc polling.
- **AD7** Con người tham gia vòng xử lý: câu sửa tay không bao giờ bị LLM dịch đè.
- **AD8** Chỉ finetune khối GPT (T2S) bằng LoRA, đóng băng các khối còn lại.

**3.2.2 Sơ đồ C4**

- Hình 3.6: mức Context.
- Hình 3.7: mức Container (Browser, FastAPI, Redis, RQ Worker GPU, kho file `data/jobs`, checkpoints, CLI).

**3.2.3 Biểu đồ gói** (Hình 3.8)

- Các gói: `vidub` (core, steps, backends), `server`, `data_prep`, `training`, `eval`, và quan hệ phụ thuộc giữa chúng.
- Nhấn mạnh: `vidub.backends.tts` và `training` dùng chung `data_prep.vi_normalize.tts_frontend`. Đây là bất biến "front-end văn bản giống hệt nhau lúc train và lúc suy luận".

**3.2.4 Mẫu thiết kế áp dụng** (Bảng 3.11)

| Mẫu | Chỗ dùng trong code |
|---|---|
| Pipes & Filters | `STEPS` |
| Repository | `Project` |
| Strategy | `TTSBackend`, `Translator` |
| Factory + cache | `get_tts` (dùng `lru_cache`), `get_translator` |
| Template | `BaseStep` |
| Producer–Consumer | `enqueue` / `run_job` |
| Observer | callback `progress` → `status.json` → SSE |
| Adapter | `IndexTTSBackend` lọc tham số bằng `inspect`; `CommandTTS` bọc lệnh CLI |

### 3.3 Thiết kế phân hệ lồng tiếng (10–12 trang, phần trọng tâm)

**3.3.1 Luồng dữ liệu**

- Hình 3.9: DFD theo chuỗi video → `original.wav` → `vocals`/`background` → `turns` → `segments` → `vi_text` → `tts_natural` → `tts_final` → `dub_mix` → MP4/SRT.
- Bảng 3.12, mỗi dòng một bước, các cột: đầu vào, đầu ra (file và trường JSON), công cụ, backend chạy CPU, loại cache, khoá cấu hình.

**3.3.2 Bộ điều phối và cache**

- Hình 3.10: biểu đồ lớp gồm `Step`, `BaseStep`, 8 bước, `Context`, `Project`.
- Hình 3.11: biểu đồ hoạt động của `run_pipeline`.
- Thuật toán 3.1: `h = SHA1(fingerprint, cfg[bước])[:16]`. Bước được bỏ qua khi `h` trùng với lần chạy trước và file đầu ra còn trên đĩa.
- Bảng 3.13: các khoá cache theo câu và cách thay đổi lan truyền.
  - `src_key = H(src_text, speaker, dur, backend, model)`
  - `tts_key = H(vi_text, sig(timbre), style_prompt, backend_signature)`
  - `align_key = H(tts_key, start, end, window_end, cfg)`
  - Chuỗi lan truyền: sửa `vi_text` thì `tts_key` đổi, kéo theo `align_key` đổi. Đổi ghi chú nhân vật thì `src_key = None`, nên câu được dịch lại. Khi nhận dạng lại, `carry_over` giữ kết quả cũ của câu trùng nội dung và lệch thời điểm dưới 0,3 s.

**3.3.3 Thuật toán.** Mỗi thuật toán gồm công thức, giả mã ≤ 15 dòng và bảng tham số.

- **3.2 Gán người nói và cắt câu.**
  - `speaker_for` chọn người nói có thời gian chồng lấn lớn nhất.
  - Luôn ngắt câu khi đổi người nói.
  - Ngắt tại dấu câu, hoặc khi khoảng lặng ≥ 0,6 s.
  - Câu dài hơn 12 s thì chia đôi tại khoảng lặng lớn nhất bên trong.
- **3.3 Dịch theo cảnh có ngân sách âm tiết.**
  - Ngân sách: `N = max(1, round(d·r))`, với r = 3,98.
  - Tách cảnh khi khoảng lặng > 2 s, mỗi cảnh tối đa 25 câu.
  - Rút gọn tối đa 2 vòng khi `n > N·(1+0,15)`.
  - Hình 3.12: biểu đồ trình tự gọi Claude API.
  - Bảng thiết kế prompt: luật xưng hô, đầu ra theo JSON schema, câu `todo=false` dùng làm ngữ cảnh, xử lý khi gặp `refusal` hoặc `max_tokens`.
- **3.4 Chọn giọng mẫu.**
  - Điểm = `−10·overlap − |dur − 6,5|/6,5 − 2·[dur < 3]`.
  - Không có câu đủ dài thì nối các câu liền kề của cùng người nói, cách nhau dưới 1 s.
  - Style prompt là chính câu gốc, cắt rộng thêm ±50 ms.
- **3.5 Căn thời lượng.** Hình 3.13 là lưu đồ. Thứ tự xử lý:
  1. `factor = clip(d/d_nat, 0,75, 1,25)`.
  2. Co giãn `rate = clip(d_cur/d, 0,9, 1,1)` bằng rubberband, giữ formant.
  3. Mượn khoảng lặng phía sau, tới `W = min(end + 0,6; next.start − 0,08; duration)`.
  4. Vẫn dài hơn thì cắt đuôi, fade 80 ms và gắn cảnh báo.
- **3.6 Trộn âm.**
  - Chuẩn hoá −20 LUFS. Câu ngắn hơn 400 ms thì dùng RMS + 3 dB thay thế.
  - Ducking nhạc nền (tuỳ chọn), giới hạn đỉnh 0,98.
  - Ghép video bằng `ffmpeg -c:v copy`.

**3.3.4 Biểu đồ trạng thái câu thoại** (Hình 3.14)

- Trạng thái: `new` → `translated` → `synthesized` → `done`, cộng thêm `error`.
- Ghi rõ sự kiện gây chuyển trạng thái: sửa tay, tạo lại, lỗi TTS.

**3.3.5 Hợp đồng backend** (Hình 3.15)

- `TTSBackend.synthesize(text, timbre, style, out, duration_factor)` và cờ `supports_duration`; ba bản cài đặt `Mock`, `IndexTTS`, `Command`.
- `Translator`: `translate_scene`, `shorten`.

### 3.4 Thiết kế dữ liệu (5–6 trang)

Hội đồng PTIT thường hỏi về CSDL, nên phần này phải có cả mô hình khái niệm lẫn lý do không dùng RDBMS.

- **3.4.1 ERD khái niệm** (Hình 3.16). Job 1–1 Project. Project 1–n Speaker, Segment, Turn, StepRecord. Segment n–1 Speaker. Segment 1–n Word.
- **3.4.2 Mô hình lưu trữ vật lý dạng tài liệu JSON.**
  - Hình 3.17: biểu đồ lớp các model Pydantic trong [project.py](../vidub/project.py).
  - Bảng 3.14–3.16: từ điển dữ liệu với các cột trường, kiểu, ràng buộc, ý nghĩa, **bước nào ghi**.
- **3.4.3 Ma trận CRUD giữa bước và trường** (Bảng 3.17). Ít đồ án có bảng này. Nó cho thấy bước nào sở hữu dữ liệu nào.
- **3.4.4 Tổ chức thư mục job** (Hình 3.18): `status.json`, `input/`, `project/{project.json, audio/, prompts/, tts/, output/}`.
  - Bảng 3.18: các trường của `status.json`.
  - Hình 3.19: máy trạng thái job `created` → `queued` → `running` → `done`/`error`. Từ `done`/`error` quay lại `queued` khi render, rerun hoặc regenerate.
- **3.4.5 Toàn vẹn dữ liệu.**
  - Ghi nguyên tử: ghi file tạm rồi `os.replace`.
  - Chặn sửa khi job đang chạy (trả 409).
  - Có số hiệu phiên bản schema và đường dẫn tương đối.
- **3.4.6 Dữ liệu huấn luyện** (Bảng 3.19): manifest JSONL, `feats_*.pt` (`text_ids`, `codes`, `spk[192]`, `emo`), `pairs_*.jsonl`.
- **3.4.7 So sánh JSON với RDBMS.** Nêu hướng mở rộng sang SQLite/Postgres khi cần nhiều người dùng.

### 3.5 Thiết kế API và xử lý bất đồng bộ (4–5 trang)

- Bảng 3.20 liệt kê **12 endpoint** trong [app.py](../server/app.py), cột: method, path, đầu vào, đầu ra, mã lỗi, UC tương ứng.
- Biểu đồ trình tự:
  - Hình 3.20: tạo job → `enqueue` → worker → SSE.
  - Hình 3.21: PATCH câu → regenerate, chạy lại `synthesize`, `align`, `mix`.
  - Hình 3.22: đổi ghi chú nhân vật → render → dịch lại.
- Hình 3.23: biểu đồ lớp phân tích BCE (Boundary–Control–Entity) cho UC03. Môn PTTKHT ở PTIT dạy kiểu này nên hội đồng quen.
- Thiết kế hàng đợi:
  - Hai chế độ: Redis + RQ, hoặc ThreadPool một luồng.
  - Timeout job 6 giờ.
  - Ghi tiến độ thưa nhất 0,5 s một lần.
  - SSE kiểm tra mỗi 1 s.
  - Mỗi tiến trình worker nạp model một lần.
- Bảng 3.21: mã lỗi và ý nghĩa.

### 3.6 Thiết kế giao diện (3–4 trang)

- Hình 3.24: bố cục trang.
- Hình 3.25–3.28: wireframe cho tải lên + danh sách job, tiến độ + so sánh hai video, bảng nhân vật, bảng câu thoại.
- Bảng 3.22: thành phần UI ↔ API ↔ UC.
- Nguyên tắc: nút bị vô hiệu khi job đang chạy, cờ cảnh báo có màu, dòng nhãn AI luôn hiển thị.
- Ảnh chụp màn hình thật để ở Chương 5.

### 3.7 Thiết kế phân hệ dữ liệu và huấn luyện, mức kiến trúc (4–5 trang)

- Hình 3.29: DFD `import_hf` → `filter` (5 stage) → `split` → `stats` → `prepare_features` → `make_pairs` → `train` → `export` → `eval` → `configs/indextts25_vi.yaml`.
- Hình 3.30: kiến trúc IndexTTS 2.5, tô màu phần **train** (LoRA trong GPT, text embedding, hai head, hàng ngôn ngữ `vi`) và phần **đóng băng** (w2v-BERT, codec, CAMPPlus, S2M, BigVGAN).
- Hình 3.31: bố cục chuỗi đầu vào GPT `[cond×3][start_text, <|vi|>, token…, stop_text][start_mel, code…, stop_mel]`.
- Hình 3.32: biểu đồ lớp `TrainSetup`, `LoRAConv1D`, `PairDataset`, `BucketBatchSampler`, `Batch`.
- Bảng 3.23: thành phần được train. LoRA r=64, α=128, gắn vào 4 vị trí × 24 lớp. Hàng `vi` khởi tạo từ `en`, LR gấp 5. Loss = 0,2·CE_text + CE_mel.
- Bất biến đã có test kiểm tra: logit lúc train trùng logit lúc suy luận; model sau khi gộp LoRA cho kết quả bằng model chưa gộp.
- Đường loss và CER để sang Chương 4.

### 3.8 Thiết kế triển khai (2 trang)

- Hình 3.33: biểu đồ triển khai.
  - Máy GPU RTX 5070 Ti 16 GB chạy Docker Compose gồm `redis`, `api:8000`, `worker` (được cấp GPU).
  - Volume: `data`, `checkpoints`, `.cache`. Khoá API nằm trong `.env`.
  - Bên ngoài: Claude API, HF Hub.
- Chế độ phát triển: CPU, `mock.yaml`, không cần Redis.
- Bảng 3.24: 5 file cấu hình (`default`, `gpu`, `mock`, `indextts25_vi`, `f5_vi`) và trường hợp dùng từng file.

### 3.9 An toàn, bảo mật và đạo đức (1–2 trang)

Bảng 3.25: rủi ro và biện pháp.

- `job_dir` kiểm tra thư mục cha để id job không thoát ra ngoài.
- `get_file` kiểm tra `is_relative_to` để chống path traversal.
- Khoá API đọc từ biến môi trường.
- Hiển thị nhãn "giọng do AI tạo".
- Demo công khai chỉ dùng clip Creative Commons.
- Chưa có xác thực người dùng: nêu là giới hạn của phạm vi demo.

### 3.10 Thiết kế kiểm thử và ma trận truy vết (2 trang)

- Chiến lược kiểm thử:
  - Unit: text, SRT, chuẩn hoá số, công thức căn thời lượng.
  - Tích hợp: pipeline với backend giả lập, cache.
  - API: `test_server`.
  - Bất biến mô hình: `test_indextts25`.
- Bảng 3.26: ma trận truy vết **FR → UC → mô-đun → API → file test**. Bảng này nối Chương 3 với Chương 5 và 6.

### 3.11 Tiểu kết

Tóm tắt thiết kế và dẫn sang Chương 4.

---

## 2. Một ví dụ đi xuyên suốt chương

Chọn **một câu thoại thật** (ví dụ trong *Tears of Steel*) và in trạng thái JSON của nó sau mỗi bước. Mọi phần của chương nhắc lại câu này, nên người đọc thấy rõ dữ liệu biến đổi qua từng bước. Số dưới đây chỉ để minh hoạ; thay bằng số thật sau lần chạy GPU đầu tiên:

> d = 2,40 s → N = round(2,40 × 3,98) = 10 âm tiết → bản dịch 11 âm tiết (≤ 11,5, đạt) → TTS tự nhiên 2,90 s (tỉ lệ 1,21) → `duration_factor` = 0,83 → 2,55 s → co giãn 1,0625 → 2,40 s, `status=done`, `duration_ratio` = 1,00.

---

## 3. Những điểm giúp chương vào nhóm đồ án tốt

1. **Thiết kế khớp code 1:1**: tên lớp, tên hàm, tên trường trong hình phải trùng với code.
2. **Mỗi quyết định có phương án thay thế và lý do** (bảng ADR 3.10).
3. **Thuật toán tự thiết kế có công thức, giả mã và ví dụ số.** Đây là đóng góp kỹ thuật bên cạnh phần finetune.
4. **Có ví dụ đi xuyên suốt** (mục 2).
5. **Có ma trận CRUD và ma trận truy vết.**
6. **NFR đo được**, và Chương 6 đo lại đúng các NFR đó.
7. **Đủ bộ UML mà hội đồng hay kiểm**: use case + đặc tả, hoạt động, trình tự, lớp (BCE và thiết kế), trạng thái, ERD, gói, triển khai.
8. **Không dán code dài.** Giả mã tối đa 15 dòng; code đầy đủ để phụ lục.

## 4. Công cụ và quy ước

- **UML:** PlantUML, lưu nguồn ở `docs/diagrams/*.puml` trong repo, xuất SVG để chèn vào Word.
- **Sơ đồ C4 và kiến trúc IndexTTS:** draw.io.
- **Wireframe:** Excalidraw.
- **Đánh số:** Hình 3.x có chú thích dưới hình, Bảng 3.x có chú thích trên bảng. Font Times New Roman giống thân bài.
- **Bảng thuật ngữ Anh–Việt** dùng thống nhất cả báo cáo: timbre prompt = giọng mẫu, style prompt = mẫu cảm xúc, diarization = phân đoạn người nói, isochrony = khớp thời lượng.

## 5. Lịch thực hiện (từ 6/10, hạn chương 4/11)

Các mục 3.1–3.6 chỉ cần code đã có, nên viết được xen kẽ trong lúc GPU đang lọc dữ liệu hoặc train. Chỉ mục 3.7 và các con số NFR phải chờ gate 28/10.

| Thời gian | Việc | Phụ thuộc |
|---|---|---|
| 6–12/10 | Chốt 7 điểm lệch ở mục 0; viết 3.1 (FR, NFR, use case, đặc tả 6 UC) | — |
| 13–19/10 | Vẽ UML từ code (lớp, trạng thái, hoạt động, 3 biểu đồ trình tự); viết 3.2–3.3 | — |
| 20–26/10 | Viết 3.4 (ERD, từ điển dữ liệu, CRUD), 3.5 (API), 3.6 (wireframe), 3.8–3.9 | — |
| 27/10–1/11 | Viết 3.7 và chốt model dùng trong pipeline; điền số đo thật cho NFR và ví dụ xuyên suốt | Gate 28/10, pipeline v1 ngày 1/11 |
| 2–4/11 | Viết 3.10–3.11, rà soát hình với code, gửi GVHD | — |

## 6. Checklist nghiệm thu chương

- [ ] Mọi FR có trong ma trận truy vết; mọi NFR có cách đo.
- [ ] 6 đặc tả use case có luồng ngoại lệ lấy từ mã lỗi thật.
- [ ] Mọi lớp và trường trong hình đều có trong code; `grep` thử 10 tên ngẫu nhiên.
- [ ] Mọi tham số trong công thức trùng với `configs/default.yaml`.
- [ ] Ví dụ xuyên suốt dùng số chạy thật.
- [ ] Nguồn PlantUML đã commit; hình đọc rõ khi in đen trắng.
- [ ] Không còn chỗ mô tả tính năng chưa làm (SQLite, React, gộp người nói, MOS) nếu chưa làm thật.
