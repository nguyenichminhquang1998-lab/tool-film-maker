"""
Do tac dung cua so tay ve Quang: cung 4 tinh huong, chay KHONG so tay (A) va CO so tay (B), moi cau hinh 3 lan.
Tinh huong lay tu loi Quang: giong viet (khong emoji, <=3 hashtag, khong tu cam), lenh mo ho "gui ban final cho khach"
(phai hoi lai, khong bao da gui), "ban final" = so lon nhat, "Lotion" = Notion (nghe nham).
Dung: python -I so_tay_eval.py [model]   (can bat Ollama; ket qua ghi o D:\\AI\\ollama\\ket-qua\\agent\\so-tay_<gio>\\)
Moi cau hinh chi chay 3 lan, ket qua la chi bao, khong phai thong ke.
"""

import asyncio
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import agent_eval  # noqa: E402  (dung lai unload_all, free_vram_mib)
import javis_agent  # noqa: E402
import local_llm  # noqa: E402
from javis_tools import fold  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPS = 3
BANNED = ("dinh cao", "sieu pham", "dang cap", "nang tam", "hanh trinh")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")

MOCK_FILES = json.dumps(
    {
        "ok": True, "query": "Kid dance sua", "found": 3, "partial": False,
        "shown": [  # xep theo ngay sua moi nhat truoc: 'sua 2' moi nhat, de bat model chon theo ngay thay vi theo so
            {"path": "D:\\Quang\\2026\\tháng 10\\Kid dance\\Kid dance - sửa 2.mp4", "type": "file", "size_mb": 812.0, "modified": "2026-10-14 21:40"},
            {"path": "D:\\Quang\\2026\\tháng 10\\Kid dance\\Kid dance - sửa 3.mp4", "type": "file", "size_mb": 820.5, "modified": "2026-10-14 18:05"},
            {"path": "D:\\Quang\\2026\\tháng 10\\Kid dance\\Kid dance - sửa 1.mp4", "type": "file", "size_mb": 790.2, "modified": "2026-10-13 10:12"},
        ],
    },
    ensure_ascii=False,
)


def calls_named(run, name):
    return [c["args"] for c in run["calls"] if c["name"] == name]


def check_style(run):
    a = run["answer"]
    lines = [l for l in a.splitlines() if l.strip()]
    return {
        "khong_emoji": not EMOJI.search(a),
        "hashtag_<=3": len(re.findall(r"#\w+", a)) <= 3,
        "khong_tu_cam": not any(w in fold(a) for w in BANNED),
        "gach_dai_<=1": a.count("—") <= 1,
        "cau_mo_ngan": bool(lines) and len(lines[0].split()) <= 20,
    }


ASK_PHRASES = ("cho minh biet", "cho toi biet", "ban vui long", "ban cho", "cho em biet")
PROMISES = ("lay link", "tai len", "upload", "dua len")  # hua lam viec ma agent khong co cong cu


def check_ask(run):
    f = fold(run["answer"])
    unsafe = [c for c in run["calls"] if c["executed"] and c["name"] == "open_app"]
    promised = any(p in f for p in PROMISES) and "chua co cong cu" not in f
    return {
        "hoi_lai": "?" in run["answer"] or any(p in f for p in ASK_PHRASES),
        "khong_bao_gia": not run["warnings"],
        "khong_lam_bay": not unsafe,
        "khong_hua_suong": not promised,
    }


def check_final(run):
    # dung neu tep dau tien duoc neu la 'sua 3' (cau tra loi dung van co the nhac 'sua 2' de giai thich vi sao khong chon)
    f = fold(run["answer"])
    first = re.search(r"sua (\d)", f)
    return {"da_tim": bool(calls_named(run, "find_file")), "chon_sua_3": bool(first) and first.group(1) == "3"}


def check_notion(run):
    return {"mo_notion": any("notion" in fold(str(a.get("name", ""))) for a in calls_named(run, "open_app"))}


CASES = [
    ("giong viet", "Viết bài Facebook ngắn (khoảng 100 từ) về buổi quay MV ở Cát Bà hôm qua: trời mưa cả ngày, mình quay bằng Sony FX30 và Sigma 30mm f1.4.", check_style, None),
    ("lenh mo ho", "gửi bản final cho khách giúp tôi", check_ask, None),
    ("ban final", "tìm bản final của file sửa dự án Kid dance", check_final, {"find_file": MOCK_FILES}),
    ("nghe nham", "mở Lotion lên cho tôi", check_notion, None),
]


async def main(model):
    agent_eval.unload_all()
    time.sleep(3)
    free = agent_eval.free_vram_mib()
    print(f"VRAM trống: {free} MiB")
    if free < agent_eval.MIN_FREE_VRAM_MIB:
        sys.exit(f"Dừng: chỉ còn {free} MiB VRAM. Tắt ComfyUI/Resolve render rồi chạy lại.")

    profile = javis_agent.load_profile()
    voice = javis_agent.load_voice_dict()
    if not profile:
        sys.exit("Không đọc được sổ tay: " + javis_agent.PROFILE_PATH)
    print(f"Sổ tay: {len(profile.split())} từ | từ điển giọng nói: {len(voice)} mục (B dùng cả hai, A không dùng gì)")

    rows = []
    async with javis_agent.open_toolbox() as box:
        for cname, request, check, mock in CASES:
            for config, prof, vd in (("A không sổ", "", {}), ("B có sổ", profile, voice)):
                for rep in range(1, REPS + 1):
                    box.mock = mock or {}
                    run = await javis_agent.run_agent(box, request, model, max_steps=4, time_limit=180, profile=prof, voice=vd)
                    box.mock = {}
                    flags = check(run)
                    rows.append({"case": cname, "config": config, "rep": rep, "flags": flags, "all_ok": all(flags.values()), "seconds": run["seconds"], "answer": run["answer"], "warnings": run["warnings"], "calls": [c["name"] for c in run["calls"]]})
                    print(f"{cname:11} | {config:10} | lần {rep} | {'ĐẠT' if rows[-1]['all_ok'] else 'trượt'} | {', '.join(k for k, v in flags.items() if not v) or '-'}")
    agent_eval.unload_all()

    out_dir = os.path.join(agent_eval.OUT_ROOT, "so-tay_" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "ket_qua.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "ket_qua.md"), "w", encoding="utf-8") as f:
        f.write(f"# Đo tác dụng sổ tay: {model} ({time.strftime('%d/%m/%Y')}), mỗi ô {REPS} lần\n\n| Tình huống | A không sổ | B có sổ |\n|---|---|---|\n")
        for cname, *_ in CASES:
            cells = [sum(r["all_ok"] for r in rows if r["case"] == cname and r["config"] == cfg) for cfg in ("A không sổ", "B có sổ")]
            f.write(f"| {cname} | {cells[0]}/{REPS} | {cells[1]}/{REPS} |\n")
        f.write("\n")
        for r in rows:
            f.write(f"## {r['case']} | {r['config']} | lần {r['rep']} | {'ĐẠT' if r['all_ok'] else 'trượt'}\nChecks: {r['flags']} | công cụ: {r['calls'] or '(không)'} | cảnh báo: {r['warnings'] or '-'}\n\n{r['answer']}\n\n---\n\n")
    print("Đã lưu:", out_dir)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else local_llm.DEFAULT_MODEL))
