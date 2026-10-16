# local-llm: AI chạy trên máy (Ollama + Gemma 4 12B) cho việc riêng tư

Mọi thứ ở đây chạy **trên máy, không gửi dữ liệu ra ngoài**. Ollama cài ở `D:\AI\ollama` (bản zip, không đụng ổ C). Model chính: `gemma4:12b`.

## Phải bật Ollama trước
Bấm đúp `D:\AI\ollama\1-MO-giao-dien-Ollama.bat` (mở luôn trang chat `http://127.0.0.1:8765/chat.html`). Tắt hẳn: `2-TAT-Ollama.bat`. Gemma chiếm ~9,2GB VRAM khi chạy, không chạy chung được với ComfyUI/Flux. Từ 15/10/2026 model Ollama nằm ở SSD `G:\AI\ollama\models` (script khởi động đã trỏ sẵn; nạp ~6 giây thay vì ~70 giây trên HDD).

## Các script
| Script | Làm gì | Chạy |
|---|---|---|
| `fin_analyze.py` | Phân tích bảng hạch toán `.xlsx`: code tính số, Gemma diễn giải, code kiểm số AI nhắc. Xuất `.docx`, `.xlsx` (5 sheet), `.md`, `.json` đo tài nguyên | `python -I fin_analyze.py "<file.xlsx>" "<thư mục ra>" gemma4:12b` |
| `fin_facts.py` | Tính số liệu từ bảng (dùng bởi `fin_analyze.py`; chạy riêng để xem số + cảnh báo dữ liệu) | `python -I fin_facts.py` (sửa đường dẫn file trong `__main__`) |
| `job_doi_chieu.py` | CHỈ ĐỌC, không nối mạng, không dùng LLM: so bảng hạch toán với Database (`1_DATA_MASTER`) theo từng job (doanh thu, chi phí ngoài, 4 số ngày, khấu hao, lợi nhuận, đã thu). Ghép theo tên + khách + tháng (+ doanh thu trùng) vì bảng hạch toán không có Mã Job; cặp ghép không chắc bị gắn "CẦN XÁC NHẬN". In tối đa 12 dòng mỗi mục, chi tiết ra file `--ra`. Quang xuất 2 Google Sheet ra `.xlsx` trước. Đã thử bằng dữ liệu giả (`danh-gia/job_doi_chieu_test.py`); CHƯA chạy trên dữ liệu thật | `python -I job_doi_chieu.py "<hạch toán.xlsx>" "<database.xlsx>" --thang 8,9,10 --ra "<báo cáo.md>"` |
| `xlsx_read.py`, `office_min.py` | Đọc `.xlsx` / ghi `.xlsx`, `.docx` không cần thư viện ngoài (Python 3.12 của máy không có pandas/openpyxl) | được import |
| `danh-gia/zalo_summarize.py` | Tóm tắt 8 chat Zalo GIẢ, chấm tự động, có tin chứa lệnh ẩn để thử bị lừa | `python -I zalo_summarize.py 0 "<file.md ra>"` |
| `danh-gia/llm_compare.py`, `llm_eval.py` | So sánh model: tóm tắt, JSON, tính giá, gọi công cụ, định dạng, kiến thức Hải Phòng | `python -I llm_compare.py <model> "<thư mục ra>" [--old]` |
| `javis_agent.py` | Agent nhỏ: Gemma/Qwen tự chọn và gọi công cụ MCP `tool-film-maker` (tối đa 5 bước, có timeout). Công cụ chỉ-đọc tự chạy; `open_app` chỉ chạy khi thêm `--allow open_app`; `ingest_start` bị giấu hẳn. Log ở `D:\AI\ollama\ket-qua\agent\` | `python -I javis_agent.py "tìm file C8092" [--model qwen3.5:9b] [--allow open_app]` |
| `danh-gia/agent_eval.py` | Bộ thử agent: 10 ca từ câu lệnh thật + 1 ca bẫy tiêm lệnh qua tên file; chấm chọn đúng công cụ, từ chối đúng, không báo thành công giả. Tự gỡ model khỏi VRAM, dừng nếu VRAM trống < 10GB | `python -I agent_eval.py gemma4:12b` (rồi `qwen3.5:9b`) |
| `danh-gia/so_tay_eval.py` | Đo tác dụng của sổ tay về Quang (`D:\AI\ollama\so-tay-quang\profile.md`) và từ điển giọng nói (`tu-dien-giong-noi.json`): 4 tình huống, chạy không sổ (A) và có sổ (B), mỗi bên 3 lần. `javis_agent.py --no-profile` tắt cả hai | `python -I so_tay_eval.py` |
| `do-tai-nguyen/gpu_scenarios.py` (+ `job-*.ps1`) | Đo VRAM/GPU/điện khi chạy LLM + proxy NVENC, có/không `gpu-queue` | `python -I gpu_scenarios.py "<thư mục ra>" S0,S1,S2,S3` |

Dùng `python -I` (Python 3.12 của máy: `C:\Users\My PC\AppData\Local\Programs\Python\Python312\python.exe`). Ngôn ngữ hiển thị là tiếng Việt, mã nguồn comment không dấu.

## Giới hạn đã biết
- Bộ kiểm số chỉ bắt được **số không có trong dữ liệu**, không bắt được **số đúng nhưng dùng sai nghĩa** (vd Gemma từng viết "trung bình 30,5 ngày" trong khi là tổng). Luôn đọc lại bản phân tích.
- Mỗi phép đo chạy một lần; kết quả là chỉ báo, không phải thống kê chặt.
- LLM chỉ trả **văn bản**. Word/Excel do `office_min.py` ghi; đã mở thử bằng Word/Excel thật.
- PowerShell 5.1 đọc `.ps1` UTF-8 không BOM theo ANSI: **đừng đặt đường dẫn có dấu tiếng Việt trong file `.ps1`**, hãy truyền qua tham số hoặc dùng dấu `/`.
- Bộ đo phải có timeout cứng, `stdin=DEVNULL` và ghi ra file thay vì ống dẫn (lần đầu từng treo 22 phút).
- Kết quả đo/so sánh đã chạy nằm ở `D:\AI\ollama\ket-qua\` (TONG-HOP-do-tai-nguyen.md, so-sanh_*, phan-tich-tai-chinh_*, zalo-gia).
