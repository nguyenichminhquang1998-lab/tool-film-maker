# tool-film-maker

Script tự động đổ thẻ nhớ cho công việc quay dựng: **copy file từ thẻ → tự tạo folder dự án → phân loại ảnh/video → nén phần gốc (raw footage) → upload Google Drive/OneDrive → thông báo hoàn tất**.

Không phải một app riêng — chỉ là 1 script PowerShell nối các công cụ có sẵn (robocopy-style copy có retry, 7-Zip, rclone, Telegram Bot API), chạy bằng 1 lệnh hoặc 1 click.

## Cấu trúc thư mục được tạo

```
D:\Quang\<Năm>\tháng <Tháng>\<d.M.yyyy> - <Tên dự án>\
  ảnh\      ← ảnh + raw ảnh (jpg, cr2, arw, nef, dng, raf, orf, rw2...)
  gốc\      ← video gốc (mp4, mov, mxf, braw, avi, mts...) — phần DUY NHẤT bị nén để backup
  music\    ← không đụng tới, tự thêm nhạc sau
  <Tên dự án>_goc.7z   ← file nén của gốc/, dùng để upload cloud
```

Toàn bộ file từ thẻ (dù nằm trong subfolder nào như `DCIM/100XXXXX/`) được **gộp phẳng** trực tiếp vào `ảnh/` hoặc `gốc/` theo đuôi file — không giữ nguyên cấu trúc thư mục của thẻ.

## Cài đặt một lần (trên máy Windows)

1. **rclone** (miễn phí, dùng để upload cả Google Drive lẫn OneDrive):
   - Tải tại https://rclone.org/downloads/, giải nén, thêm vào PATH.
   - Chạy `rclone config`, tạo 2 remote:
     - tên `gdrive`, loại `Google Drive`
     - tên `onedrive`, loại `Microsoft OneDrive`
   - (Tên remote phải khớp với `rcloneRemotes` trong `ingest.config.json`, mặc định đã đúng.)

2. **7-Zip** (miễn phí, dùng để đóng gói `gốc/`):
   - Tải tại https://www.7-zip.org/, cài đặt bình thường (script tự tìm ở đường dẫn cài mặc định).

3. **Telegram bot** (tuỳ chọn, để nhận thông báo qua điện thoại):
   - Chat với `@BotFather` trên Telegram → `/newbot` → lấy **bot token**.
   - Nhắn cho bot 1 tin bất kỳ, sau đó mở `https://api.telegram.org/bot<TOKEN>/getUpdates` để lấy **chat id** của mình.
   - Copy `ingest.secrets.json.example` thành `ingest.secrets.json`, điền `telegramBotToken` và `telegramChatId`. File này đã bị `.gitignore` chặn, không commit lên git.
   - Nếu bỏ qua bước này, script vẫn chạy bình thường và vẫn báo bằng thông báo Windows (toast), chỉ không gửi Telegram.

4. Kiểm tra lại `ingest.config.json` nếu `basePath` (`D:\Quang`) hoặc danh sách đuôi file ảnh/video của bạn khác mặc định.

## Chạy hằng ngày

Double-click **`ingest.bat`** → nhập tên dự án, ổ đĩa thẻ nhớ (vd `E:`), chọn đích upload (`drive` / `onedrive` / `both`, Enter = cả hai).

Hoặc chạy trực tiếp bằng PowerShell:

```powershell
.\ingest.ps1 -CardDrive "E:" -ProjectName "Kid dance bsixteen" -Dest both
```

Tham số thêm:
- `-ShootDate "2026-08-30"` — chỉ định ngày quay khác ngày hiện tại (mặc định dùng ngày chạy script)
- `-SkipCompress` — chỉ copy + phân loại, không nén
- `-SkipUpload` — chỉ copy + nén, không upload (ví dụ khi không có mạng tại hiện trường)

## Cơ chế từng bước

1. **Tạo folder** — tính path theo pattern năm/tháng/ngày-tên dự án, tạo sẵn 3 subfolder `ảnh/`, `gốc/`, `music/`.
2. **Copy + phân loại** — quét toàn bộ thẻ (đệ quy), copy từng file vào `ảnh/` hoặc `gốc/` theo đuôi file (`ingest.config.json` → `photoExtensions` / `videoExtensions`). Mỗi file có retry tới 5 lần nếu thẻ đọc chậm/lag. Nếu trùng tên nhưng khác size (khác file), script tự đổi tên (`_dup1`, `_dup2`...) — **không bao giờ ghi đè âm thầm**.
3. **Xác minh (integrity check)** — so khớp số lượng file nguồn với số file đã xử lý (copy mới + đã có sẵn). Chỉ khi khớp 100%, script mới in dòng "AN TOAN de format the nho". Nếu lệch, dừng ngay, không đi tiếp nén/upload.
4. **Nén `gốc/`** — dùng 7-Zip chế độ **store** (`-mx=0`, không nén thật). Video đã là codec nén sẵn (H.264/H.265/ProRes/BRAW), nén lại gần như không giảm size mà tốn rất nhiều thời gian — store mode chỉ đóng gói thành 1 file để upload gọn, nhanh hơn nhiều lần.
5. **Upload** — `rclone copy` file nén lên `gdrive:MediaBackup/<tên dự án>/` và/hoặc `onedrive:MediaBackup/<tên dự án>/`. Trước khi upload, script kiểm tra dung lượng trống còn lại trên remote; dừng lại nếu không đủ chỗ, cảnh báo nếu sắp hết.
6. **Thông báo** — bắn cả Windows toast (built-in, không cần cài gì) lẫn Telegram (nếu đã cấu hình) khi xong, hoặc khi có lỗi ở bất kỳ bước nào (nội dung ghi rõ "LOI do the").

Log chi tiết từng file được ghi vào `_ingest_logs/` (bị gitignore).

## An toàn dữ liệu

- Script **không bao giờ** tự động xoá hoặc format thẻ nhớ — luôn thao tác thủ công sau khi thấy dòng "AN TOAN de format the nho".
- Nếu bước copy hoặc xác minh lỗi, các bước nén/upload sẽ **không chạy tiếp** (fail-fast) để tránh xử lý dữ liệu chưa đầy đủ.
- File trùng tên khác nội dung không bao giờ bị ghi đè — luôn được đổi tên để giữ cả hai.

## Lưu ý kỹ thuật

- Script viết cho Windows PowerShell (5.1 trở lên có sẵn trên Windows 10/11), không cần cài PowerShell 7.
- Nếu chữ tiếng Việt hiển thị lỗi (dấu `?`, ô vuông) trong console hoặc toast, mở `ingest.ps1` bằng VS Code/Notepad rồi **Save As** chọn encoding **UTF-8 with BOM** — đây là quirk quen thuộc của Windows PowerShell 5.1 khi đọc file không có BOM.
- `ingest.bat` cố tình dùng tiếng Việt không dấu ở các câu hỏi vì cửa sổ `cmd.exe` mặc định không phải UTF-8, dễ hiển thị sai nếu dùng dấu.
