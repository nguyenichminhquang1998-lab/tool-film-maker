"""Phan tich bang hach toan bang LLM local. Dung: python fin_analyze.py <xlsx> <thu_muc_ra> [model]"""
import ctypes, datetime as dt, json, os, re, statistics, subprocess, sys, threading, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import fin_facts
from office_min import write_docx, write_xlsx

SRC, OUT = sys.argv[1], sys.argv[2]
MODEL = sys.argv[3] if len(sys.argv) > 3 else "gemma4:12b"
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:11434"

# ---------- 1. so lieu (code tinh) ----------
rows = fin_facts.load(SRC)
F = fin_facts.facts(rows)
M = lambda v: round(v / 1e6, 1)  # trieu dong
tot = F["tong"]

unpaid = [d for d in rows if d["doanh_thu_n"] and not d["thuc_nhan_n"]]
unpaid_sum = sum(d["doanh_thu_n"] for d in unpaid)
waits = [x["so_ngay_cho_tien"] for x in F["du_an"] if x["so_ngay_cho_tien"] is not None and x["so_ngay_cho_tien"] >= 0]
alloc_cols = [("quy_thiet_bi_n", "Quỹ thiết bị"), ("sinh_hoat_n", "Sinh hoạt (35%)"), ("tiet_kiem_n", "Tiết kiệm phòng thủ (25%)"), ("co_phieu_n", "Tích lũy mua cổ phiếu (18%)"), ("bo_me_n", "Gửi bố mẹ (17%)"), ("phat_trien_n", "Phát triển bản thân (5%)"), ("quy_khac_n", "Quỹ tự do khác / tiền thừa")]
alloc = [(label, sum(d[k] for d in rows)) for k, label in alloc_cols]
by_rev = sorted(F["du_an"], key=lambda x: -x["doanh_thu"])[:5]
low_margin = sorted([x for x in F["du_an"] if x["bien_pct"] is not None and x["doanh_thu"] > 0], key=lambda x: x["bien_pct"])[:5]
days_jobs = [x for x in F["du_an"] if x["ngay_dung"]]
profit_per_day = round(sum(x["loi_nhuan"] for x in days_jobs) / sum(x["ngay_dung"] for x in days_jobs)) if days_jobs else None

lines = [f"TỔNG CỘNG {tot['so_du_an']} dự án: doanh thu {M(tot['doanh_thu'])} triệu; chi phí ngoài {M(tot['chi_phi_ngoai'])} triệu; khấu hao thiết bị {M(tot['khau_hao'])} triệu; lợi nhuận thuần {M(tot['loi_nhuan'])} triệu (biên {tot['bien_pct']}%); thực nhận {M(tot['thuc_nhan'])} triệu; chưa thu {M(unpaid_sum)} triệu ({round(100*unpaid_sum/tot['doanh_thu'],1)}% doanh thu); tổng {tot['ngay_dung']} ngày dựng PC.",
         f"Doanh thu trung bình mỗi dự án: {M(tot['doanh_thu']/tot['so_du_an'])} triệu."]
if profit_per_day: lines.append(f"Lợi nhuận trung bình mỗi ngày dựng PC (chỉ các dự án có ghi số ngày dựng): {M(profit_per_day)} triệu.")
if waits: lines.append(f"Thời gian chờ tiền về (các dự án có đủ 2 ngày): trung bình {round(statistics.mean(waits))} ngày, trung vị {round(statistics.median(waits))} ngày, dài nhất {max(waits)} ngày (n={len(waits)}).")
lines.append("\nTHEO THÁNG (triệu đồng):")
for m in F["theo_thang"]:
    lines.append(f"- {m['thang']}: {m['so_du_an']} dự án | doanh thu {M(m['doanh_thu'])} | chi phí ngoài {M(m['chi_phi_ngoai'])} | khấu hao {M(m['khau_hao'])} | lợi nhuận {M(m['loi_nhuan'])} | biên {m['bien_pct']}% | thực nhận {M(m['thuc_nhan'])} | chưa thu {M(m['chua_thu'])}")
lines.append("\nKHOẢN CHƯA THU:")
for d in unpaid: lines.append(f"- {d['sheet']} · {d['du_an']}: {M(d['doanh_thu_n'])} triệu · tình trạng: {d['cong_no_s'] or 'để trống'}")
lines.append("\n5 DỰ ÁN DOANH THU CAO NHẤT: " + "; ".join(f"{x['du_an']} ({x['thang']}) {M(x['doanh_thu'])} triệu" for x in by_rev))
lines.append("5 DỰ ÁN BIÊN LỢI NHUẬN THẤP NHẤT: " + "; ".join(f"{x['du_an']} ({x['thang']}) biên {x['bien_pct']}%" for x in low_margin))
lines.append("\nLỢI NHUẬN ĐƯỢC PHÂN BỔ VÀO CÁC QUỸ (triệu đồng): " + "; ".join(f"{k} {M(v)}" for k, v in alloc))
lines.append("\nLỖI/NGHI VẤN TRONG DỮ LIỆU (do code kiểm tra):")
lines += [f"- {c}" for c in F["canh_bao"]]
facts_text = "\n".join(lines)

# ---------- 2. LLM dien giai ----------
SYS = ("Bạn là trợ lý phân tích vận hành cho một filmmaker freelance ở Hải Phòng. Bạn chỉ DIỄN GIẢI số liệu đã được tính sẵn. "
       "QUY TẮC: (1) Chỉ dùng đúng các con số có trong dữ liệu; không tự cộng, trừ, nhân, chia ra số mới. Nếu cần so sánh thì dùng lời (cao hơn, thấp hơn, gấp đôi...) hoặc trích số có sẵn. "
       "(2) Mọi số tiền ghi theo 'triệu đồng' như dữ liệu. (3) Không đưa lời khuyên đầu tư (không nói nên mua gì, bao nhiêu); chỉ mô tả cách tiền được phân bổ. "
       "(4) Nếu thiếu dữ liệu thì nói rõ 'chưa có dữ liệu'. (5) Tiếng Việt có dấu, ngắn gọn, thực tế.")
USER = ("Dưới đây là số liệu đã tính sẵn từ bảng hạch toán thu chi. Hãy viết bản phân tích gồm đúng 5 mục, đánh số và đặt tiêu đề rõ:\n"
        "1. Tổng quan (3 đến 4 câu)\n2. Điểm đáng chú ý (3 gạch đầu dòng)\n3. Rủi ro và cảnh báo (công nợ, dữ liệu nhập sai; nêu cụ thể dự án)\n"
        "4. Việc nên làm trong 30 ngày tới (3 đến 5 việc cụ thể, đánh số)\n5. Câu hỏi cần tôi xác nhận (2 đến 3 câu hỏi về dữ liệu còn mơ hồ)\n\nSỐ LIỆU:\n" + facts_text)

def mem_available_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
    s = MS(); s.dwLength = ctypes.sizeof(s); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)); return s.ullAvailPhys / 1e9

samples = []; stop = threading.Event()
def sampler():
    while not stop.is_set():
        o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu,power.draw,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip().split(",")
        try: samples.append((float(o[0]), float(o[1]), float(o[2]), float(o[3]), mem_available_gb()))
        except Exception: pass
        time.sleep(0.4)
base_ram = mem_available_gb(); base = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip()
th = threading.Thread(target=sampler, daemon=True); th.start()
t0 = time.time()
payload = {"model": MODEL, "stream": False, "think": False, "keep_alive": "5m", "options": {"num_ctx": 16384, "temperature": 0.3},
           "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": USER}]}
req = urllib.request.Request(BASE + "/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
resp = json.load(urllib.request.urlopen(req, timeout=900))
wall = time.time() - t0; stop.set(); th.join()
analysis = resp["message"]["content"].strip()
res = {"model": MODEL, "wall_sec": round(wall, 1), "tokens_in": resp.get("prompt_eval_count"), "tokens_out": resp.get("eval_count"),
       "tok_s": round(resp["eval_count"] / (resp["eval_duration"] / 1e9), 1), "vram_base_mib": float(base),
       "vram_peak_mib": max(s[0] for s in samples), "gpu_util_peak_pct": max(s[1] for s in samples), "power_peak_w": max(s[2] for s in samples),
       "temp_peak_c": max(s[3] for s in samples), "ram_free_base_gb": round(base_ram, 1), "ram_free_min_gb": round(min(s[4] for s in samples), 1)}
print("TAI NGUYEN:", json.dumps(res, ensure_ascii=False))

# ---------- 3. kiem tra so lieu AI nhac ----------
def nums(text): return {x.replace(",", ".") for x in re.findall(r"\d+(?:[.,]\d+)?", text)}
allowed = nums(facts_text)
for x in list(allowed):
    try: f = float(x); allowed |= {str(round(f, 1)), str(int(round(f))), f"{f:.1f}", f"{f:.2f}"}
    except ValueError: pass
used = [x for x in nums(analysis) if (len(x.replace(".", "")) >= 2 or "." in x)]
unverified = sorted(x for x in used if x not in allowed and x not in {"2026", "30", "100"})
print("So AI nhac:", len(used), "| chua khop du lieu:", unverified)

# ---------- 4. xuat file ----------
stamp = dt.date.today().isoformat()
md = [f"# Phân tích tài chính từ bảng hạch toán ({stamp})", f"_Số liệu do code tính; phần diễn giải do {MODEL} chạy trên máy bạn, không gửi ra ngoài._", "", "## Phân tích của AI", analysis, "",
      "## Số liệu gốc đã tính", "```", facts_text, "```", "", "## Số AI nhắc nhưng không có trong dữ liệu (cần kiểm tay)", ", ".join(unverified) or "(không có)"]
open(os.path.join(OUT, "bao-cao.md"), "w", encoding="utf-8").write("\n".join(md))

blocks = [("h1", "Phân tích tài chính từ bảng hạch toán"), ("note", f"Ngày {stamp}. Số liệu do code tính từ file của bạn; phần diễn giải do {MODEL} chạy trên máy bạn. Chỉ để tham khảo vận hành, không phải tư vấn đầu tư.")]
for ln in analysis.splitlines():
    s = ln.rstrip()
    if not s.strip(): continue
    if re.match(r"^\s*(#{1,3}\s+|\*\*\d+\.)", s) or re.match(r"^\s*\d+\.\s+\*\*", s) and len(s) < 90: blocks.append(("h2", re.sub(r"[#*]", "", s).strip()))
    elif re.match(r"^\s*[-*•]\s+", s): blocks.append(("bullet", re.sub(r"^\s*[-*•]\s+", "", s)))
    elif re.match(r"^\s*\d+\.\s+", s): blocks.append(("bullet", s.strip()))
    else: blocks.append(("p", s.strip()))
blocks += [("h2", "Bảng tổng hợp theo tháng (triệu đồng)"), ("table", [["Tháng", "Dự án", "Doanh thu", "Chi phí ngoài", "Khấu hao", "Lợi nhuận", "Biên %", "Thực nhận", "Chưa thu"]] +
           [[m["thang"], m["so_du_an"], M(m["doanh_thu"]), M(m["chi_phi_ngoai"]), M(m["khau_hao"]), M(m["loi_nhuan"]), m["bien_pct"], M(m["thuc_nhan"]), M(m["chua_thu"])] for m in F["theo_thang"]] +
           [["Tổng", tot["so_du_an"], M(tot["doanh_thu"]), M(tot["chi_phi_ngoai"]), M(tot["khau_hao"]), M(tot["loi_nhuan"]), tot["bien_pct"], M(tot["thuc_nhan"]), M(unpaid_sum)]]),
           ("h2", "Cảnh báo chất lượng dữ liệu (do code kiểm tra)")] + [("bullet", c) for c in F["canh_bao"]]
blocks += [("h2", "Số AI nhắc nhưng không có trong dữ liệu (cần kiểm tay)"), ("p", ", ".join(unverified) or "Không có.")]
write_docx(os.path.join(OUT, "bao-cao.docx"), blocks)

sheets = {
    "Tổng hợp tháng": [["Tháng", "Số dự án", "Doanh thu", "Chi phí ngoài", "Khấu hao", "Lợi nhuận", "Biên %", "Thực nhận", "Ngày dựng", "Chưa thu"]] +
        [[m["thang"], m["so_du_an"], m["doanh_thu"], m["chi_phi_ngoai"], m["khau_hao"], m["loi_nhuan"], m["bien_pct"], m["thuc_nhan"], m["ngay_dung"], m["chua_thu"]] for m in F["theo_thang"]] +
        [["Tổng", tot["so_du_an"], tot["doanh_thu"], tot["chi_phi_ngoai"], tot["khau_hao"], tot["loi_nhuan"], tot["bien_pct"], tot["thuc_nhan"], tot["ngay_dung"], unpaid_sum]],
    "Theo dự án": [["Tháng", "Dự án", "Doanh thu", "Chi phí ngoài", "Khấu hao", "Lợi nhuận", "Biên %", "Ngày dựng", "LN mỗi ngày dựng", "Thực nhận", "Công nợ", "Số ngày chờ tiền"]] +
        [[x["thang"], x["du_an"], x["doanh_thu"], x["chi_phi_ngoai"], x["khau_hao"], x["loi_nhuan"], x["bien_pct"], x["ngay_dung"], x["loi_nhuan_moi_ngay_dung"], x["thuc_nhan"], x["cong_no"], x["so_ngay_cho_tien"]] for x in F["du_an"]],
    "Phân bổ quỹ": [["Quỹ", "Tổng (đồng)"]] + [[k, v] for k, v in alloc],
    "Cảnh báo dữ liệu": [["Cảnh báo"]] + [[c] for c in F["canh_bao"]],
    "Phân tích của AI": [["Nội dung (do " + MODEL + " viết)"]] + [[l] for l in analysis.splitlines() if l.strip()],
}
write_xlsx(os.path.join(OUT, "so-lieu-va-phan-tich.xlsx"), sheets, widths={"Tổng hợp tháng": [10, 10, 14, 14, 12, 14, 8, 14, 10, 12], "Theo dự án": [9, 32, 14, 14, 12, 14, 8, 10, 14, 14, 20, 12], "Phân bổ quỹ": [34, 16], "Cảnh báo dữ liệu": [120], "Phân tích của AI": [140]})
json.dump({"resource": res, "unverified_numbers": unverified, "facts_chars": len(facts_text)}, open(os.path.join(OUT, "do-tai-nguyen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Da xuat:", [f for f in os.listdir(OUT)])
