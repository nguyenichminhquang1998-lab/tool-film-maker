# tool-film-maker

Script tự động đổ thẻ nhớ cho công việc quay dựng: **copy file từ thẻ → tự tạo folder dự án → phân loại ảnh/video → nén phần gốc (raw footage) → upload Google Drive/OneDrive → thông báo hoàn tất**.

Cốt lõi là 1 bộ script PowerShell nối các công cụ có sẵn (robocopy-style copy có retry, 7-Zip, rclone, Telegram Bot API) — có 3 cách chạy: dòng lệnh (`ingest.bat`), **giao diện cửa sổ** (`ingest-gui.bat`), hoặc **ra lệnh trực tiếp từ Claude Desktop** (`mcp_server/`) — cả ba dùng chung 1 logic nên sửa lỗi/cải tiến ở một chỗ là áp dụng cho tất cả.

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

### Cách 1 — Giao diện cửa sổ (giống app, khuyến khích)

Double-click **`ingest-gui.bat`** → mở ra 1 cửa sổ (không có cửa sổ đen cmd phía sau):

- **Tự động nhận diện thẻ nhớ** — cắm thẻ vào lúc cửa sổ đang mở, app tự quét ổ đĩa mới xuất hiện mỗi 2 giây, tự chọn sẵn trong dropdown và tự quét luôn (không cần bấm gì). Chọn thẻ khác trong dropdown, hoặc bấm **"Quet lai"**, cũng quét lại thủ công.
- Sau khi quét xong, hiện ngay: **số file** (bao nhiêu ảnh, bao nhiêu video) và **tổng dung lượng**, kèm **ước tính thời gian hoàn tất** (copy + nén + upload) — con số ước tính dựa trên tốc độ đọc thẻ/mạng *giả định* trong `ingest.config.json` (`estimatedReadSpeedMBps`, `estimatedUploadSpeedMbps`), **không phải đo thật** nên có thể chênh lệch nhiều tuỳ thẻ/mạng thực tế — chỉnh lại 2 số đó cho gần đúng tốc độ máy bạn để ước tính chuẩn hơn.
- Nhập **tên dự án**
- Chọn đích upload: Google Drive / OneDrive / Cả hai (đổi lựa chọn này cũng tự cập nhật lại số phút ước tính, vì upload cả 2 nơi mất gấp đôi thời gian upload)
- Tick "Chi copy + nen, khong upload" nếu đang không có mạng
- Bấm **"Bat dau do the"** — cửa sổ log hiển thị tiến trình trực tiếp, thanh progress chạy trong lúc xử lý, xong sẽ hiện popup kết quả (kèm cả Windows toast + Telegram như bản dòng lệnh).

Muốn có hẳn 1 file `.exe` riêng (icon riêng, không cần thấy đuôi `.ps1`/`.bat` gì cả) — đóng gói bằng `ps2exe` (miễn phí, 1 lần):

```powershell
Install-Module -Name ps2exe -Scope CurrentUser
Invoke-ps2exe -inputFile .\ingest-gui.ps1 -outputFile .\DoTheApp.exe -noConsole -title "Do The Tu Dong"
```

Sau đó double-click thẳng `DoTheApp.exe` — Windows có thể cảnh báo "Unknown Publisher" lần chạy đầu (do không có chứng chỉ ký số, bình thường với tool nội bộ) — bấm "More info → Run anyway" một lần là xong.

### Cách 2 — Dòng lệnh

Double-click **`ingest.bat`** → nhập tên dự án, ổ đĩa thẻ nhớ (vd `E:`), chọn đích upload (`drive` / `onedrive` / `both`, Enter = cả hai).

Hoặc chạy trực tiếp bằng PowerShell:

```powershell
.\ingest.ps1 -CardDrive "E:" -ProjectName "Kid dance bsixteen" -Dest both
```

Tham số thêm:
- `-ShootDate "2026-08-30"` — chỉ định ngày quay khác ngày hiện tại (mặc định dùng ngày chạy script)
- `-SkipCompress` — chỉ copy + phân loại, không nén
- `-SkipUpload` — chỉ copy + nén, không upload (ví dụ khi không có mạng tại hiện trường)

### Cách 3 — Ra lệnh trực tiếp từ Claude Desktop (MCP)

Cho phép gõ thẳng bằng tiếng Việt trong Claude Desktop kiểu "đổ thẻ E: cho dự án Kid dance bsixteen, upload cả 2 cloud" và Claude tự gọi đúng pipeline. Đây là **dự án MCP server riêng** (nằm trong `mcp_server/`), không đụng vào logic đổ thẻ đã có — chỉ là lớp cầu nối gọi lại `ingest.ps1`/`ingest.functions.ps1` qua PowerShell.

**Quan trọng:** MCP server này **bắt buộc chạy trên chính máy Windows** đang cắm thẻ nhớ/có rclone/7-Zip — không chạy được từ xa hay trên máy khác. Nếu bạn ra lệnh qua **Claude Code** (không phải Claude Desktop) đang chạy ngay trên máy đó, thì **không cần MCP** — Claude Code vốn đã chạy được PowerShell trực tiếp qua Bash, chỉ cần mở nó tại đúng folder này và gõ yêu cầu bằng tiếng Việt.

**Cài đặt 1 lần — cách nhanh (tự động):** double-click `mcp_server\setup-mcp.bat`. Script tự tìm đúng file cấu hình Claude Desktop (cả bản cài thường lẫn bản Microsoft Store — bản Store để cấu hình ở `%LOCALAPPDATA%\Packages\Claude_...`, không phải `%APPDATA%\Claude`), tự cài Python qua winget nếu thiếu, tự `pip install`, tự ghi cấu hình (sao lưu file cũ trước, giữ nguyên các MCP server khác, dừng lại không ghi đè nếu file cũ bị lỗi JSON). Xong chỉ cần Quit hẳn Claude Desktop rồi mở lại.

**Cài đặt 1 lần — cách thủ công** (nếu script tự động báo lỗi):

1. Cài Python (nếu chưa có): https://www.python.org/downloads/ — nhớ tick "Add python.exe to PATH" lúc cài.
2. Cài thư viện MCP:
   ```
   cd D:\Quang\tool-film-maker\mcp_server
   pip install -r requirements.txt
   ```
3. Mở file cấu hình Claude Desktop — Windows: `%APPDATA%\Claude\claude_desktop_config.json` (gõ đường dẫn này vào thanh địa chỉ File Explorer để mở nhanh, tạo file mới nếu chưa có). Thêm (hoặc merge nếu file đã có nội dung khác):
   ```json
   {
     "mcpServers": {
       "tool-film-maker": {
         "command": "python",
         "args": ["D:\\Quang\\tool-film-maker\\mcp_server\\server.py"]
       }
     }
   }
   ```
   (Sửa đường dẫn `D:\\Quang\\tool-film-maker` cho khớp đúng nơi bạn đã `git clone` về.)
4. Khởi động lại Claude Desktop hoàn toàn (thoát hẳn, không chỉ đóng cửa sổ — icon Claude nếu còn ở khay hệ thống thì click phải → Quit).
5. Mở lại Claude Desktop, gõ thử: *"liệt kê các thẻ nhớ đang cắm vào máy"* — nếu Claude gọi được tool và trả lời đúng, MCP đã hoạt động.

**4 tool mà Claude Desktop có thể gọi:**
- `ingest_list_drives` — liệt kê thẻ nhớ/USB đang cắm
- `ingest_scan_card` — quét nhanh 1 thẻ (chỉ đọc), báo số file/dung lượng/ước tính thời gian
- `ingest_start` — bắt đầu đổ thẻ thật (chạy nền, trả về ngay 1 `job_id`)
- `ingest_get_status` — hỏi tiến trình 1 job đang chạy bằng `job_id`

Vì đổ thẻ có thể mất nhiều phút, `ingest_start` không chờ xong mới trả lời — Claude sẽ tự gọi `ingest_get_status` lặp lại vài lần để báo bạn biết khi nào xong, giống hệt cách nó tự kiểm tra tiến trình chạy nền của chính nó.

## Cơ chế từng bước

1. **Tạo folder** — tính path theo pattern năm/tháng/ngày-tên dự án, tạo sẵn 3 subfolder `ảnh/`, `gốc/`, `music/`.
2. **Copy + phân loại** — quét toàn bộ thẻ (đệ quy), copy từng file vào `ảnh/` hoặc `gốc/` theo đuôi file (`ingest.config.json` → `photoExtensions` / `videoExtensions`). Mỗi file có retry tới 5 lần nếu thẻ đọc chậm/lag. Nếu trùng tên nhưng khác size (khác file), script tự đổi tên (`_dup1`, `_dup2`...) — **không bao giờ ghi đè âm thầm**.
3. **Xác minh (integrity check)** — so khớp số lượng file nguồn với số file đã xử lý (copy mới + đã có sẵn). Chỉ khi khớp 100%, script mới in dòng "AN TOAN de format the nho". Nếu lệch, dừng ngay, không đi tiếp nén/upload.
4. **Nén `gốc/`** — dùng 7-Zip chế độ **store** (`-mx=0`, không nén thật). Video đã là codec nén sẵn (H.264/H.265/ProRes/BRAW), nén lại gần như không giảm size mà tốn rất nhiều thời gian — store mode chỉ đóng gói thành 1 file để upload gọn, nhanh hơn nhiều lần.
5. **Upload** — `rclone copy` file nén lên cloud theo **đúng cấu trúc năm/tháng/dự án giống hệt local**: `gdrive:<cloudRootFolder>/<Năm>/tháng <X>/<ngày> - <tên dự án>/` và/hoặc `onedrive:...` tương tự (ví dụ `gdrive:Quang/2026/tháng 9/19.9.2026 - Kid dance bsixteen/`). Không đổ phẳng tất cả job vào 1 folder — sau nhiều job, cloud vẫn duyệt được theo năm/tháng như trên ổ cứng, không thành "bãi rác". Tên folder gốc trên cloud (`cloudRootFolder`, mặc định `Quang`) đổi được trong `ingest.config.json`. Trước khi upload, script kiểm tra dung lượng trống còn lại trên remote; dừng lại nếu không đủ chỗ, cảnh báo nếu sắp hết. Nếu mạng chập chờn giữa chừng (lỗi DNS/mất kết nối tạm thời), rclone tự thử lại tối đa 8 lần, mỗi lần cách nhau 15 giây (`--retries 8 --retries-sleep 15s`) trước khi báo lỗi hẳn — đủ để vượt qua hầu hết các đợt rớt mạng ngắn mà không cần chạy lại từ đầu.
6. **Thông báo** — bắn cả Windows toast (built-in, không cần cài gì) lẫn Telegram (nếu đã cấu hình) khi xong, hoặc khi có lỗi ở bất kỳ bước nào (nội dung ghi rõ "LOI do the").

Log chi tiết từng file được ghi vào `_ingest_logs/` (bị gitignore).

## An toàn dữ liệu

- Script **không bao giờ** tự động xoá hoặc format thẻ nhớ — luôn thao tác thủ công sau khi thấy dòng "AN TOAN de format the nho".
- Nếu bước copy hoặc xác minh lỗi, các bước nén/upload sẽ **không chạy tiếp** (fail-fast) để tránh xử lý dữ liệu chưa đầy đủ.
- File trùng tên khác nội dung không bao giờ bị ghi đè — luôn được đổi tên để giữ cả hai.

## Cấu trúc file trong repo

- `ingest.functions.ps1` — thư viện chứa toàn bộ logic pipeline (5 bước ở trên). Không tự chạy được, chỉ để file khác dot-source.
- `ingest.ps1` + `ingest.bat` — bản dòng lệnh, dot-source thư viện trên rồi chạy tuần tự.
- `ingest-gui.ps1` + `ingest-gui.bat` — bản giao diện cửa sổ (Windows Forms), cũng dot-source đúng thư viện đó, chạy pipeline trên 1 luồng nền (PowerShell runspace) để cửa sổ không bị "Not Responding" khi đang copy/nén file lớn, log được đẩy về giao diện qua 1 hàng đợi dùng chung (`syncHash`) mà 1 Timer đọc mỗi 200ms.
- `mcp_server/server.py` — MCP server (Python) cho Claude Desktop, gọi lại `ingest.ps1`/`ingest.functions.ps1` qua `powershell.exe` làm subprocess nền — không viết lại logic. `mcp_server/scan_card_json.ps1` là helper nhỏ dot-source `ingest.functions.ps1` để trả JSON cho tool quét thẻ.
- Sửa lỗi hay thêm tính năng cho pipeline → chỉ cần sửa `ingest.functions.ps1`, cả 3 cách chạy (CLI, GUI, MCP) đều nhận thay đổi.

## Lưu ý kỹ thuật

- Script viết cho Windows PowerShell (5.1 trở lên có sẵn trên Windows 10/11), không cần cài PowerShell 7.
- Nếu chữ tiếng Việt hiển thị lỗi (dấu `?`, ô vuông) trong console hoặc toast, mở `ingest.ps1` bằng VS Code/Notepad rồi **Save As** chọn encoding **UTF-8 with BOM** — đây là quirk quen thuộc của Windows PowerShell 5.1 khi đọc file không có BOM.
- `ingest.bat` cố tình dùng tiếng Việt không dấu ở các câu hỏi vì cửa sổ `cmd.exe` mặc định không phải UTF-8, dễ hiển thị sai nếu dùng dấu.
