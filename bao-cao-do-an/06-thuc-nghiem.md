# Tư liệu Chương 6: Thực nghiệm và đánh giá

Đánh giá chia hai tầng: **tầng TTS** chứng minh finetune có tác dụng; **tầng lồng tiếng** chứng minh cả hệ thống dùng được. Đến 07/10 mới có số liệu tầng TTS.

Mọi số chạy trên RTX 5070 Ti 16 GB. Tham số giải mã: temperature 0,7, top-p 0,8, top-k 30, beam 1, repetition penalty 10, `emo_alpha` 0,8. Nguồn số liệu: `results/tts/*/summary.json`, gom trong `so-lieu/tong-hop-danh-gia-tts.csv`.

## 6.1 Bộ test

| Bộ | Số câu | Mô tả | File |
| --- | ---: | --- | --- |
| Dev (`dev3`) | 100 | Người nói đã có trong train; câu mẫu lấy từ train, cùng giọng thật | `data/splits/dev_tts_v3.jsonl` |
| **Test zero-shot** | **180** | 25 người nói **chưa từng có trong train**; câu mẫu chọn lại cho cùng giọng thật (`data_prep/test_prompts.py`) | `data/splits/test_zeroshot.jsonl` |
| Chuyển cảm xúc xuyên ngôn ngữ | 86 | Câu mẫu tiếng Anh có cảm xúc (ESD, 9 người, 5 cảm xúc). Văn bản tiếng Việt trung tính, giống nhau cho mọi cảm xúc của cùng một người nói, nên cảm xúc ở đầu ra chỉ có thể đến từ câu mẫu. Câu mẫu vừa làm giọng mẫu vừa làm mẫu cảm xúc, **mô phỏng đúng tình huống lồng tiếng** | `data/esd_en/emotion_test.jsonl` |
| Lồng tiếng | 15–20 clip × 1–3 phút (~300 câu) | Phim mở của Blender (*Tears of Steel*, *Sintel*, CC) | **[CHƯA CÓ]** |

So với kế hoạch: bộ test zero-shot dùng 180 câu thay vì 200. Bộ cross-lingual 100 câu được thay bằng bộ ESD 86 câu, vì bộ ESD vừa đo được cảm xúc vừa đo được độ giống giọng xuyên ngôn ngữ.

## 6.2 Kết quả chính: test zero-shot (Bảng 6.1)

| Hệ thống | CER ↓ | WER ↓ | SS ↑ | SS_WavLM ↑ | UTMOS ↑ | RTF ↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| IndexTTS 2.5 gốc (`lang=vi`) | 71,4% | 95,3% | 0,662 | 0,934 | 2,792 | 0,330 |
| IndexTTS2-vi (dinhthuan) | **1,4%** | **3,2%** | 0,678 | 0,930 | 2,268 | 0,622 |
| Run 1 (LR 5e-5, 1 epoch) ¹ | 4,1% | 9,6% | 0,720 | 0,948 | 2,509 | 0,337 |
| **Run 2, bước 28k (đề xuất)** | **3,1%** | 7,2% | **0,726** | **0,950** | **2,539** | **0,335** |
| F5-TTS-Vietnamese | **[CHƯA CHẠY]** | | | | | |

¹ Run 1 dùng lần chia tập cũ, nên có thể đã nghe một phần người nói của tập test này.

**Đối chiếu gate 28/10:**

| Tiêu chí | Kết quả | Đạt? |
| --- | --- | --- |
| CER ≤ 5% trên người nói chưa nghe | 3,1% | ✅ |
| SS ≥ dinhthuan | 0,726 so với 0,678 | ✅ |
| Nghe 20 mẫu không thấy lỗi thanh điệu rõ | — | **[CHƯA LÀM]**: cần người nghe |

**Nhận xét để viết:**

- Model gốc không nói được tiếng Việt: CER 71%, không câu nào có CER < 10%. Nghe thử ở `am-thanh-mau/overfit/base_*.wav` và `am-thanh-mau/truoc-finetune/base_vi.wav`.
- Sau finetune, **CER giảm 23 lần** (71,4% → 3,1%). **SS tăng** từ 0,662 lên 0,726: model gốc nói sai ngôn ngữ nên giọng cũng kém giống. Trung vị CER của Run 2 là 1,9%; 61/180 câu đúng hoàn toàn; 9/180 câu có CER > 10%.
- So với dinhthuan:
  - Run 2 **giống giọng hơn** (0,726 so với 0,678), **UTMOS cao hơn** (2,54 so với 2,27) và **nhanh hơn khoảng 1,9 lần** (RTF 0,335 so với 0,622).
  - dinhthuan **rõ chữ hơn**: CER 1,4% so với 3,1%; dinhthuan có 103/180 câu đúng hoàn toàn.
  - Tính theo từng câu: Run 2 có SS cao hơn dinhthuan ở 52,8% số câu, và CER ≤ dinhthuan ở 48,3% số câu.
  - Đây là đánh đổi cần viết thẳng: tại bước 28k, Run 2 mới train khoảng 1,5 epoch (18.530 bước mỗi epoch) trên 371 giờ, còn dữ liệu và thời gian train của dinhthuan không công bố.
- So với bản Đức (WER 5,35% trên 30 câu): Run 2 có WER 7,2% trên 180 câu. Hai số không so trực tiếp được vì khác ngôn ngữ, khác ASR và khác cỡ bộ test.

Kết quả theo từng nguồn dữ liệu của người nói test (CER / SS của Run 2):

| Nguồn | phoaudiobook | phoaudiobook2 | vimd | vivoice | vivoice2 |
| --- | --- | --- | --- | --- | --- |
| Run 2 | 2,8% / 0,642 | 1,2% / 0,741 | 2,6% / 0,817 | 4,8% / 0,711 | 4,6% / 0,690 |
| dinhthuan | 0,7% / 0,630 | 0,9% / 0,750 | 1,4% / 0,800 | 2,0% / 0,588 | 2,5% / 0,561 |

viVoice khó hơn với cả hai model, vì là giọng tự nhiên từ YouTube. Ở nhóm này Run 2 có SS cao hơn dinhthuan rõ nhất (+0,12).

## 6.3 Chọn checkpoint, chọn LR và tham số giải mã (dev, 100 câu)

**Run 1, chọn LR** (dev của lần chia tập cũ):

| Hệ thống | CER | WER | SS | UTMOS |
| --- | ---: | ---: | ---: | ---: |
| Gốc | 67,6% | 94,4% | 0,651 | 3,076 |
| LR 2e-5, bước 9.159 | 5,4% | 11,0% | 0,728 | 2,755 |
| LR 5e-5, bước 6.000 | 4,5% | 10,4% | 0,731 | 2,757 |
| **LR 5e-5, bước 9.159** | **4,1%** | **9,2%** | **0,731** | **2,777** |

**Run 2, theo checkpoint** (dev3):

| Bước | 24k | **28k** | 32k | 36k | 40k | 44k | 48k | 52k | 55,59k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CER | 4,2% | **3,2%** | 3,7% | 3,9% | 3,3% | 4,2% | 3,9% | 4,0% | 4,1% |
| SS | 0,735 | **0,741** | 0,740 | 0,734 | 0,733 | 0,732 | 0,728 | 0,740 | 0,737 |
| UTMOS | 2,876 | **2,896** | 2,880 | 2,855 | 2,838 | 2,865 | 2,866 | 2,846 | 2,820 |

Trên cùng bộ dev3: model gốc CER 68,8%, SS 0,672; Run 1 CER 4,2%, SS 0,737.

**Tham số giải mã và độ nhiễu của phép đo** (Run 2 bước 28k, dev3; `data/sweep_and_pilot2.sh`):

| Cấu hình | CER | WER | SS | UTMOS | RTF |
| --- | ---: | ---: | ---: | ---: | ---: |
| T 0,7 (mặc định), lần 1 | 3,2% | 7,4% | 0,741 | 2,896 | 0,479 |
| T 0,7, **chạy lặp lần 2** | 3,7% | 8,8% | 0,737 | 2,890 | 0,516 |
| T 0,5 | 3,2% | 7,0% | 0,735 | 2,836 | 0,553 |
| T 0,3 | 3,2% | 6,6% | 0,739 | 2,844 | 0,538 |
| T 0,7 + beam 3 | **2,8%** | 6,8% | 0,736 | 2,901 | 0,507 |

**Kết luận cần viết:**

- Chạy lặp đúng một cấu hình mà CER vẫn chênh 0,5 điểm (3,2% so với 3,7%), vì giải mã có lấy mẫu ngẫu nhiên.
- Vì vậy chênh lệch giữa các checkpoint từ 24k đến 55k (3,2–4,2%) **phần lớn nằm trong mức nhiễu**. Việc chọn bước 28k là hợp lệ theo quy tắc đã đặt trước, nhưng không nên nói 28k "tốt hơn hẳn".
- Giảm temperature không cải thiện CER rõ rệt. Beam 3 có CER thấp nhất (2,8%), nhưng chênh lệch vẫn trong nhiễu. Muốn kết luận phải chạy lặp nhiều seed.
- Dev loss giảm đến bước 54k (4.4) nhưng CER không giảm theo. Đây là bằng chứng cho quyết định chọn theo CER.

## 6.4 Chuyển cảm xúc và giọng xuyên ngôn ngữ (Bảng 6.x, 86 câu ESD)

| Hệ thống | CER | SS | SS_WavLM | UTMOS | ES ↑ | EMO_MATCH ↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| IndexTTS 2.5 gốc | 73,2% | **0,608** | **0,874** | **3,660** | **0,869** | **0,861** |
| dinhthuan | **0,3%** | 0,388 | 0,737 | 3,079 | 0,594 | 0,349 |
| Run 1 LR 2e-5, 9.159 | 1,0% | 0,469 | 0,716 | 3,019 | 0,663 | 0,488 |
| Run 1 LR 5e-5, 6.000 | 0,5% | 0,467 | 0,710 | 2,941 | 0,665 | 0,616 |
| Run 1 LR 5e-5, 9.159 | 0,8% | 0,464 | 0,715 | 3,008 | 0,658 | 0,570 |
| Run 2, 28k | 0,7% | 0,460 | 0,713 | 3,014 | 0,648 | 0,512 |
| Run 3 thử nghiệm (p = 0,5), 9.200 | 0,8% | 0,477 | 0,728 | 2,938 | 0,691 | 0,616 |
| **Run 3 thử nghiệm 2 (p = 1,0), 9.200** | 0,5% | **0,503** | **0,734** | 3,112 | **0,779** | **0,721** |
| Run 3 đầy đủ (p = 1,0, 3 epoch) | **[ĐANG CHẠY]** từ 08/10 | | | | | |

**Phát hiện (đóng góp phân tích của đồ án):**

1. **Finetune làm mất một phần cảm xúc và độ giống giọng khi câu mẫu là tiếng Anh.**
   - ES giảm từ 0,87 xuống khoảng 0,65; EMO_MATCH giảm từ 0,86 xuống 0,51–0,62.
   - SS xuyên ngôn ngữ giảm từ 0,61 xuống khoảng 0,46. Ngược lại, khi câu mẫu là tiếng Việt (mục 6.2), SS lại tăng.
   - Điểm cảm xúc cao của model gốc phải đọc kèm CER 73%: model gốc nói "không thành chữ" nhưng chép lại được ngữ điệu của câu mẫu.
   - dinhthuan còn mất nhiều hơn: SS 0,388, EMO_MATCH 0,349.
2. **Giả thuyết:** khi train, vector cảm xúc lấy từ câu mẫu, là một câu khác của cùng người nói. Mô hình học được rằng vector cảm xúc ít liên quan đến cách đọc câu đích, nên dần bỏ qua nó. Có dấu hiệu hiện tượng nặng dần theo số bước train: ES giảm đều từ 0,665 (Run 1, 6k) xuống 0,658 (9,2k) rồi 0,648 (Run 2, 28k); EMO_MATCH đi theo cùng chiều (0,616 → 0,570 → 0,512). Tuy nhiên bộ test chỉ có 86 câu, và bản LR 2e-5 có EMO_MATCH thấp (0,488) dù train cùng số bước, nên chưa đủ để kết luận chắc chắn.
3. **Thử khắc phục (Run 3):** khi train, với xác suất p, lấy vector cảm xúc **từ chính câu đích** (`train.emotion_from_target_prob`).
   - Với p = 0,5, sau 9.200 bước (so với Run 1 cùng số bước): ES 0,658 → 0,691, EMO_MATCH 0,570 → 0,616, SS xuyên ngôn ngữ 0,464 → 0,477.
   - CER giữ nguyên trên bộ ESD (0,8%) và trên dev3 (4,3% so với 4,2%).
   - Với p = 1,0 (cùng 9.200 bước): ES 0,779, EMO_MATCH 0,721, SS xuyên ngôn ngữ 0,503; CER dev3 4,2% (không đổi).
   - **Hiệu ứng tăng đều theo p** (p = 0 / 0,5 / 1,0: EMO_MATCH 0,570 / 0,616 / 0,721; ES 0,658 / 0,691 / 0,779; SS 0,464 / 0,477 / 0,503) mà CER không đổi. Đây là bằng chứng chính cho giả thuyết ở điểm 2.
   - Đã chạy Run 3 đầy đủ (p = 1,0, 3 epoch, cùng dữ liệu Run 2) từ 08/10; kết quả ở `results/tts/report_run3.md`.
4. Phân tích theo từng cảm xúc (ES / EMO_MATCH):

| Cảm xúc | Gốc | Run 2, 28k | Run 3 thử nghiệm (p = 0,5) | Run 3 thử nghiệm 2 (p = 1,0) |
| --- | --- | --- | --- | --- |
| angry | 0,926 / 1,00 | 0,753 / 0,56 | 0,821 / 0,81 | **0,896 / 0,94** |
| happy | 0,856 / 0,69 | 0,719 / 0,63 | 0,762 / 0,69 | **0,805 / 0,75** |
| neutral | 0,914 / 0,89 | 0,820 / 0,94 | 0,806 / 0,94 | 0,852 / 0,83 |
| sad | 0,914 / 1,00 | 0,534 / 0,22 | 0,605 / 0,50 | **0,714 / 0,61** |
| surprised | 0,742 / 0,72 | 0,433 / 0,22 | 0,485 / 0,17 | **0,644 / 0,50** |

   - "Ngạc nhiên" và "buồn" bị mất nhiều nhất.
   - EMO_MATCH của "trung tính" luôn cao. Lý do: đầu ra kém cảm xúc thì hay bị phân loại thành trung tính, nên số này **không** chứng tỏ model giữ được cảm xúc trung tính tốt. Phải ghi rõ khi trình bày.

## 6.5 Phân tích lỗi (test zero-shot, Run 2 bước 28k)

Các câu CER cao nhất (`so-lieu/ket-qua-tts/test_r2_028000.csv`):

| CER | Văn bản đích | ASR nghe được | Loại lỗi |
| ---: | --- | --- | --- |
| 34,5% | Thế nên tụi mình ế bền, ế vững. | Thế nên tụi mình É b bên, ấy v vẫn. | Câu ngắn, từ lóng, lặp âm "ế" |
| 20,6% | người nhiệt tình chỉ đường cho tôi | Nguyên nhí tình chỉ đường cho tôi. | Sai vần/thanh ở âm tiết đầu |
| 19,3% | Kỷ lục thứ sáu, người song phẳng nhất, đó là Đào Minh Dương. | Kỷ lục thứ sáu,ân song ph phải nhất đó là Đào Mình Dương. | Tên riêng (Minh → Mình: sai thanh), lặp phụ âm |
| 17,4% | hay cái gì tương tự vậy. | Hay cái gì tin từ vậy? | Nuốt âm khi nói nhanh |
| 16,0% | Tôi nhớ rõ khoảnh khắc đó. | Tôio rõ khoảnh khắc đó. | Mất âm tiết |
| 11,5% | lần đầu là năm tôi sinh ra. | Lần đầu là năm tôi sinh già. | Sai phụ âm đầu |
| 11,3% | Liên binh đòn bay như rồng, yêu tinh bất khả chiến bại. | Liên bến đòn bay chưa rồng, yêuinh bất khả chiến bại. | Cụm từ hiếm (tên trong game) |
| 10,3% | Mà nước nở hết lên rồi chạy ra khỏi nhà. | Mã nức nở hất lên rồi chạy ra khỏi nhà. | Có thể do chính văn bản gốc sai ("nước nở" → "nức nở"): **lỗi nhãn**, không phải lỗi TTS |

CER theo độ dài câu (số âm tiết): ≤ 8: 4,1% (36 câu) · 9–15: 4,7% (22) · 16–30: 2,9% (38) · > 30: 2,4% (84). **Câu ngắn khó hơn.** Câu ngắn thì mỗi lỗi chiếm tỉ trọng lớn, và mô hình có ít ngữ cảnh. Điều này đáng chú ý cho lồng tiếng, vì thoại phim thường ngắn.

Các nhóm lỗi nên kiểm tra thêm, theo cách bản Đức chia nhóm:

- câu đơn giản;
- tên riêng;
- số và ngày tháng (bản Đức sai nhiều nhất ở nhóm này: WER 15,6%);
- câu hỏi;
- từ mượn tiếng Anh;
- cặp chỉ khác thanh (ma / má / mà / mả / mã / mạ).

**[CHƯA CÓ]** bộ test theo nhóm này.

Hạn chế của phép đo:

- CER phụ thuộc ASR parakeet: lỗi ASR với tên riêng và từ lóng bị tính thành lỗi TTS.
- UTMOS được train chủ yếu trên tiếng Anh, nên chỉ dùng để so tương đối.
- Mỗi lần chấm chỉ một seed; độ nhiễu khoảng ±0,5 điểm CER (mục 6.3).

## 6.6 Tầng lồng tiếng: **[CHƯA CÓ]**

Theo kế hoạch, cần các số sau:

| Chỉ số | Mục tiêu (NFR-03) | Công cụ |
| --- | --- | --- |
| Sai số thời lượng trung bình; % câu lệch < 10% | ≥ 90% câu lệch < 10% | `eval/eval_dubbing.py` |
| Nhất quán giọng mỗi nhân vật | — | `eval_dubbing` |
| COMET-kiwi + chấm tay 50 câu | — | `eval_dubbing` (xuất CSV chấm tay) |
| RTF toàn pipeline, thời gian tạo lại 1 câu | Chốt sau lần đo đầu | `vidub rtf` |
| VRAM đỉnh | ≤ 16 GB | log |

## 6.7 Ablation: **[CHƯA CÓ]**

Theo kế hoạch, chọn 3 thí nghiệm, mỗi thí nghiệm một bảng nhỏ:

1. Finetune so với zero-shot: **đã có** (mục 6.2).
2. Mẫu cảm xúc là câu gốc, so với dùng giọng mẫu cho cả hai (`synthesize.indextts.use_style_prompt=false`); đo ES và EMOS. Bộ ESD đã mô phỏng một phần.
3. Dịch có ngữ cảnh và ràng buộc độ dài, so với dịch từng câu; đo sai số thời lượng và chất lượng dịch.
4. (Tuỳ chọn) Có và không có bước co giãn thời gian.
5. Có thể thêm: `emotion_from_target_prob` 0 / 0,5 / 1,0 (mục 6.4).

## 6.8 MOS chủ quan: **[CHƯA CÓ]**

- 10–15 người nghe, trộn ngẫu nhiên các hệ thống, có câu kiểm tra mức độ chú ý.
- Chấm 4 tiêu chí: tự nhiên, giống giọng, cảm xúc, khớp hình (thang 1–5).
- Gửi từ 12/11, chốt kết quả trước 18/11.
