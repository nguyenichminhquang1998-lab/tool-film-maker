"""So sanh model. Dung: python llm_compare.py <model> <thu_muc_ket_qua> [--old]  (--old: chay them 6 bai cu cau 5/8/9)"""
import json, os, re, subprocess, sys, time, unicodedata, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MODEL, OUT = sys.argv[1], sys.argv[2]
WITH_OLD = "--old" in sys.argv
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:11434"
SYS_VI = "Bạn là trợ lý cho một filmmaker/production house ở Hải Phòng, Việt Nam. Trả lời bằng tiếng Việt có dấu, ngắn gọn, thực tế, dùng được ngay."

def fold(s):
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def post(path, payload, timeout=1200):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def chat(messages, think=False, tools=None, temp=0.3, ctx=16384):
    payload = {"model": MODEL, "stream": False, "think": think, "messages": messages, "options": {"num_ctx": ctx, "temperature": temp}, "keep_alive": "10m"}
    if tools: payload["tools"] = tools
    t = time.time(); r = post("/api/chat", payload); wall = time.time() - t
    toks = r.get("eval_count", 0); tps = toks / (r["eval_duration"] / 1e9) if r.get("eval_duration") else 0
    return r, {"tokens": toks, "tok_s": round(tps, 1), "wall": round(wall, 1)}

def cjk(text): return sum(1 for c in text if "一" <= c <= "鿿" or "぀" <= c <= "ヿ" or "가" <= c <= "힯")

results = []
def record(tid, group, think, answer, meta, score=None, notes=""):
    row = {"id": tid, "group": group, "think": think, "answer": answer, "cjk": cjk(answer), "score": score, "notes": notes, **meta}
    results.append(row)
    sc = "" if score is None else f" | diem {score}"
    print(f"[{tid}{'+think' if think else ''}] {meta['tokens']} tok, {meta['tok_s']} tok/s, {meta['wall']}s | CJK {row['cjk']}{sc} {notes}")

# ---------- Bai cu: cau 5, 8, 9 (chi doc thu cong) ----------
OLD = [
    ("5a", "Câu 5 - ý tưởng", "Khách là một homestay ở Cát Bà muốn làm video quảng cáo 30 giây cho mùa hè. Hãy đề xuất 3 ý tưởng khác nhau. Mỗi ý gồm: logline một câu và hình ảnh mở đầu."),
    ("5b", "Câu 5 - ý tưởng", "Tôi cần ý tưởng cho MV 3 phút của một ca sĩ indie, nhạc buồn nhẹ, quay ở Hải Phòng. Gợi ý 3 concept hình ảnh khác nhau, mỗi concept 2 đến 3 câu."),
    ("8a", "Câu 8 - prompt video AI", "Cảnh: cô gái mặc váy trắng đứng trên bãi đá Cát Bà lúc bình minh, váy bay trong gió, máy quay lia chậm từ chân lên mặt. Hãy viết prompt TIẾNG ANH cho model tạo video AI (5 giây, 16:9), kèm một dòng negative prompt, và một phiên bản ngắn hơn để tạo ảnh khung đầu bằng Flux trong ComfyUI. Chỉ đưa ra các prompt, không giải thích dài."),
    ("8b", "Câu 8 - prompt video AI", "Chuyển ý tưởng sau thành prompt TIẾNG ANH cho fal.ai image-to-video (cinematic, 5 giây): một robot cũ kỹ, gỉ sét, mở cửa quán cà phê vào buổi sáng ở phố cổ, hơi nước bốc lên từ máy pha cà phê. Nêu rõ chuyển động camera và ánh sáng. Chỉ đưa ra prompt."),
    ("9a", "Câu 9 - content social", "Viết một bài Facebook cá nhân khoảng 120 từ, giọng chân thật, hơi tự giễu, kể chuyện đi quay ở Cát Bà bị mưa cả ngày nhưng vẫn ra được cảnh đẹp. Có câu mở đầu gây tò mò, không dùng nhiều emoji, tránh lời sáo rỗng kiểu 'hành trình', 'khoảnh khắc đáng nhớ'."),
    ("9b", "Câu 9 - content social", "Viết caption TikTok tối đa 3 dòng cho video hậu trường quay phim ở Hải Phòng, giọng gần gũi, kèm đúng 5 hashtag."),
]
if WITH_OLD:
    for tid, group, q in OLD:
        r, meta = chat([{"role": "system", "content": SYS_VI}, {"role": "user", "content": q}], temp=0.7)
        record(tid, group, False, r["message"]["content"].strip(), meta)

# ---------- N1: kien thuc Hai Phong / Cat Ba (cham thu cong + vai kiem tra tu dong) ----------
q = "Cát Bà thuộc tỉnh hay thành phố nào của Việt Nam? Kể 3 địa điểm nổi tiếng ở Cát Bà và 2 địa điểm nổi tiếng ở trung tâm thành phố Hải Phòng. Chỉ nêu những gì bạn chắc chắn; nếu không chắc thì nói rõ là không chắc."
r, meta = chat([{"role": "system", "content": SYS_VI}, {"role": "user", "content": q}])
a = r["message"]["content"].strip(); f = fold(a)
bad = [w for w in ["ben nha rong", "quang ninh", "ha long", "van don", "co to"] if w in f]
record("N1", "Kiến thức Hải Phòng", False, a, meta, score="cham tay", notes=f"| nhac dia danh de sai/nham: {bad or 'khong'} | noi 'thanh pho Hai Phong': {'hai phong' in f}")

# ---------- N2: tom tat chat mau ----------
CHAT = """[09:12] Khách (chị Mai - Sunrise Homestay): Anh ơi em muốn làm video giới thiệu homestay, khoảng 45 giây.
[09:14] Khách: Quay ở Cát Bà, em muốn quay cuối tháng 11, cụ thể thứ Bảy 22/11 nhé.
[09:20] Mình: Dạ chị, anh cần biết chị có bao nhiêu phòng và muốn flycam không ạ?
[09:25] Khách: 8 phòng anh, có flycam luôn. Ngân sách em dự kiến 12 triệu.
[09:31] Mình: Với flycam và 45 giây thì anh báo 14 triệu, đã gồm hậu kỳ, nhạc có bản quyền.
[09:40] Khách: 14 hơi cao anh, bớt xuống 13 được không? Em cần xem bản dựng đầu trước thứ Sáu 28/11 để đăng quảng cáo.
[09:45] Mình: Được, 13 triệu, chị cọc 30% trước ngày 15/11. Bản dựng đầu anh gửi thứ Tư 26/11.
[09:50] Khách: Ok anh. Em chuyển cọc thứ Hai 10/11. Chỉ sửa tối đa 2 lần nha anh."""
q = "Tóm tắt đoạn chat sau thành các mục: Khách; Yêu cầu; Giá chốt; Mốc thời gian; Điều kiện. Chỉ dùng thông tin có trong chat, không thêm gì.\n\n" + CHAT
r, meta = chat([{"role": "system", "content": SYS_VI}, {"role": "user", "content": q}])
a = r["message"]["content"].strip(); f = fold(a)
facts = {"ten khach (Mai/Sunrise)": ("mai" in f and "sunrise" in f), "quay 22/11": "22/11" in f, "45 giay": "45" in f, "gia chot 13 trieu": bool(re.search(r"13\s*(trieu|tr\b)", f)), "coc 30%": "30%" in f, "han coc 15/11": "15/11" in f, "ban dung dau 26/11": "26/11" in f, "khach can truoc 28/11": "28/11" in f, "sua toi da 2 lan": bool(re.search(r"(2|hai)\s*lan", f)), "8 phong": bool(re.search(r"8\s*phong", f))}
wrong_final = bool(re.search(r"gia (chot|cuoi|thoa thuan)[^.\n]{0,25}14\s*trieu", f))
got = sum(facts.values())
record("N2", "Tóm tắt chat mẫu", False, a, meta, score=f"{got}/{len(facts)} ý đúng", notes=f"| thieu: {[k for k, v in facts.items() if not v] or 'khong'} | ghi sai gia chot=14: {wrong_final}")

# ---------- N3: trich so lieu -> JSON ----------
TABLE = """Job A (TVC quán cà phê): doanh thu 18.000.000; chi phí: nhân công 5.400.000, thiết bị 2.000.000, hậu kỳ 3.000.000.
Job B (MV ca sĩ indie): doanh thu 9.500.000; chi phí: nhân công 2.400.000, hậu kỳ 2.500.000, di chuyển 600.000.
Job C (phim giới thiệu resort): doanh thu 30.000.000; chi phí: nhân công 9.000.000, thiết bị 4.500.000, hậu kỳ 6.000.000, âm nhạc 1.500.000."""
q = ('Từ dữ liệu sau, tính tổng chi phí, lợi nhuận và biên lợi nhuận (% lợi nhuận trên doanh thu, làm tròn 1 chữ số thập phân) cho từng job và cho tổng cộng. '
     'Trả về DUY NHẤT một JSON hợp lệ, không giải thích, theo mẫu: {"jobs":[{"ten":"A","doanh_thu":0,"tong_chi_phi":0,"loi_nhuan":0,"bien_loi_nhuan_pct":0.0}],"tong":{"doanh_thu":0,"tong_chi_phi":0,"loi_nhuan":0,"bien_loi_nhuan_pct":0.0}}. Số tiền là số nguyên đồng.\n\n' + TABLE)
EXP = {"A": (18_000_000, 10_400_000, 7_600_000, 42.2), "B": (9_500_000, 5_500_000, 4_000_000, 42.1), "C": (30_000_000, 21_000_000, 9_000_000, 30.0)}
EXP_T = (57_500_000, 36_900_000, 20_600_000, 35.8)
def score_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m: return "khong co JSON", 0, 7
    try: j = json.loads(m.group(0))
    except Exception as e: return "JSON hong", 0, 7
    ok = tot = 0
    def chk(got, want, tol):
        nonlocal ok, tot; tot += 1
        try: ok += abs(float(got) - want) <= tol
        except Exception: pass
    jobs = {str(x.get("ten", "")).strip().upper()[-1:]: x for x in j.get("jobs", []) if x.get("ten")}
    for k, (dt, cp, ln, bp) in EXP.items():
        x = jobs.get(k, {}); chk(x.get("tong_chi_phi"), cp, 1); chk(x.get("loi_nhuan"), ln, 1); chk(x.get("bien_loi_nhuan_pct"), bp, 0.15)
    t = j.get("tong", {}); chk(t.get("tong_chi_phi"), EXP_T[1], 1); chk(t.get("loi_nhuan"), EXP_T[2], 1); chk(t.get("bien_loi_nhuan_pct"), EXP_T[3], 0.15)
    return "JSON hop le", ok, tot
for think in (False, True):
    r, meta = chat([{"role": "system", "content": SYS_VI}, {"role": "user", "content": q}], think=think, temp=0.1)
    a = r["message"]["content"].strip(); st, ok, tot = score_json(a)
    record("N3", "Trích số liệu -> JSON", think, a, meta, score=f"{ok}/{tot} số đúng", notes=f"| {st}")

# ---------- N4: goi cong cu (vai tro 'le tan') ----------
TOOLS = [
    {"type": "function", "function": {"name": "open_app", "description": "Mở một ứng dụng trên máy tính (Resolve, Premiere, After Effects, Blender, Zalo, Chrome...)", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Tên app"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "find_file", "description": "Tìm file hoặc thư mục theo tên trên các ổ đĩa", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Từ khóa trong tên"}, "extension": {"type": "string", "description": "Đuôi file, vd mp4, pdf"}, "all_drives": {"type": "boolean", "description": "true nếu muốn quét mọi ổ"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "pc_status", "description": "Xem tình trạng máy: GPU, VRAM, ổ đĩa, việc đang chạy", "parameters": {"type": "object", "properties": {}}}},
]
def call_of(r): return [(c["function"]["name"], c["function"].get("arguments", {})) for c in (r["message"].get("tool_calls") or [])]
CASES = [
    ("mở DaVinci Resolve lên cho tôi", lambda cs: any(n == "open_app" and any(k in fold(str(a.get("name", ""))) for k in ("resolve", "davinci")) for n, a in cs)),
    ("tìm giúp tôi file hợp đồng Cát Bà Pathfinder định dạng pdf", lambda cs: any(n == "find_file" and str(a.get("extension", "")).lower().lstrip(".") == "pdf" and any(k in fold(str(a.get("query", ""))) for k in ("pathfinder", "hop dong")) for n, a in cs)),
    ("mở premiere", lambda cs: any(n == "open_app" and "premiere" in fold(str(a.get("name", ""))) for n, a in cs)),
    ("máy tính của tôi còn bao nhiêu VRAM trống?", lambda cs: any(n == "pc_status" for n, a in cs)),
    ("hôm nay trời đẹp nhỉ", lambda cs: len(cs) == 0),
    ("viết cho tôi bài Facebook về chuyến quay hôm qua", lambda cs: len(cs) == 0),
    ("tìm file C8092", lambda cs: any(n == "find_file" and "c8092" in fold(str(a.get("query", ""))) for n, a in cs)),
    ("mở Zalo và After Effects", lambda cs: sum(1 for n, a in cs if n == "open_app" and any(k in fold(str(a.get("name", ""))) for k in ("zalo", "after effects"))) >= 2),
    ("tìm tất cả video mp4 có chữ Pathfinder trên mọi ổ đĩa", lambda cs: any(n == "find_file" and "pathfinder" in fold(str(a.get("query", ""))) and str(a.get("extension", "")).lower().lstrip(".") == "mp4" and a.get("all_drives") in (True, "true") for n, a in cs)),
    ("xóa hết file trong thư mục Downloads giúp tôi", lambda cs: len(cs) == 0),
]
ok = 0; tt = 0; log = []; t0 = time.time()
for text, check in CASES:
    r, meta = chat([{"role": "system", "content": "Bạn là lễ tân của Javis. Nếu yêu cầu khớp một công cụ thì gọi công cụ đó; nếu không (trò chuyện, viết nội dung, hoặc việc không có công cụ) thì KHÔNG gọi công cụ và trả lời ngắn gọn."}, {"role": "user", "content": text}], tools=TOOLS, temp=0.0)
    cs = call_of(r); good = bool(check(cs)); ok += good; tt += meta["tokens"]
    log.append(f"{'ĐÚNG' if good else 'SAI '} | {text} -> {cs if cs else 'không gọi công cụ'}")
meta = {"tokens": tt, "tok_s": 0, "wall": round(time.time() - t0, 1)}
record("N4", "Gọi công cụ (lễ tân)", False, "\n".join(log), meta, score=f"{ok}/{len(CASES)} đúng")

# ---------- N5: lam dung dinh dang ----------
q = "Liệt kê đúng 5 gạch đầu dòng (dùng dấu -) những việc cần chuẩn bị trước ngày quay ngoài trời. Mỗi gạch tối đa 8 từ. Không dùng emoji, không có câu mở đầu hay kết luận."
r, meta = chat([{"role": "system", "content": SYS_VI}, {"role": "user", "content": q}])
a = r["message"]["content"].strip(); lines = [l for l in a.splitlines() if l.strip()]
bul = [l for l in lines if l.lstrip().startswith("-")]; longest = max((len(l.lstrip("- ").split()) for l in bul), default=0)
emoji = bool(re.search(r"[\U0001F300-\U0001FAFF☀-➿]", a))
passed = len(bul) == 5 and len(lines) == 5 and longest <= 8 and not emoji
record("N5", "Làm đúng định dạng", False, a, meta, score="ĐẠT" if passed else "TRƯỢT", notes=f"| {len(bul)} gach, {len(lines)} dong, dai nhat {longest} tu, emoji={emoji}")

# ---------- N6: tinh gia ----------
q = ("Một dự án quay 3 ngày, mỗi ngày 2 người, giá nhân công 1,2 triệu/người/ngày. Thuê thiết bị 3 triệu, hậu kỳ 4,5 triệu. "
     "Tôi muốn lợi nhuận bằng 20% trên GIÁ BÁN (không phải trên chi phí). Giá bán phải là bao nhiêu? Trình bày các bước ngắn gọn rồi ghi kết quả cuối cùng.")
for think in (False, True):
    r, meta = chat([{"role": "system", "content": SYS_VI}, {"role": "user", "content": q}], think=think, temp=0.1)
    a = r["message"]["content"].strip(); f = a.replace(" ", "")
    right = bool(re.search(r"18[,.]375|18[,.]4(?!\d)|18\.375\.000|18375000", f))
    record("N6", "Tính giá (đáp án 18,375 triệu)", think, a, meta, score="ĐÚNG" if right else "SAI")

with open(os.path.join(OUT, "so_sanh.json"), "w", encoding="utf-8") as fh: json.dump(results, fh, ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "so_sanh.md"), "w", encoding="utf-8") as fh:
    fh.write(f"# {MODEL} (15/10/2026)\n\n")
    for x in results:
        fh.write(f"## [{x['id']}] {x['group']} (thinking={x['think']}) — {x['score']} {x['notes']}\n\n{x['answer']}\n\n_({x['tokens']} token, {x['tok_s']} tok/s, {x['wall']}s)_\n\n---\n\n")
used = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
ps = json.load(urllib.request.urlopen(BASE + "/api/ps"))["models"]
for m in ps: print(f"Nạp: {m['name']} | {m['size']/1e9:.1f} GB, trong VRAM {m['size_vram']/1e9:.1f} GB ({100*m['size_vram']/m['size']:.0f}%) | VRAM cả GPU: {used}")
post("/api/generate", {"model": MODEL, "keep_alive": 0}, timeout=60)
print("Da luu:", OUT)
