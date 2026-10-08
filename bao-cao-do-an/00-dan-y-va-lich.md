# Dàn ý quyển đồ án và lịch viết

Theo mục 9 của [kế hoạch 8 tuần](https://claude.ai/code/artifact/4d983aba-1013-4f99-850e-6a397bf85737). Hạn nộp: **25/11/2026**.

Viết song song từ tuần 3, không dồn vào tuần cuối. Chương 2 tận dụng bài survey TTS đã đăng trên *Discover Artificial Intelligence*. Các chương còn lại viết ngay khi phần việc tương ứng xong.

| Chương | Nội dung | Viết khi | Xong trước | Tư liệu trong thư mục này | Trạng thái tư liệu |
| --- | --- | --- | --- | --- | --- |
| 1. Giới thiệu | Bài toán, động lực, mục tiêu, phạm vi, đóng góp | Tuần 3 | 21/10 | [01](01-gioi-thieu.md) | Đủ |
| 2. Cơ sở lý thuyết | Các paradigm TTS (từ bài survey), IndexTTS2/2.5, diarization, ASR, MT, isochrony | Tuần 3–4 | 28/10 | [02](02-co-so-ly-thuyet.md) | Đủ khung; cần đối chiếu paper khi trích dẫn |
| 3. Thiết kế hệ thống | Pipeline, dữ liệu JSON, use case website | Tuần 5 | 4/11 | [03](03-thiet-ke-he-thong.md) + [docs/ke-hoach-chuong-3](../docs/ke-hoach-chuong-3-thiet-ke-he-thong.md) | Đủ; ví dụ xuyên suốt chờ lần chạy pipeline thật |
| 4. Finetune IndexTTS tiếng Việt | Dữ liệu, tokenizer, điều kiện ngôn ngữ, cấu hình, đường loss | Tuần 5–6 | 11/11 | [04](04-finetune-indextts.md), `so-lieu/` | Gần đủ; còn thiếu hình |
| 5. Triển khai | Pipeline, website, ảnh chụp màn hình | Tuần 6–7 | 15/11 | [05](05-trien-khai.md) | Thiếu: chạy pipeline thật, ảnh màn hình |
| 6. Thực nghiệm | Bảng kết quả, ablation, MOS, phân tích lỗi | Tuần 7 | 20/11 | [06](06-thuc-nghiem.md) | Có tầng TTS; thiếu tầng lồng tiếng, MOS, ablation |
| 7. Kết luận | Kết quả, hạn chế, hướng phát triển (lip-sync, GRPO, streaming) | Tuần 8 | 22/11 | [07](07-ket-luan.md) | Có khung |

## Các mốc liên quan

| Ngày | Mốc | Tình trạng (07/10) |
| --- | --- | --- |
| 10/10 | Overfit đạt | **Đã đạt** ngày 5/10: CER 6 câu đã train giảm từ 75% xuống 6% |
| 14/10 | Đủ dữ liệu, trích xong đặc trưng | **Đã xong**: 371 giờ, 1.786 người nói |
| 17/10 | Run 1 xong, chọn LR | **Đã xong** ngày 6/10: chọn LR 5e-5 |
| 28/10 | Run 2 xong, gate | Run 2 xong 7/10. Đã đạt 2/3 tiêu chí gate; còn tiêu chí nghe 20 mẫu |
| 1/11 | Pipeline end-to-end v1 | Chưa chạy backend thật trên GPU |
| 7/11 | Website MVP | Đã có bản HTML/JS và API, chạy được với backend giả lập |
| 12/11 | Gửi khảo sát MOS | Chưa có trang MOS |
| 18/11 | Xong toàn bộ số liệu | — |
| 25/11 | Nộp | — |

Phần finetune đi trước kế hoạch khoảng 3 tuần, nên có thể dùng thời gian dư cho pipeline thật, đánh giá tầng lồng tiếng và MOS.

## Quy ước trình bày (theo kế hoạch Chương 3)

- Hình 3.x có chú thích dưới hình. Bảng 3.x có chú thích trên bảng. Font Times New Roman.
- UML vẽ bằng PlantUML, lưu ở `docs/diagrams/*.puml`. C4 và kiến trúc IndexTTS vẽ bằng draw.io. Wireframe vẽ bằng Excalidraw.
- Giả mã không quá 15 dòng; code đầy đủ để ở phụ lục.
- Thuật ngữ dùng thống nhất cả quyển:

| Tiếng Anh | Tiếng Việt |
| --- | --- |
| timbre prompt | giọng mẫu |
| style prompt / emotion prompt | mẫu cảm xúc |
| speaker diarization | phân đoạn người nói |
| isochrony | khớp thời lượng |
| zero-shot | zero-shot (người nói chưa từng nghe) |
| semantic token | token ngữ nghĩa |
| speaker similarity (SS) | độ giống giọng |
| real-time factor (RTF) | hệ số thời gian thực |

## Chuẩn bị bảo vệ (tuần 8)

- Slide khoảng 20 trang: vấn đề → kiến trúc → finetune → demo → kết quả → hạn chế.
- Video demo 2–3 phút quay sẵn, phòng khi mạng hoặc GPU gặp sự cố lúc bảo vệ.
- 3–4 clip trước/sau đã render sẵn, mở được offline.
- Tập dượt ít nhất 2 lần, có bấm giờ.
- Chuẩn bị trả lời các câu hay bị hỏi:
  - vì sao chọn IndexTTS thay vì F5 hay CosyVoice;
  - vì sao không làm lip-sync;
  - đạo đức và đồng ý khi clone giọng;
  - license của dữ liệu và mô hình;
  - giới hạn của UTMOS với tiếng Việt.
