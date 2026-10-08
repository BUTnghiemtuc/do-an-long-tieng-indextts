# Việc còn thiếu để đủ nội dung quyển đồ án

Tình trạng ngày 08/10/2026. Xếp theo thứ tự nên làm. Đánh dấu `[x]` khi xong và cập nhật số liệu vào file chương tương ứng.

## Thí nghiệm và số liệu

- [x] Đọc kết quả Run 3 thử nghiệm 2 (p = 1,0): EMO_MATCH 0,721, ES 0,779, CER không đổi → đã chạy Run 3 đầy đủ.
- [ ] **Đọc kết quả Run 3 đầy đủ** (tmux `run3`, xong khoảng 21:30 ngày 08/10; tự chấm, ghi `results/tts/report_run3.md`). Điền vào [06](06-thuc-nghiem.md) mục 6.2 và 6.4; chọn model chính giữa Run 2 và Run 3.
- [ ] **Nghe 20 mẫu** của Run 2 bước 28k: tiêu chí thứ 3 của gate. Ghi lại các lỗi thanh điệu nghe được.
- [ ] **Chạy pipeline thật lần đầu** trên clip *Tears of Steel*. Lần chạy này cho:
  - ví dụ xuyên suốt Chương 3;
  - ảnh chụp màn hình Chương 5;
  - RTF và VRAM thật (NFR-01, NFR-02).
- [x] Sửa `translate.vi_syllables_per_sec` từ 5,0 thành 4,0 trong `configs/default.yaml`.
- [x] Bước dịch chuyển sang Gemini 2.5 Flash qua OpenRouter (08/10); key trong `.env` (đã gitignore). Ghi lý do chọn model (chi phí, tốc độ: ~2 s/cảnh 3 câu) vào Chương 3/5.
- [ ] **Baseline F5-TTS-Vietnamese** trên test zero-shot (`configs/f5_vi.yaml`).
- [ ] Bộ lồng tiếng: 15–20 clip, khoảng 300 câu → `eval_dubbing` (sai số thời lượng, nhất quán giọng, COMET-kiwi, CSV chấm tay 50 câu).
- [ ] Ablation: mẫu cảm xúc là câu gốc so với giọng mẫu; dịch theo ngữ cảnh so với dịch từng câu; có và không có co giãn thời gian.
- [ ] Chạy lặp 2–3 seed cho các hệ thống chính, để báo cáo trung bình ± độ lệch.
- [ ] (Nên có) Bộ test theo nhóm lỗi: số và ngày tháng, tên riêng, câu hỏi, từ mượn, cặp chỉ khác thanh.
- [ ] Kiểm lại số giờ của đợt tải thứ 2 (viVoice và PhoAudiobook) bằng `data_prep.stats` (xem [04](04-finetune-indextts.md) mục 4.2).
- [ ] **Trang MOS** và khảo sát với 10–15 người (gửi từ 12/11).

## Hình và bảng

- [ ] Vẽ hình từ `so-lieu/`:
  - đường loss Run 2;
  - dev loss Run 1 ở 2 mức LR;
  - CER theo checkpoint, có dải nhiễu;
  - phễu lọc dữ liệu;
  - phân bố độ dài câu;
  - cột ES / EMO_MATCH theo cảm xúc.
- [ ] Sơ đồ kiến trúc IndexTTS 2.5, tô màu phần được train và phần đóng băng (draw.io).
- [ ] UML cho Chương 3 bằng PlantUML (`docs/diagrams/`), theo danh sách hình trong [dàn ý chương 3](../docs/ke-hoach-chuong-3-thiet-ke-he-thong.md).
- [ ] Phổ đồ (spectrogram) so sánh model gốc với bản finetune trên cùng câu (`am-thanh-mau/overfit/`).

## Viết

- [ ] Chốt 7 điểm lệch giữa plan và code (dàn ý Chương 3, mục 0). Ngày 08/10 đã xong: React, SQLite, xác thực. Còn lại: gộp người nói, trang MOS, huỷ job.
- [ ] Chương 3: thêm tác nhân "Quản trị viên", use case đăng nhập/đăng ký/quản trị, ERD 5 bảng SQLite (`server/db.py`), quyết định kiến trúc về bảo mật (xem [05](05-trien-khai.md) mục 5.4).
- [ ] Điền đủ tài liệu tham khảo ([tai-lieu-tham-khao.md](tai-lieu-tham-khao.md), các mục "[cần bổ sung]").
- [ ] Model card cho checkpoint.
- [ ] Sửa README và hướng dẫn GPU: số test là 39 chứ không còn 36.
- [ ] Commit các thay đổi đang chưa commit: `make_pairs.py`, `esd_emotion_set.py`, `test_prompts.py`, các sửa trong `eval/` và `training/`. Kết quả trong báo cáo phải tái lập được từ một commit cụ thể.
