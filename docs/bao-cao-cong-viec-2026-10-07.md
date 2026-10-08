# Báo cáo công việc: lồng tiếng phim tự động sang tiếng Việt với IndexTTS

**Kỳ báo cáo:** 03/10 – 07/10/2026 (tuần 1 của kế hoạch 8 tuần)
**Máy thực nghiệm:** 1 GPU NVIDIA RTX 5070 Ti 16 GB

## 1. Tóm tắt

- **Dữ liệu huấn luyện đã xong, sớm một tuần so với hạn 14/10.** Sau khi lọc còn 371,2 giờ tiếng Việt, gồm 298.465 câu của 1.786 người nói, lấy từ 3 bộ dữ liệu công khai.
- **Đã finetune xong IndexTTS 2.5 cho tiếng Việt (Run 2).** Trên 25 người nói chưa có trong dữ liệu train, CER đạt 3,1% (bản gốc: 71,4%). Độ giống giọng là 0,726, cao hơn bản IndexTTS2 tiếng Việt của cộng đồng (dinhthuan, 0,678). Như vậy đã **đạt 2/3 tiêu chí của gate 28/10**. Tiêu chí còn lại là nghe kiểm tra lỗi thanh điệu, chưa làm.
- **Vấn đề lớn nhất là model mất cảm xúc sau finetune.** Khi câu mẫu là tiếng Anh có cảm xúc, tỉ lệ câu tiếng Việt giữ đúng cảm xúc giảm từ 86% xuống 51%. Câu buồn gần như mất hẳn: còn 4/18 câu. Đã xác định được nguyên nhân. Bản sửa thử nghiệm nâng tỉ lệ lên 62% mà CER không tăng. Mẫu thử còn nhỏ nên cần xác nhận thêm.
- **Pipeline lồng tiếng 8 bước và website đã viết xong và chạy được với backend giả lập.** Chưa chạy clip thật trên GPU.
- **Chương 3 (Phân tích và thiết kế hệ thống):** đã lập dàn ý chi tiết và lịch viết. Xem [ke-hoach-chuong-3-thiet-ke-he-thong.md](ke-hoach-chuong-3-thiet-ke-he-thong.md).

## 2. Tiến độ so với kế hoạch

| Giai đoạn | Hạn | Trạng thái |
| --- | --- | --- |
| 1. Dữ liệu | 14/10 | **Xong** (07/10) |
| 2. Finetune IndexTTS 2.5 | 28/10 (gate) | Run 2 xong, đạt 2/3 tiêu chí gate. Đang xử lý vấn đề cảm xúc |
| 3. Pipeline lồng tiếng | 01/11 | Code xong, test với backend giả lập đều qua. Chưa chạy clip thật |
| 4. Website | 13/11 | Bản HTML/JS thuần đã chạy với backend giả lập |
| 5. Đánh giá | 18/11 | Phần đánh giá TTS đã chạy thật trên GPU. Phần đánh giá lồng tiếng chưa chạy |
| Chương 3 báo cáo | 04/11 | Đã lập kế hoạch viết (06/10) |

## 3. Công việc đã làm

### 3.1 Mã nguồn

Repo `vidub` gồm 5 phần:

- `vidub/`: pipeline lồng tiếng 8 bước, gồm tách audio, tách giọng/nhạc nền, phân đoạn người nói, nhận dạng lời thoại, dịch bằng LLM có ràng buộc số âm tiết, sinh giọng, căn thời lượng và trộn âm. Pipeline có cache theo từng câu, nên sửa một câu thì chỉ sinh lại câu đó.
- `server/`: API FastAPI và trang web để tải clip, theo dõi tiến độ, sửa bản dịch, tạo lại từng câu và tải kết quả.
- `data_prep/`: tải, lọc, chia tập và thống kê dữ liệu.
- `training/indextts25/`: finetune IndexTTS 2.5 bằng LoRA.
- `eval/`: các chỉ số đánh giá TTS và đánh giá lồng tiếng.

Có 39 test tự động. Ngày 07/10 đã chạy lại 34 test chạy nhanh, tất cả đều qua. 5 test finetune chạy rất lâu trên CPU nên lần này chưa chạy lại.

Các thành phần **đã chạy thật trên GPU**: IndexTTS 2.5 (bản gốc và các bản finetune), IndexTTS2 dinhthuan, ASR Parakeet tiếng Việt, UTMOS, CAMPPlus, WavLM-SV, emotion2vec.

Các thành phần **chưa chạy thật**: Demucs, pyannote, WhisperX, dịch bằng Claude, COMET.

### 3.2 Dữ liệu huấn luyện

Nguồn dữ liệu:

- **viVoice:** giọng đọc từ YouTube. Tải 300 giờ.
- **PhoAudiobook:** sách nói. Tải 200 giờ.
- **ViMD:** giọng nói nhiều vùng miền. Tải 81,4 giờ.

Tổng cộng 581 giờ thô. Dữ liệu thô được lọc qua 4 tầng:

| Tầng lọc | Số câu còn lại |
| --- | ---: |
| Dữ liệu thô | 446.865 |
| Thời lượng 1–25 s | 425.747 |
| CER (nhận dạng lại bằng Parakeet) ≤ 10%; riêng PhoAudiobook ≤ 5% | 356.559 |
| Bỏ khoảng 12% câu có UTMOS thấp nhất | 313.856 |
| Mỗi người nói có ít nhất 2 câu | 310.139 |

Sau khi lọc, dữ liệu được chia thành 3 tập:

| Tập | Số câu | Ghi chú |
| --- | ---: | --- |
| Train | 298.465 | 371,2 giờ, 1.786 người nói |
| Dev | 100 | Người nói có trong train |
| Test zero-shot | 180 | 25 người nói không có trong train |

Thống kê chi tiết ở [data_stats.md](data_stats.md). Tốc độ nói trung vị là **4,0 âm tiết/giây**, dùng để tính ngân sách âm tiết khi dịch.

Hai lỗi dữ liệu đã phát hiện và xử lý:

- **viVoice gắn nhãn người nói theo kênh YouTube.** Một kênh có thể có nhiều người nói, nên câu mẫu giọng có thể là một người khác. Đã thêm bước lọc cặp (câu mẫu, câu đích) theo độ giống giọng CAMPPlus ≥ 0,5 ([make_pairs.py](../training/indextts25/make_pairs.py)), còn 592.951 cặp. Câu mẫu của tập test cũng được chọn lại theo cách này ([test_prompts.py](../data_prep/test_prompts.py)), nên tập test giảm từ 184 xuống 180 câu.
- **ViMD mất 83% số câu khi lọc**, từ 15.023 còn 2.566 câu. Lý do: phần lớn người nói chỉ có 1 câu, và CER nhận dạng lại cao. ViMD vẫn đóng góp 1.142 người nói, tức đa dạng giọng nhất trong 3 bộ.

### 3.3 Finetune IndexTTS 2.5

Công thức finetune theo bản tiếng Đức đã công bố (sharrnah/index-tts-2.5-german), chỉ đổi ngôn ngữ:

- LoRA rank 64, α = 128, gắn vào cả 24 lớp của khối GPT.
- Train thêm text embedding, hai output head và token ngôn ngữ `vi`. Token `vi` khởi tạo từ `en`, learning rate gấp 5 lần.
- Đóng băng các khối còn lại: w2v-BERT, codec, CAMPPlus, S2M, BigVGAN.
- Batch hiệu dụng 32 (8 × tích luỹ 4), có gradient checkpointing. VRAM đỉnh 7,4 GB, đủ chỗ trống để chạy đánh giá song song trên cùng GPU.

Các lần chạy:

| Lần chạy | Dữ liệu | Số bước | Kết quả chính |
| --- | --- | ---: | --- |
| Overfit (kiểm tra mã) | 6 câu ViMD | 1.500 | CER giảm từ 75,2% xuống 6,0%. Mã train và export chạy đúng |
| Run 1 | 188 giờ, khoảng 293 nghìn cặp, 1 epoch | 9.159 | So 2 mức learning rate: 5e-5 cho CER dev 4,1%, còn 2e-5 cho 5,4%. **Chọn 5e-5** |
| Run 2 | 371 giờ, 592.951 cặp, 3 epoch | 55.590 | Chạy 11 giờ 42 phút. **Checkpoint tốt nhất ở bước 28.000** (khoảng 1,5 epoch) |
| Run 3 thử nghiệm | Như Run 2; vector cảm xúc lấy từ câu đích với p = 0,5 | 9.200 | Thử sửa lỗi mất cảm xúc, xem mục 4.1 |

Checkpoint được chọn theo CER trên dev, không theo loss dev. Loss dev của Run 2 giảm đến tận bước 54.000. Trong khi đó, CER dev thấp nhất ở bước 28.000 (3,2%) và dao động trong khoảng 3,2–4,2% ở các checkpoint sau.

### 3.4 Kết quả trên tập test zero-shot

Tập test gồm 180 câu của 25 người nói chưa có trong train. Câu mẫu giọng là tiếng Việt, cùng người nói với câu đích.

| Hệ thống | CER ↓ | WER ↓ | SS ↑ | SS WavLM ↑ | UTMOS ↑ | RTF ↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| IndexTTS 2.5 gốc | 71,4% | 95,3% | 0,662 | 0,934 | 2,79 | 0,330 |
| dinhthuan (IndexTTS2 tiếng Việt, cộng đồng) | **1,4%** | **3,2%** | 0,678 | 0,930 | 2,27 | 0,622 |
| Run 1 (lr 5e-5, bước 9.159)¹ | 4,1% | 9,6% | 0,720 | 0,948 | 2,51 | 0,337 |
| **Run 2 (bước 28.000)** | 3,1% | 7,2% | **0,726** | **0,950** | 2,54 | **0,335** |

¹ Dữ liệu được chia lại sau Run 1, nên Run 1 có thể đã nghe một phần người nói của tập test này.

Đối chiếu với tiêu chí gate 28/10:

| Tiêu chí | Kết quả | Đánh giá |
| --- | --- | --- |
| CER ≤ 5% trên người nói chưa nghe | 3,1% | Đạt |
| SS không thấp hơn dinhthuan | 0,726 so với 0,678 (WavLM: 0,950 so với 0,930) | Đạt |
| Nghe không thấy lỗi thanh điệu rõ | Chưa nghe chấm | **Chưa kiểm tra** |

Nhận xét:

- Bản gốc IndexTTS 2.5 không nói được tiếng Việt: CER trên 70%, nghe ra chuỗi âm vô nghĩa. Finetune đã giải quyết được việc này.
- dinhthuan có CER thấp hơn (1,4% so với 3,1%). Đổi lại, Run 2 giống giọng hơn, UTMOS cao hơn và sinh nhanh gần gấp đôi. Hiện chưa rõ dinhthuan được train trên dữ liệu nào, nên không loại trừ được khả năng nó đã nghe người nói của tập test.
- UTMOS của các bản finetune (2,5–2,9) thấp hơn bản gốc. Một phần do dữ liệu train có chất lượng thu âm trung bình (YouTube, sách nói). Một phần do UTMOS được huấn luyện cho tiếng Anh. Chỉ số này nên dùng để so sánh giữa các bản finetune với nhau.

## 4. Vấn đề và hướng xử lý

### 4.1 Model mất cảm xúc sau finetune

Lồng tiếng cần giữ cảm xúc của diễn viên gốc. Để đo khả năng này, đã dựng bộ test 86 câu ([esd_emotion_set.py](../data_prep/esd_emotion_set.py)):

- Câu mẫu là tiếng Anh có cảm xúc, lấy từ bộ ESD, gồm 5 loại cảm xúc.
- Văn bản cần đọc là tiếng Việt trung tính, giống nhau giữa các cảm xúc.

Vì văn bản không đổi, cảm xúc ở đầu ra chỉ có thể đến từ câu mẫu.

Số câu giữ đúng cảm xúc của câu mẫu (nhãn do emotion2vec gán):

| Hệ thống | Trung tính | Vui | Buồn | Giận | Ngạc nhiên | **Tổng** | ES ↑ | SS ↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| IndexTTS 2.5 gốc² | 16/18 | 11/16 | 18/18 | 16/16 | 13/18 | 86,0% | 0,869 | 0,608 |
| dinhthuan | 9/18 | 6/16 | 2/18 | 9/16 | 4/18 | 34,9% | 0,594 | 0,388 |
| Run 1 (bước 9.159) | 17/18 | 11/16 | 3/18 | 13/16 | 5/18 | 57,0% | 0,658 | 0,464 |
| Run 2 (bước 28.000) | 17/18 | 10/16 | 4/18 | 9/16 | 4/18 | 51,2% | 0,648 | 0,460 |
| Run 3 thử (p = 0,5, bước 9.200) | 17/18 | 11/16 | **9/18** | 13/16 | 3/18 | **61,6%** | **0,691** | **0,477** |

² Bản gốc đọc sai nội dung (CER 73%) nhưng giữ được ngữ điệu của câu mẫu. Đây là mức tham chiếu, không phải đối thủ so sánh.

**Nguyên nhân.** Khi train, vector cảm xúc được lấy từ câu mẫu, tức một câu khác của cùng người nói. Vector đó gần như không cho biết ngữ điệu của câu đích, nên model học cách bỏ qua nó. Train càng lâu thì model càng bỏ qua nhiều: Run 2 (bước 28.000) kém Run 1 (bước 9.159).

**Hướng sửa.** Với xác suất p, lấy vector cảm xúc từ chính câu đích, còn vector giọng vẫn lấy từ câu mẫu. Bản thử p = 0,5 (Run 3, 9.200 bước) được so với Run 1 cùng số bước:

- Tỉ lệ giữ đúng cảm xúc tăng từ 57,0% lên 61,6%.
- Câu buồn tăng từ 3/18 lên 9/18.
- ES tăng từ 0,658 lên 0,691.
- CER dev gần như không đổi: 4,3% so với 4,2%.

Mức chênh tổng chỉ tương đương 4 câu trên 86, nên cần đo độ nhiễu trước khi kết luận. Câu ngạc nhiên vẫn chưa cải thiện (3/18).

### 4.2 Giọng kém giống khi câu mẫu là tiếng Anh

Khi câu mẫu và câu đích cùng là tiếng Việt, SS của Run 2 là 0,726. Khi câu mẫu là tiếng Anh (bộ ESD), SS chỉ còn 0,46. Bản gốc cũng giảm khi đổi sang câu mẫu tiếng Anh, nhưng ít hơn: từ 0,662 xuống 0,608.

Điều này ảnh hưởng trực tiếp đến bài toán lồng tiếng, vì câu mẫu luôn là giọng diễn viên nói tiếng Anh. Run 3 cải thiện nhẹ (0,477). Sẽ theo dõi chỉ số này cùng với cảm xúc ở các lần chạy sau.

### 4.3 Các vấn đề kỹ thuật khác

| Vấn đề | Ảnh hưởng | Xử lý |
| --- | --- | --- |
| Dùng cùng một ASR (Parakeet) để lọc dữ liệu và để chấm CER | CER có thể bị đánh giá lạc quan | Chấm chéo bằng Whisper (`--asr whisper`) |
| Tập dev chỉ có 100 câu | Chênh lệch CER giữa các checkpoint (3,2–4,2%) có thể chỉ là nhiễu | Đang chạy lặp cùng một cấu hình để đo nhiễu (mục 5) |
| Kernel CUDA của BigVGAN không biên dịch được, vì nvcc 12.6 chưa hỗ trợ kiến trúc Blackwell (sm_120) | Tự chuyển sang bản PyTorch, chạy đúng nhưng chậm hơn một chút | Cài CUDA toolkit ≥ 12.8 |
| `vi_syllables_per_sec` trong cấu hình đang là 5,0, trong khi đo được 4,0 | Bản dịch sẽ dài hơn thời lượng cho phép | Sửa [default.yaml](../configs/default.yaml) trước khi chạy pipeline thật |
| Bộ ESD có giấy phép CC-BY-NC-4.0 | — | Chỉ dùng để đánh giá, không dùng để train |

## 5. Việc đang chạy

Script `sweep_and_pilot2.sh` bắt đầu chạy lúc 21:41 ngày 07/10, gồm 2 phần:

1. **Thử tham số giải mã trên checkpoint Run 2 bước 28.000** (không cần train lại):
   - lặp lại cấu hình hiện tại để đo độ nhiễu của chỉ số;
   - temperature 0,5 và 0,3;
   - beam search 3.
2. **Run 3 thử nghiệm lần 2 với p = 1,0** (khoảng 2 giờ train), để xem hiệu quả có tăng theo p hay không.

## 6. Kế hoạch tuần tới (08–14/10)

1. Đọc kết quả mục 5:
   - Nếu hiệu quả sửa lỗi cảm xúc lớn hơn độ nhiễu, chạy Run 3 đầy đủ (3 epoch, khoảng 12 giờ) với mức p tốt nhất.
   - Nếu không, giữ Run 2 bước 28.000 cho pipeline.
2. Nghe chấm khoảng 30 câu test zero-shot để kiểm tra lỗi thanh điệu, tức tiêu chí còn lại của gate. Chấm chéo CER bằng Whisper.
3. Chạy toàn bộ pipeline trên một clip thật (*Tears of Steel*) bằng GPU, để kiểm chứng Demucs, pyannote, WhisperX và bước dịch bằng Claude, đồng thời đo RTF từng bước. Sửa `vi_syllables_per_sec` thành 4,0 trước khi chạy.
4. Chương 3: chốt 7 điểm lệch giữa kế hoạch cũ và code, rồi viết mục 3.1 (yêu cầu chức năng, phi chức năng, use case).
5. Cài CUDA toolkit ≥ 12.8 để dùng được kernel BigVGAN.

## 7. Điểm xin ý kiến

1. **Có đưa tiêu chí cảm xúc vào gate 28/10 không?** Ví dụ: tỉ lệ giữ đúng cảm xúc không thấp hơn mức của Run 1 (57%). Gate hiện tại chỉ có CER, SS và nghe thanh điệu, nên Run 2 đạt gate dù mất phần lớn cảm xúc.
2. **Có làm trang chấm MOS trong website không?** Nếu làm, cần thêm tác nhân "Người nghe đánh giá" và use case tương ứng vào Chương 3. Nếu không, đánh giá chủ quan sẽ dùng file CSV chấm tay.

---

## Phụ lục: chỉ số và nơi lưu kết quả

| Chỉ số | Ý nghĩa |
| --- | --- |
| CER / WER | Tỉ lệ lỗi ký tự / từ, so sánh văn bản đầu vào với kết quả nhận dạng lại giọng sinh ra bằng Parakeet |
| SS | Cosine giữa vector giọng CAMPPlus của câu mẫu và giọng sinh ra |
| SS WavLM | Như SS, nhưng dùng WavLM-SV |
| UTMOS | Điểm tự nhiên dự đoán tự động, thang 1–5 |
| ES | Cosine giữa vector emotion2vec của câu mẫu và giọng sinh ra |
| Khớp cảm xúc | Nhãn emotion2vec của giọng sinh ra trùng với nhãn cảm xúc của ESD |
| RTF | Thời gian sinh chia cho thời lượng audio |

Nơi lưu kết quả:

- Bảng tổng hợp Run 2: [results/tts/report_run2.md](../results/tts/report_run2.md).
- Điểm từng câu: `results/tts/<hệ thống>/scores.csv`.
- Log train: `runs/<lần chạy>/log.jsonl`.
- Script chạy từng thí nghiệm: `data/*.sh`.
