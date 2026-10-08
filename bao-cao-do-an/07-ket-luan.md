# Tư liệu Chương 7: Kết luận và hướng phát triển

Khung này viết theo số liệu ngày 07/10. Viết lại sau khi có số liệu tầng lồng tiếng và MOS.

## 7.1 Kết quả đạt được

- Finetune IndexTTS 2.5 cho tiếng Việt bằng LoRA trên 1 GPU 16 GB:
  - 371 giờ dữ liệu, 1.786 người nói;
  - 11,7 giờ train cho 3 epoch;
  - VRAM đỉnh 7,4 GB.
- Trên 25 người nói chưa từng nghe:
  - CER giảm từ 71,4% xuống 3,1%;
  - SS tăng từ 0,662 lên 0,726, cao hơn bản IndexTTS2-vi cộng đồng (0,678);
  - RTF 0,335, nhanh gấp khoảng 1,9 lần bản cộng đồng.
- Đạt 2/3 tiêu chí gate trước hạn 3 tuần.
- Phát hiện và đo được hiện tượng mất cảm xúc và mất giọng xuyên ngôn ngữ sau finetune. Đã thử một cách khắc phục (Run 3) cho kết quả khả quan.
- Pipeline 8 bước và website biên tập. **[CẦN BỔ SUNG]**: số liệu khi chạy thật.

## 7.2 Hạn chế

- Độ rõ chữ còn kém bản dinhthuan: CER 3,1% so với 1,4%. Câu ngắn khó hơn câu dài, trong khi thoại phim thường ngắn.
- Cảm xúc và độ giống giọng khi câu mẫu là tiếng Anh giảm so với model gốc. Đây là đúng tình huống của lồng tiếng.
- Phép đo có nhiễu (±0,5 điểm CER giữa hai lần chạy cùng cấu hình), và mỗi cấu hình chỉ chấm một seed.
- Chỉ số tự động có giới hạn:
  - UTMOS được train trên tiếng Anh;
  - CER phụ thuộc lỗi của ASR với tên riêng và từ lóng.
- Dữ liệu và checkpoint chỉ dùng được cho mục đích phi thương mại.
- Hệ thống:
  - không lip-sync;
  - không xử lý đoạn nhiều người nói chồng tiếng;
  - không có xác thực người dùng;
  - chỉ chạy 1 job một lúc;
  - chưa có chức năng huỷ job.

## 7.3 Hướng phát triển

- Train Run 3 đầy đủ, với vector cảm xúc lấy từ câu đích.
- GRPO theo mục 3.3 của paper 2.5: sinh 4 ứng viên mỗi câu, phần thưởng là CER (ASR đóng băng) cộng SS.
- Finetune nhẹ S2M nếu CER đã tốt mà tai vẫn nghe méo thanh. Việc này cần khoảng 50 giờ dữ liệu sạch 22–24 kHz.
- Bộ test theo nhóm lỗi (số, tên riêng, cặp chỉ khác thanh); bổ sung bộ chuẩn hoá số và ngày tháng.
- Lip-sync hình ảnh; xử lý streaming hoặc gần real-time; hỗ trợ phim dài.
- Hỗ trợ nhiều người dùng: chuyển metadata sang SQLite hoặc Postgres, thêm xác thực.

## 7.4 Đạo đức và pháp lý (nên có một mục riêng)

- Giọng nói do AI tạo luôn có nhãn trên website và trong video xuất ra.
- Demo công khai chỉ dùng phim có license Creative Commons (Blender Open Movies).
- Clone giọng chỉ dùng cho nghiên cứu, cần sự đồng ý của chủ giọng.
- License dữ liệu (CC BY-NC-SA, CC BY-NC-ND, chỉ dùng cho nghiên cứu) và license mô hình (bilibili IndexTTS) quy định cách công bố checkpoint.
