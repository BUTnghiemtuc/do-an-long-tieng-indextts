# Tư liệu viết quyển đồ án

Thư mục này gom mọi nội dung cần để viết quyển đồ án tốt nghiệp **"Lồng tiếng phim tự động sang tiếng Việt với IndexTTS"**. Mỗi file tương ứng một chương. Trong mỗi file có:

- số liệu thật, trích từ log và kết quả trong repo (kèm đường dẫn nguồn để kiểm lại);
- các ý đã chốt trong kế hoạch;
- chỗ còn thiếu, đánh dấu **[CHƯA CÓ]**.

Cập nhật lần cuối: 07/10/2026, sau khi Run 2, Run 3 thử nghiệm và một phần sweep giải mã đã xong.

## Cấu trúc

| File / thư mục | Nội dung |
| --- | --- |
| [00-dan-y-va-lich.md](00-dan-y-va-lich.md) | Dàn ý 7 chương, hạn từng chương, tư liệu nào dùng cho mục nào |
| [01-gioi-thieu.md](01-gioi-thieu.md) | Bài toán, mục tiêu, phạm vi, đóng góp |
| [02-co-so-ly-thuyet.md](02-co-so-ly-thuyet.md) | IndexTTS2 / 2.5, các thành phần pipeline, các bản finetune cùng loại |
| [03-thiet-ke-he-thong.md](03-thiet-ke-he-thong.md) | Tóm tắt thiết kế và tham số; dàn ý chi tiết nằm ở [docs/ke-hoach-chuong-3-thiet-ke-he-thong.md](../docs/ke-hoach-chuong-3-thiet-ke-he-thong.md) |
| [04-finetune-indextts.md](04-finetune-indextts.md) | Dữ liệu, phễu lọc, cấu hình, các lần train, VRAM, đường loss |
| [05-trien-khai.md](05-trien-khai.md) | Mã nguồn, kiểm thử, CLI, website, môi trường máy |
| [06-thuc-nghiem.md](06-thuc-nghiem.md) | Bảng kết quả, nhận xét, phân tích lỗi, thí nghiệm đang chạy |
| [07-ket-luan.md](07-ket-luan.md) | Kết quả đạt được, hạn chế, hướng phát triển |
| [tai-lieu-tham-khao.md](tai-lieu-tham-khao.md) | Danh mục tài liệu tham khảo |
| [viec-con-thieu.md](viec-con-thieu.md) | Checklist việc phải làm thêm để đủ nội dung |
| [so-lieu/](so-lieu/) | Dữ liệu thô cho bảng và hình: CSV đường loss, phễu lọc, benchmark VRAM, điểm từng câu |
| [am-thanh-mau/](am-thanh-mau/) | File nghe thử: model gốc và bản overfit trên cùng câu |

## File trong `so-lieu/`

| File | Dùng cho |
| --- | --- |
| `tong-hop-danh-gia-tts.csv` | Mọi lần chấm (29 hệ thống): CER, WER, SS, SS_WAVLM, UTMOS, ES, EMO_MATCH, RTF |
| `ket-qua-run2.md` | Bảng kết quả chính do `data/eval_run2.sh` sinh ra |
| `ket-qua-tts/*.csv` | Điểm từng câu của các hệ thống chính, dùng để phân tích lỗi |
| `duong-loss-train.csv`, `duong-loss-dev.csv` | Vẽ đường loss của overfit, Run 1 (2 mức LR), Run 2, Run 3 thử nghiệm |
| `pheu-loc-du-lieu.csv` | Hình hoặc bảng phễu lọc dữ liệu |
| `benchmark-vram.csv` | Bảng chọn batch size cho GPU 16 GB |
| `thong-ke-du-lieu-train.md` | Thống kê tập train (bản sao của [docs/data_stats.md](../docs/data_stats.md)) |
| `overfit-cer-6-cau.json` | Văn bản gốc, kết quả ASR và CER của 6 câu overfit: model gốc so với bản overfit |

## Nguồn gốc

- Kế hoạch 8 tuần (Claude Docs): https://claude.ai/code/artifact/4d983aba-1013-4f99-850e-6a397bf85737
- Kế hoạch finetune (Claude Docs): https://claude.ai/code/artifact/7366d741-b2d8-4944-b6e6-06a47ad8c5d1
- Log: `logs/*.log`, `runs/*/log.jsonl`. Kết quả: `results/tts/*/summary.json`. Script thí nghiệm: `data/*.sh`.

Sau mỗi thí nghiệm mới:

1. Chạy `/home/thor/miniconda3/envs/vidub/bin/python bao-cao-do-an/cap_nhat_so_lieu.py` để làm mới CSV và các bản sao trong `so-lieu/`.
2. Sửa tay các bảng trong [06-thuc-nghiem.md](06-thuc-nghiem.md).
3. Đánh dấu việc đã xong trong [viec-con-thieu.md](viec-con-thieu.md).
