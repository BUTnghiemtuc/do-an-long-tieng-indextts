# Script thí nghiệm (đã chạy thật trên RTX 5070 Ti, 10/2026)

Bản chép của các script đã chạy trong `data/` (thư mục `data/` bị gitignore). Chạy từ gốc repo,
thường trong tmux: `tmux new -s run3 "bash scripts/experiments/run3.sh 2>&1 | tee -a logs/run3.log"`.
Đường dẫn Python và thư mục dự án đang ghi cứng theo máy đã chạy; sửa `PY=` và `cd` nếu chạy máy khác.

| Script | Việc | Kết quả |
| --- | --- | --- |
| `run_prep_vimd.sh` | Lọc, chia tập, trích đặc trưng chỉ với ViMD (để overfit sớm) | `data/splits_vimd_only/` |
| `run_prep_all.sh` | Lọc viVoice + PhoAudiobook, chia tập 3 bộ, trích đặc trưng (188 giờ) | dữ liệu Run 1 |
| `bench_vram.sh` | Đo VRAM đỉnh / tốc độ các cấu hình batch, gradient checkpointing | `bao-cao-do-an/so-lieu/benchmark-vram.csv` |
| `run1.sh` | Run 1: 1 epoch, LR 5e-5 và 2e-5 | `runs/run1_lr*` |
| `eval_run1.sh` | Chấm Run 1 trên dev | `results/tts/dev_*` |
| `run2.sh` | Tải thêm dữ liệu → lọc → chia tập (371 giờ) → đặc trưng → ghép cặp → Run 2 (3 epoch) | `runs/run2` |
| `eval_run2.sh` | Chọn checkpoint Run 2 theo CER dev, test zero-shot, test cảm xúc, so với gốc/Run 1/dinhthuan | `results/tts/report_run2.md` |
| `diag_emotion.sh` | Chẩn đoán mất cảm xúc theo bước / LR | `results/tts/emo_*` |
| `run3_pilot.sh` | Run 3 thử nghiệm: cảm xúc từ câu đích p = 0,5 | `runs/run3_pilot` |
| `sweep_and_pilot2.sh` | Thử tham số giải mã + Run 3 thử nghiệm p = 1,0 | `results/tts/dec_*`, `runs/run3_pilot_p1` |
| `run3.sh` | Run 3 đầy đủ (p = 1,0, 3 epoch) + tự chấm | `results/tts/report_run3.md` |
