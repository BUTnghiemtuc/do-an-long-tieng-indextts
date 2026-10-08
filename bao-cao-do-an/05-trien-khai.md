# Tư liệu Chương 5: Triển khai

## 5.1 Môi trường

| Thành phần | Giá trị |
| --- | --- |
| GPU | NVIDIA GeForce RTX 5070 Ti 16 GB (Blackwell, sm_120), driver 580.159.03 |
| CPU / RAM | Intel Core Ultra 7 265KF (20 luồng) / 30 GB |
| Hệ điều hành | Ubuntu (Linux) |
| Python / PyTorch | 3.11 / 2.8.0+cu128. Blackwell bắt buộc PyTorch bản CUDA ≥ 12.8 |
| transformers | 4.52.1 (bản index-tts ghim) |
| index-tts | commit `d9e41aa` |
| ASR lọc dữ liệu và chấm điểm | NeMo `nvidia/parakeet-ctc-0.6b-vi` |

Các lỗi môi trường đã gặp và cách xử lý (có thể đưa vào phụ lục): xem bảng "Lỗi hay gặp" trong [docs/huong-dan-may-gpu.md](../docs/huong-dan-may-gpu.md). Ví dụ:

- xung đột protobuf giữa descript-audiotools và sentencepiece;
- NeMo kéo protobuf lên 7.x;
- lỗi `sm_120` khi dùng torch bản CUDA cũ.

## 5.2 Mã nguồn

Số dòng Python đếm ngày 07/10/2026:

| Gói | Vai trò | Số dòng |
| --- | --- | ---: |
| `vidub/` | Lõi pipeline: 8 bước, backend, dự án JSON, CLI | 1.786 |
| `server/` | FastAPI, hàng đợi job, worker, xác thực, trang quản trị, bảo mật | 1.434 (đếm 08/10) |
| `web/src/` | Giao diện React + TypeScript (không tính `node_modules`) | 5.226 dòng TS/TSX/CSS (đếm 08/10) |
| `data_prep/` | Tải, lọc, chuẩn hoá tiếng Việt, chia tập, thống kê, bộ test cảm xúc | 795 |
| `training/` | Finetune IndexTTS 2.5 (LoRA, dataset, train, export) và phương án dự phòng IndexTTS2 | 1.078 |
| `eval/` | Chỉ số TTS và lồng tiếng | 427 |
| `tests/` | Kiểm thử | 780 |

**Kiểm thử:** `pytest` thu thập **53 test** (đếm 08/10; 39 test ngày 07/10), chạy trên CPU. README và hướng dẫn GPU còn ghi 36 test, cần sửa lại. Nhóm test:

- unit (văn bản, SRT, chuẩn hoá số, công thức căn thời lượng);
- tích hợp pipeline với backend giả lập, cache;
- API (`test_server`: tải lên, sửa, tạo lại, xoá, cách ly job giữa người dùng, giới hạn upload);
- xác thực và quản trị (`test_auth`: CSRF, khoá sau 5 lần sai, chính sách mật khẩu, phân quyền, mật khẩu tạm, phiên);
- bất biến mô hình (`test_indextts25`: logit train = logit suy luận, gộp LoRA, chạy tiếp từ checkpoint, export).

## 5.3 Pipeline (CLI)

```bash
vidub run clip.mp4 -c configs/gpu.yaml -c configs/indextts25_vi.yaml   # -> runs/clip/output/clip.vi.mp4 + .srt
vidub show runs/clip                                                   # bảng câu thoại, tỉ lệ thời lượng, cảnh báo
vidub regen runs/clip --segment 12 --text "Anh chưa bao giờ nghe em cả."
vidub run runs/clip --from translate
vidub rtf runs/clip
```

**Tình trạng:** toàn bộ pipeline đã chạy với backend giả lập trên CPU (có test). Các backend thật (Demucs, pyannote, WhisperX, IndexTTS trong pipeline) **chưa chạy end-to-end trên GPU**, nên chưa có lần chạy nào trong `runs/`. Riêng IndexTTS 2.5 đã chạy thật trong `eval_tts`. **[CHƯA CÓ]**: lần chạy pipeline đầu tiên trên clip *Tears of Steel*.

Lưu ý VRAM 16 GB: pipeline nạp lần lượt WhisperX (~5 GB), pyannote, rồi IndexTTS (~6 GB). Nếu thiếu VRAM thì chạy từng bước bằng `--steps`.

## 5.4 Website

Cập nhật 08/10/2026. Giao diện React thay cho trang HTML/JS thuần (trang cũ chỉ còn là thông báo "chưa build giao diện").

**Công nghệ:** React 19 + Vite + TypeScript, Tailwind CSS v4, Motion (animation), wavesurfer.js (timeline sóng âm), font Be Vietnam Pro. Có giao diện sáng và tối, đổi bằng View Transitions API. Backend vẫn là FastAPI; `npm run build` ra `web/dist`, FastAPI phục vụ thư mục này.

**Trang và chức năng:**

| Trang | Chức năng |
| --- | --- |
| Khởi tạo (`#/setup`) | Tạo quản trị viên đầu tiên, cần mã khởi tạo in ra log server |
| Đăng nhập / Đăng ký | Ghi nhớ đăng nhập, báo Caps Lock, thước độ mạnh mật khẩu khớp chính sách server |
| Dự án của tôi | Kéo thả clip + SRT, danh sách job của mình, xoá job |
| Phòng biên tập | Tiến độ 8 bước qua SSE; bộ phát A/B (2 video đồng bộ, chuyển chéo tiếng); timeline 2 làn gốc/tiếng Việt; sửa bản dịch, đổi người nói, tạo lại 1 câu, đổi giọng mẫu, mở khoá câu; tải MP4/SRT |
| Tài khoản | Đổi tên, đổi mật khẩu, xem và đăng xuất từng thiết bị |
| Quản trị · Tổng quan | Số người dùng/job, job mỗi ngày (14 ngày), trạng thái job, GPU (nvidia-smi), ổ đĩa, đăng nhập sai 24 giờ, hoạt động gần đây |
| Quản trị · Người dùng | Thêm (mật khẩu tạm), cấp/hạ quyền, khoá/mở khoá, cấp mật khẩu tạm, buộc đăng xuất, xoá |
| Quản trị · Job / Nhật ký / Cài đặt | Mọi job kèm chủ sở hữu và dung lượng; nhật ký có lọc, phân trang; bật/tắt tự đăng ký, giới hạn upload, số job đồng thời, thời hạn phiên |

**Bảo mật** (mỗi mục có test trong `tests/test_auth.py`, `tests/test_server.py`):

| Biện pháp | Cài đặt |
| --- | --- |
| Lưu mật khẩu | scrypt (N=2^14, r=8, p=1), muối 16 byte, so sánh hằng thời gian |
| Phiên | Token 256 bit trong cookie HttpOnly + SameSite=Lax (+ Secure khi HTTPS); CSDL chỉ lưu sha256(token); hết hạn 12 giờ, hoặc 30 ngày nếu "ghi nhớ" |
| CSRF | Double-submit: cookie `vidub_csrf` phải trùng header `X-CSRF-Token` ở mọi request ghi |
| Dò mật khẩu | Khoá 15 phút sau 5 lần sai (theo email và theo IP); cùng một thông báo lỗi cho email sai và mật khẩu sai; email không tồn tại vẫn tốn thời gian băm như thường |
| Chính sách mật khẩu | ≥ 8 ký tự, có chữ và số, không phổ biến, không chứa tên email |
| Phân quyền | Vai trò `admin` / `user`; người dùng chỉ thấy job của mình (job người khác trả 404 để không lộ); không tự hạ quyền, tự khoá, tự xoá; luôn còn ít nhất 1 admin |
| Upload | Danh sách đuôi file cho phép, giới hạn dung lượng chặn sớm theo Content-Length và kiểm lại khi ghi, làm sạch tên file, giới hạn số job chưa xong mỗi người |
| Header HTTP | CSP (`script-src 'self'`), X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy, HSTS khi HTTPS; API trả `Cache-Control: no-store` |
| Nhật ký | Đăng nhập (đúng/sai), đổi mật khẩu, thao tác quản trị, tạo/xoá job, đổi cài đặt, kèm IP |
| Khôi phục | `python -m server.manage create-admin / reset-password / list-users` |

**Giới hạn nên ghi vào báo cáo:**

- Bộ đếm đăng nhập sai nằm trong bộ nhớ, chỉ đúng khi API chạy một tiến trình.
- Không có email, nên "quên mật khẩu" đi qua quản trị viên.
- Không có 2FA.

**Hàng đợi và triển khai** (giữ nguyên):

- Hàng đợi dùng Redis + RQ khi có `REDIS_URL`, nếu không thì dùng luồng nền trong API.
- `docker compose up --build`; Dockerfile có thêm một bước dùng Node để build `web/`.

**[CHƯA CÓ]**: ảnh chụp màn hình thật cho các hình 5.x. Ảnh phòng biên tập phải lấy từ một job chạy với backend thật. Ảnh đăng nhập và quản trị chụp được ngay.

## 5.5 Sản phẩm mô hình

- Checkpoint đề xuất: `checkpoints/r2_028000/`. Thư mục chứa `gpt.pth` đã gộp LoRA; các file còn lại liên kết tới IndexTTS-2.5 gốc. Để dùng trong pipeline: `cp -rL checkpoints/r2_028000 checkpoints/IndexTTS-2.5-vi`.
- **[CHƯA CÓ]**: model card gồm dữ liệu, cấu hình, kết quả và license phi thương mại theo license của dữ liệu.
