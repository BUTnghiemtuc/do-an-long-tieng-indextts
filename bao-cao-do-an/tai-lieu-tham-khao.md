# Danh mục tài liệu tham khảo (nháp)

Gom từ hai tài liệu kế hoạch và từ mã nguồn. Trước khi đưa vào quyển phải điền đủ tác giả, năm và nơi công bố theo chuẩn trích dẫn của trường (IEEE hoặc APA). Mục nào ghi "[cần bổ sung]" là còn thiếu thông tin.

## Bài báo

1. IndexTTS2: A Breakthrough in Emotionally Expressive and Duration-Controlled Auto-Regressive Zero-Shot Text-to-Speech. arXiv:2506.21619. https://arxiv.org/abs/2506.21619
2. IndexTTS 2.5 Technical Report. arXiv:2601.03888. https://arxiv.org/abs/2601.03888. Các mục hay trích: mục 2 (pipeline dữ liệu), mục 3 (kiến trúc), mục 3.3 (GRPO), Bảng 1 (cách đưa ngôn ngữ vào).
3. Bài survey TTS của chính tác giả đồ án, đăng trên *Discover Artificial Intelligence*. [cần bổ sung: tên bài, số tập, năm, DOI]
4. ESD: Zhou et al., 2021. Emotional Speech Dataset. [cần bổ sung tên đầy đủ]
5. PhoAudiobook: paper gốc của bộ dữ liệu. License yêu cầu trích dẫn. [cần bổ sung]
6. ViMD: paper gốc. [cần bổ sung]
7. viVoice: trang dataset hoặc paper. [cần bổ sung]
8. LoRA: Hu et al., 2021. LoRA: Low-Rank Adaptation of Large Language Models. arXiv:2106.09685
9. Demucs / Hybrid Transformer Demucs: Rouard, Massa, Défossez, 2023. [cần bổ sung]
10. pyannote.audio 3.1. [cần bổ sung]
11. Whisper: Radford et al., 2023. WhisperX: Bain et al., 2023. [cần bổ sung]
12. ECAPA-TDNN: Desplanques et al., 2020. WavLM: Chen et al., 2022.
13. UTMOS: Saeki et al., 2022. emotion2vec: Ma et al., 2024. COMET-kiwi: Rei et al., 2022.
14. F5-TTS: Chen et al., 2024. CosyVoice; VoxCPM. [cần bổ sung, nếu đem ra so sánh]
15. ITU-R BS.1770: đo loudness (LUFS).
16. Emilia và Emilia-Pipe (Amphion). [cần bổ sung]

## Mô hình và mã nguồn

- IndexTeam/IndexTTS-2.5: https://huggingface.co/IndexTeam/IndexTTS-2.5
- index-tts (mã suy luận, đọc ở commit d9e41aa ngày 3/10/2026): https://github.com/index-tts/index-tts
- IndexTTS-2.5 German (sharrnah): https://huggingface.co/sharrnah/index-tts-2.5-german, cùng `training_config.yaml` và `evaluation_summary.json`
- IndexTTS2-Kazakh: https://huggingface.co/TilLabs/IndexTTS2-Kazakh
- IndexTTS2 Vietnamese (dinhthuan): https://huggingface.co/dinhthuan/index-tts-2-vietnamese
- Mã train IndexTTS2 không chính thức (JarodMica, issue #501): https://github.com/index-tts/index-tts/issues/501
- F5-TTS-Vietnamese-1000h: https://huggingface.co/hynt/F5-TTS-Vietnamese-ViVoice
- nvidia/parakeet-ctc-0.6b-vi; speechbrain/spkrec-ecapa-voxceleb; microsoft/wavlm-base-plus-sv; SpeechMOS utmos22_strong; emotion2vec_plus_large

## Dữ liệu

- viVoice: https://huggingface.co/datasets/capleaf/viVoice
- PhoAudiobook: https://huggingface.co/datasets/thivux/phoaudiobook
- ViMD: https://huggingface.co/datasets/nguyendv02/ViMD_Dataset
- ESD (bản trên HF: `jspaulsen/esd`)
- Đã cân nhắc nhưng không dùng: YODAS2 (https://huggingface.co/datasets/espnet/yodas2), GigaSpeech 2 (https://huggingface.co/datasets/speechcolab/gigaspeech2), Bud500 (https://huggingface.co/datasets/linhtran92/viet_bud500), Emilia (https://huggingface.co/datasets/amphion/Emilia-Dataset)
- Phim demo: Blender Open Movies, gồm *Tears of Steel* và *Sintel* (CC BY)
