# Tư liệu Chương 2: Cơ sở lý thuyết

Khung chương lấy từ bài survey TTS đã đăng trên *Discover Artificial Intelligence*. File này chỉ ghi những gì cần thêm cho đồ án. Các chi tiết về IndexTTS dưới đây tổng hợp từ tài liệu kế hoạch và từ việc đọc mã `index-tts` (commit `d9e41aa`, đọc ngày 3/10/2026). **Khi viết phải trích dẫn lại đúng mục và bảng của paper.**

## 2.1 Các paradigm TTS

Lấy từ bài survey: TTS ghép nối, TTS tham số, TTS neural end-to-end, TTS dựa trên codec / mô hình ngôn ngữ, flow matching / diffusion. Đặt IndexTTS vào nhánh **AR trên token ngữ nghĩa + flow matching**.

Các baseline sẽ so sánh, mỗi cái đại diện cho một nhánh:

| Hệ thống | Kiến trúc | Vai trò trong đồ án |
| --- | --- | --- |
| IndexTTS 2.5 gốc | AR T2S + S2M flow matching | Mốc "trước finetune" |
| IndexTTS2 Vietnamese (dinhthuan) | IndexTTS2, tokenizer SentencePiece mới | Baseline cộng đồng, đồng thời là phương án dự phòng |
| F5-TTS-Vietnamese-1000h | Flow matching non-AR | Baseline khác kiến trúc. **[CHƯA CHẠY]** |
| VoxCPM / OmniVoice (một trong hai) | — | Tuỳ chọn |

## 2.2 IndexTTS2 (arXiv 2506.21619)

Những điểm cần trình bày:

- Text-to-Semantic (T2S) tự hồi quy, có **điều khiển thời lượng**: một embedding thời lượng `p` ép số token ngữ nghĩa bằng thời lượng đích.
- Tách âm sắc khỏi cảm xúc: vector giọng `c` và vector cảm xúc `e` lấy từ hai prompt khác nhau. Đây là cơ sở của thiết kế "giọng mẫu = câu sạch của nhân vật, mẫu cảm xúc = chính câu gốc" trong pipeline.
- Train 3 giai đoạn. Giai đoạn 3 đóng băng các thành phần khác, chỉ train T2S. Đồ án làm tương tự khi chỉ finetune GPT.
- Semantic-to-Mel (S2M) dùng flow matching, sau đó BigVGAN sinh dạng sóng.
- Mô tả bằng chữ (Qwen) → vector cảm xúc.

## 2.3 IndexTTS 2.5 (arXiv 2601.03888) và những điểm khác 2.0

| Thành phần | Mô tả | Khi finetune tiếng Việt |
| --- | --- | --- |
| Tokenizer kiểu Whisper, byte-level BPE, 60.509 token | Byte-level nên không bao giờ ra UNK. Đã có mã ngôn ngữ `<\|vi\|>` | **Giữ nguyên.** Đo được: tiếng Việt khoảng 1,65 token/âm tiết, tiếng Đức khoảng 1,53 token/từ |
| Embedding văn bản + output head | Mỗi token một vector | **Train.** Các token tiếng Việt ít xuất hiện khi pretrain |
| Điều kiện ngôn ngữ kiểu token-level concatenation | Mỗi token văn bản được gắn thêm embedding ngôn ngữ | **Train hàng `vi`** (id 19), khởi tạo từ `en` (id 0), LR gấp 5. Bảng 1 của paper so 3 cách đưa ngôn ngữ vào: cách này cho SS tốt nhất ở cả 4 ngôn ngữ và WER tốt nhất ở 3/4 |
| T2S Transformer: GPT 24 lớp, 1280 chiều, khoảng 0,8B tham số | Văn bản + giọng mẫu → token ngữ nghĩa | **LoRA r=64, α=128 trên cả 24 lớp** |
| Embedding thời lượng `p` | **Không còn** trong GPT của 2.5: hai vị trí sau cond luôn bằng 0 | `duration_factor` co giãn ở S2M: `target_lengths = số frame × 1,72 × duration_factor`. Model card cho phép 0,5–2,0. Không cần xử lý gì khi train |
| Speaker conditioner (CAMPPlus) → `c` | Trích âm sắc | Đóng băng |
| Emotion conditioner + GRL → `e` | Trích cảm xúc từ mẫu cảm xúc | Đóng băng. Paper 2.5 cho thấy cảm xúc chuyển được sang es/ja/ar dù chỉ train cảm xúc trên zh/en |
| Semantic codec (đặc trưng w2v-BERT 2.0, 25 Hz) | Âm thanh → token ngữ nghĩa | Đóng băng. Đổi codec thì phải train lại toàn bộ |
| S2M (flow matching, Zipformer) | Token ngữ nghĩa + latent GPT + giọng → mel | Đóng băng. `f0_condition: false`, nên thanh điệu được quyết định ở token ngữ nghĩa và latent GPT, tức là ở phần đồ án train |
| BigVGAN | Mel → dạng sóng | Đóng băng |
| Text-to-Emotion (Qwen) | Mô tả bằng chữ → vector cảm xúc | Không dùng: pipeline lấy cảm xúc từ câu thoại gốc |
| GRPO (mục 3.3) | Học tăng cường: sinh nhiều ứng viên, phần thưởng là CER + SS | Hướng phát triển |

Lập luận "vì sao chỉ cần train T2S": T2S là nơi duy nhất "biết đọc". Nó nhận chữ và quyết định phát âm, thanh điệu, ngắt nghỉ. Các khối sau chỉ biến token ngữ nghĩa thành âm thanh mang giọng người nói. Phần này không phụ thuộc ngôn ngữ và đã được train trên dữ liệu lớn.

- Tiếng Việt thiếu đúng một thứ: mô hình chưa biết chữ tiếng Việt đọc thế nào.
- Dấu thanh nằm sẵn trong chữ, nên không cần G2P (khác tiếng Trung hay tiếng Nhật).
- Chuẩn hoá văn bản (số, ngày tháng, đơn vị, viết tắt) phải giống hệt nhau lúc train và lúc suy luận. Hàm dùng chung: `data_prep.vi_normalize.tts_frontend`, đặt kèm `text_normalization=False`.

Hai paper còn cung cấp: RTF của 2.5 nhanh hơn IndexTTS2 khoảng 2,28 lần (theo paper 2.5). Pipeline dữ liệu ở mục 2 của paper 2.5 là cơ sở cho quy trình lọc dữ liệu của đồ án.

## 2.4 Các bản finetune cùng loại (bài học đã áp dụng)

| Bản | Mô hình gốc | Dữ liệu | Cách train | Kết quả | Bài học |
| --- | --- | --- | --- | --- | --- |
| [IndexTTS-2.5 German](https://huggingface.co/sharrnah/index-tts-2.5-german) | IndexTTS 2.5 | 310 giờ, 105.616 câu, 932 người nói (MLS 150 giờ, HUI 140 giờ, Emilia-YODAS 20 giờ) | LoRA r64/α128 trên 24 lớp GPT; train embedding văn bản và các head; hàng ngôn ngữ `de` khởi tạo từ `en`; đóng băng speaker và emotion | WER 5,35% (Whisper Small, 30 câu, 2 giọng chưa nghe); nhóm số và ngày tháng WER 15,6% | Cấu hình đồ án chép theo bản này. Checkpoint tốt nhất ở bước 16.000/19.803 (khoảng 80%), không phải bước cuối |
| [IndexTTS2-Kazakh](https://huggingface.co/TilLabs/IndexTTS2-Kazakh) | IndexTTS2 | Khoảng 4,8 GB, **1 người nói** | Thay vocab bằng BPE mới 2.000 token; 3 epoch | Mất khả năng clone giọng: luôn nói bằng giọng người trong dữ liệu | Cần dữ liệu nhiều người nói. Không thay vocab |
| [IndexTTS2 Vietnamese (dinhthuan)](https://huggingface.co/dinhthuan/index-tts-2-vietnamese) | IndexTTS2 | Không công bố | SentencePiece mới; AdamW LR 1e-5; loss text 0,2 / mel 0,8 | MOS khoảng 4,3 (tự đánh giá nội bộ); không công bố CER/SS | Baseline cần so sánh |
| [JarodMica training_v2](https://github.com/index-tts/index-tts/issues/501) | IndexTTS2 | Emilia-YODAS tiếng Nhật, 500 giờ | Mã train không chính thức | Một số câu bị lẫn âm thanh của giọng mẫu vào câu sinh ra | Viết cho bản 2, không dùng thẳng cho 2.5 được |

Bản Đức, bản dinhthuan và đồ án đều đặt trọng số loss text 0,2.

## 2.5 Các thành phần của pipeline lồng tiếng

Cần một đoạn lý thuyết ngắn cho mỗi thành phần:

| Bước | Công cụ | Lý thuyết cần trình bày |
| --- | --- | --- |
| Tách giọng / nhạc nền | Demucs `htdemucs` | Source separation, Hybrid Transformer Demucs |
| Phân đoạn người nói | pyannote `speaker-diarization-3.1` | Diarization: VAD → speaker embedding → phân cụm |
| Nhận dạng tiếng nói | WhisperX large-v3 | Whisper + forced alignment cấp từ |
| Dịch | Gemini 2.5 Flash qua OpenRouter (`google/gemini-2.5-flash`; backend `anthropic` vẫn dùng được) | MT bằng LLM, dịch theo ngữ cảnh cảnh phim, xưng hô tiếng Việt, ràng buộc độ dài |
| Sinh giọng | IndexTTS 2.5 đã finetune | Mục 2.2–2.3 |
| Căn thời lượng | `duration_factor`, rubberband (giữ formant), mượn khoảng lặng | **Isochrony** trong lồng tiếng tự động; ràng buộc số âm tiết |
| Trộn âm | pyloudnorm (−20 LUFS), ffmpeg | Chuẩn hoá loudness theo ITU-R BS.1770 |

## 2.6 Các chỉ số đánh giá

Định nghĩa đúng như mã trong `eval/metrics.py`:

| Chỉ số | Cách đo | Ghi chú cho báo cáo |
| --- | --- | --- |
| CER / WER | ASR `nvidia/parakeet-ctc-0.6b-vi` (hoặc Whisper large-v3). Văn bản qua `normalize`, viết thường, bỏ dấu câu | Tiếng Việt dùng CER làm chỉ số chính: mỗi âm tiết ngắn, nên một lỗi thanh điệu chỉ làm sai một ký tự |
| SS | Cosine giữa embedding ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`) của giọng mẫu và câu sinh ra | Thang đo hay gặp trong các paper |
| SS_WAVLM | Cosine x-vector WavLM-base-plus-sv | Điểm dồn sát 0,9+, nên chỉ dùng để so nội bộ |
| UTMOS | SpeechMOS `utmos22_strong` | **Hạn chế:** được train chủ yếu trên tiếng Anh. Phải ghi rõ trong báo cáo |
| ES | Cosine giữa embedding `emotion2vec_plus_large` của mẫu cảm xúc và câu sinh ra | |
| EMO_MATCH | Tỉ lệ câu có nhãn cảm xúc emotion2vec (5 lớp) trùng với nhãn câu mẫu | |
| RTF | Thời gian sinh / thời lượng âm thanh, trên RTX 5070 Ti | Ghi rõ loại GPU |
| Sai số thời lượng | Trung bình \|dur_vi − dur_src\| / dur_src, và % câu lệch dưới 10% | `eval/eval_dubbing.py` |
| Nhất quán giọng | SS giữa các câu của cùng một nhân vật | `eval/eval_dubbing.py` |
| Chất lượng dịch | COMET-kiwi + chấm tay độ đúng và độ tự nhiên trên 50 câu | |
| MOS chủ quan | 10–15 người nghe; chấm tự nhiên, giống giọng, cảm xúc, khớp hình (thang 1–5) | **[CHƯA CÓ]** |
