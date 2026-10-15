"""Chay thu LLM local tren cac cau 5, 8, 9 cua Quang. Dung: python llm_eval.py <model> <thu_muc_ket_qua>"""
import json, os, re, subprocess, sys, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MODEL = sys.argv[1]
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:11434"

SYS = "Ban la tro ly cho mot filmmaker/production house o Hai Phong, Viet Nam. Tra loi ngan gon, thuc te, de dung ngay."
SYS_VI = "Bạn là trợ lý cho một filmmaker/production house ở Hải Phòng, Việt Nam. Trả lời bằng tiếng Việt có dấu, ngắn gọn, thực tế, dùng được ngay."

TASKS = [
    # (id, nhom, yeu cau ngon ngu dau ra, noi dung)
    ("5a", "Câu 5 - ý tưởng", "vi", "Khách là một homestay ở Cát Bà muốn làm video quảng cáo 30 giây cho mùa hè. Hãy đề xuất 3 ý tưởng khác nhau. Mỗi ý gồm: logline một câu và hình ảnh mở đầu."),
    ("5b", "Câu 5 - ý tưởng", "vi", "Tôi cần ý tưởng cho MV 3 phút của một ca sĩ indie, nhạc buồn nhẹ, quay ở Hải Phòng. Gợi ý 3 concept hình ảnh khác nhau, mỗi concept 2 đến 3 câu."),
    ("8a", "Câu 8 - viết prompt video AI", "en", "Cảnh: cô gái mặc váy trắng đứng trên bãi đá Cát Bà lúc bình minh, váy bay trong gió, máy quay lia chậm từ chân lên mặt. Hãy viết prompt TIẾNG ANH cho model tạo video AI (5 giây, 16:9), kèm một dòng negative prompt, và một phiên bản ngắn hơn để tạo ảnh khung đầu bằng Flux trong ComfyUI. Chỉ đưa ra các prompt, không giải thích dài."),
    ("8b", "Câu 8 - viết prompt video AI", "en", "Chuyển ý tưởng sau thành prompt TIẾNG ANH cho fal.ai image-to-video (cinematic, 5 giây): một robot cũ kỹ, gỉ sét, mở cửa quán cà phê vào buổi sáng ở phố cổ, hơi nước bốc lên từ máy pha cà phê. Nêu rõ chuyển động camera và ánh sáng. Chỉ đưa ra prompt."),
    ("9a", "Câu 9 - content social", "vi", "Viết một bài Facebook cá nhân khoảng 120 từ, giọng chân thật, hơi tự giễu, kể chuyện đi quay ở Cát Bà bị mưa cả ngày nhưng vẫn ra được cảnh đẹp. Có câu mở đầu gây tò mò, không dùng nhiều emoji, tránh lời sáo rỗng kiểu 'hành trình', 'khoảnh khắc đáng nhớ'."),
    ("9b", "Câu 9 - content social", "vi", "Viết caption TikTok tối đa 3 dòng cho video hậu trường quay phim ở Hải Phòng, giọng gần gũi, kèm đúng 5 hashtag."),
]

def post(path, payload, timeout=900):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=30))

def vram():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip()
    used, total = [int(x) for x in out.split(",")]
    return used, total

def stats(text, lang):
    letters = [c for c in text if c.isalpha()]
    n = max(1, len(letters))
    cjk = sum(1 for c in letters if "一" <= c <= "鿿" or "぀" <= c <= "ヿ" or "가" <= c <= "힯")
    viet = sum(1 for c in letters if c in "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ")
    non_ascii = sum(1 for c in letters if ord(c) > 127)
    return {"words": len(text.split()), "cjk_chars": cjk, "viet_diacritic_ratio": round(viet / n, 3), "non_ascii_ratio": round(non_ascii / n, 3)}

def run(task, think):
    tid, group, lang, content = task
    payload = {
        "model": MODEL, "stream": False, "think": think,
        "messages": [{"role": "system", "content": SYS_VI}, {"role": "user", "content": content}],
        "options": {"num_ctx": 16384, "temperature": 0.7},
        "keep_alive": "10m",
    }
    t = time.time()
    r = post("/api/chat", payload)
    wall = time.time() - t
    text = r["message"]["content"].strip()
    toks = r.get("eval_count", 0)
    tps = toks / (r["eval_duration"] / 1e9) if r.get("eval_duration") else 0
    return {
        "id": tid, "group": group, "think": think, "lang_expected": lang, "prompt": content,
        "answer": text, "thinking_chars": len(r["message"].get("thinking") or ""),
        "tokens": toks, "tokens_per_sec": round(tps, 1), "wall_sec": round(wall, 1),
        "load_sec": round(r.get("load_duration", 0) / 1e9, 1), **stats(text, lang),
    }

results = []
print(f"Model: {MODEL} | Ollama {get('/api/version')['version']}")
for i, task in enumerate(TASKS):
    res = run(task, think=False)
    results.append(res)
    if i == 0:
        ps = get("/api/ps")["models"]
        for m in ps:
            print(f"Dang nap: {m['name']} | tong {m['size']/1e9:.1f} GB, trong VRAM {m['size_vram']/1e9:.1f} GB ({100*m['size_vram']/m['size']:.0f}%) | context {m.get('context_length')}")
        used, total = vram(); print(f"VRAM toan GPU luc model nap: {used}/{total} MiB")
    print(f"[{res['id']}] {res['tokens']} token, {res['tokens_per_sec']} tok/s, {res['wall_sec']}s | tu {res['words']} | CJK {res['cjk_chars']} | dau tieng Viet {res['viet_diacritic_ratio']} | non-ASCII {res['non_ascii_ratio']}")
# so sanh bat che do suy nghi (thinking) tren 1 cau
res = run(TASKS[0], think=True); res["id"] = "5a+think"; results.append(res)
print(f"[5a+think] {res['tokens']} token, {res['tokens_per_sec']} tok/s, {res['wall_sec']}s, phan 'suy nghi' {res['thinking_chars']} ky tu")

with open(os.path.join(OUT, "ket_qua.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "ket_qua.md"), "w", encoding="utf-8") as f:
    f.write(f"# Chạy thử {MODEL} (15/10/2026)\n\n")
    for r in results:
        f.write(f"## [{r['id']}] {r['group']} (thinking={r['think']})\n**Yêu cầu:** {r['prompt']}\n\n**Trả lời:**\n\n{r['answer']}\n\n_({r['tokens']} token, {r['tokens_per_sec']} tok/s, {r['wall_sec']}s)_\n\n---\n\n")
print("Da luu:", OUT)
