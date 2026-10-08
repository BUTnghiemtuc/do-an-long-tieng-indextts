# Tư liệu Chương 1: Giới thiệu

## 1.1 Bài toán

- **Đầu vào:** clip phim 1–5 phút, thoại tiếng Anh. Giả định thoại rõ, ít nhạc nền đè lên và ít chồng tiếng.
- **Đầu ra:** video lồng tiếng Việt và phụ đề SRT tiếng Việt, với các yêu cầu:
  - mỗi nhân vật giữ giọng gốc;
  - mỗi câu thoại khớp thời lượng câu gốc;
  - nhạc nền và hiệu ứng (M&E) giữ nguyên.
- Người dùng sửa được người nói và bản dịch, rồi tạo lại từng câu trên website.

## 1.2 Động lực (ý để viết)

- Lồng tiếng thủ công tốn nhiều thời gian và tiền (thuê diễn viên lồng tiếng, phòng thu). Phụ đề không phù hợp với một số người xem, ví dụ trẻ em hoặc người thị lực kém.
- Các mô hình TTS zero-shot gần đây (IndexTTS2, IndexTTS 2.5) đã làm được ba việc cùng lúc: tách âm sắc khỏi cảm xúc, điều khiển thời lượng, và chuyển cảm xúc sang ngôn ngữ khác. Đây đúng là ba yêu cầu của lồng tiếng.
- IndexTTS 2.5 gốc **không nói được tiếng Việt**. Đo trên 180 câu của 25 người nói chưa từng nghe, CER là **71,4%** ([06-thuc-nghiem.md](06-thuc-nghiem.md)). Vì vậy cần finetune.
- Bản IndexTTS2 tiếng Việt cộng đồng (dinhthuan) chưa công bố CER hay độ giống giọng, và chạy chậm hơn 2.5.

## 1.3 Mục tiêu

Trước 25/11/2026, bàn giao hệ thống lồng tiếng phim tự động sang tiếng Việt, chạy end-to-end qua website. Hệ thống phải giữ âm sắc từng nhân vật, kèm báo cáo và bộ số liệu đánh giá. Lõi kỹ thuật là IndexTTS 2.5 được finetune cho tiếng Việt.

**Sản phẩm bàn giao:**

1. Checkpoint IndexTTS 2.5 tiếng Việt và model card (dữ liệu, cấu hình, kết quả, license).
2. Pipeline lồng tiếng end-to-end bằng Python, chạy được qua CLI.
3. Website demo: tải clip lên, chỉnh sửa, xuất MP4 và SRT.
4. Bộ test và bảng kết quả: CER/WER, UTMOS, độ giống giọng, RTF, sai số thời lượng, MOS.
5. Quyển đồ án, slide bảo vệ, video demo dự phòng.

## 1.4 Phạm vi

**Trong phạm vi:**

- Một chiều dịch Anh → Việt.
- Clip ngắn, mỗi lần chạy trên 1 GPU.
- Demo trên một máy.

**Ngoài phạm vi** (ghi vào hướng phát triển):

- lip-sync hình ảnh;
- phim dài;
- xử lý real-time;
- đoạn nhiều người nói chồng lên nhau;
- xác thực người dùng, nhiều người dùng cùng lúc.

## 1.5 Đóng góp (đề xuất cách viết, chốt lại sau khi có đủ số liệu)

1. **Finetune IndexTTS 2.5 cho tiếng Việt bằng LoRA trên GPU phổ thông 16 GB.**
   - Theo các nguồn đã tìm được, đây là bản IndexTTS 2.5 tiếng Việt đầu tiên. Cần kiểm tra lại HuggingFace trước khi viết câu này.
   - Script train viết lại từ đầu, vì nhóm tác giả không công bố script train. Có test kiểm chứng logit lúc train trùng logit đường suy luận chính thức.
   - Kết quả trên 25 người nói chưa từng nghe: CER 71,4% → **3,1%**, SS 0,662 → **0,726**. SS cao hơn bản dinhthuan (0,678), RTF nhanh gấp khoảng 1,9 lần dinhthuan.
2. **Quy trình dữ liệu tiếng Việt 371 giờ, 1.786 người nói**, lọc qua 5 bước. Có thêm bước lọc cặp giọng mẫu/câu đích theo độ giống giọng. Bước này xử lý được vấn đề nhãn người nói của viVoice là kênh YouTube chứ không phải người thật.
3. **Phân tích hiện tượng mất cảm xúc và mất độ giống giọng xuyên ngôn ngữ sau finetune**, kèm một cách khắc phục đã thử nghiệm: lấy vector cảm xúc từ câu đích khi train (Run 3). Xem [06-thuc-nghiem.md](06-thuc-nghiem.md) mục 6.4.
4. **Pipeline lồng tiếng 8 bước có con người tham gia vòng xử lý**, gồm:
   - dịch theo cảnh, có ngân sách âm tiết lấy từ tốc độ nói trung vị đo trên tập train (4,0 âm tiết/giây; lần chia tập đầu đo được 3,98);
   - căn thời lượng nhiều tầng: `duration_factor` → co giãn ±10% → mượn khoảng lặng;
   - cache theo từng câu, nên sửa một câu chỉ phải sinh lại câu đó.
5. **Website biên tập** cho phép sửa bản dịch hoặc người nói rồi tạo lại từng câu.

## 1.6 Bố cục quyển

Liệt kê 7 chương theo [00-dan-y-va-lich.md](00-dan-y-va-lich.md).
