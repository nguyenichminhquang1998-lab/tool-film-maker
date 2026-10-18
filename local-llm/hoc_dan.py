"""
hoc_dan.py: vong "sua loi -> luat -> kiem" de AI local (Gemma, Qwen 27B) lam viec cua Quang ngay cang chinh xac. Model KHONG tu hoc:
cai tien nam o so tay (profile.md) va tu dien giong noi, moi luat moi phai QUA BO CA HOI QUY truoc khi xin Quang duyet dua vao so tay.

Vong lap:
  1. Quang sua AI ("Sua: ...")  ->  python hoc_dan.py them --yeu-cau "<lenh>" --sua "<loi Quang>" --luat "<luat rut ra>" [kiem tra...]
     ghi nhat-ky-sua-loi.md (chi them), tao ca hoi quy trong ca-hoi-quy.json, ghi luat vao luat-cho-duyet.md (CHUA vao so tay).
  2. python hoc_dan.py chay --model gemma4:12b [--luat "<luat thu>"]   chay moi ca 3 cach: A khong so | B co so (+tu dien) | C = B + luat thu
  3. Luat nao lam ca loi dung them (C hon B) ma khong lam hong ca khac thi de xuat Quang duyet roi moi dan vao profile.md (Quang tu duyet so tay).
Cac kiem tra (dung ngay trong 'them'): --phai-goi TOOL.. --khong-goi TOOL.. --args-chua TOOL=chu --tra-loi-chua a b --tra-loi-mot-trong a b --khong-chua a b
  --hoi-lai --khong-bao-gia --khong-emoji --toi-da-hashtag N --nhac-dau-tien REGEX=GIA_TRI --mock TOOL=file.json
File o D:\\AI\\ollama\\so-tay-quang\\ (ngoai repo vi la thong tin ca nhan). Cho phep model cham (27B) dat --gioi-han 600.
"""
import argparse, asyncio, datetime as dt, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "danh-gia"))
import javis_agent  # noqa: E402
import local_llm  # noqa: E402
from javis_tools import fold  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DIR = r"D:\AI\ollama\so-tay-quang"
CASES = os.path.join(DIR, "ca-hoi-quy.json")
LOG = os.path.join(DIR, "nhat-ky-sua-loi.md")
RULES = os.path.join(DIR, "luat-cho-duyet.md")
OUT_ROOT = r"D:\AI\ollama\ket-qua\agent"
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
ASK = ("cho minh biet", "cho toi biet", "ban vui long", "ban cho", "cho em biet")


def load_cases():
    return json.load(open(CASES, encoding="utf-8")) if os.path.exists(CASES) else []


def kiem(case, run):
    """Tra ve dict {ten kiem tra: True/False}."""
    chk, ans, calls = case["kiem"], run["answer"], run["calls"]
    f, names = fold(ans), [c["name"] for c in calls]
    r = {}
    for t in chk.get("phai_goi", []): r["goi:" + t] = t in names
    for t in chk.get("khong_goi", []): r["khong_goi:" + t] = t not in names
    for t, s in (chk.get("args_chua") or {}).items(): r["args:%s~%s" % (t, s)] = any(t == c["name"] and fold(s) in fold(json.dumps(c["args"], ensure_ascii=False)) for c in calls)
    if chk.get("tra_loi_chua"): r["chua_het"] = all(fold(s) in f for s in chk["tra_loi_chua"])
    if chk.get("tra_loi_mot_trong"): r["chua_mot_trong"] = any(fold(s) in f for s in chk["tra_loi_mot_trong"])
    if chk.get("khong_chua"): r["khong_chua"] = not any(fold(s) in f for s in chk["khong_chua"])
    if chk.get("hoi_lai"): r["hoi_lai"] = "?" in ans or any(p in f for p in ASK)
    if chk.get("khong_bao_gia"): r["khong_bao_gia"] = not run["warnings"]
    if chk.get("khong_emoji"): r["khong_emoji"] = not EMOJI.search(ans)
    if chk.get("toi_da_hashtag") is not None: r["hashtag<=%d" % chk["toi_da_hashtag"]] = len(re.findall(r"#\w+", ans)) <= chk["toi_da_hashtag"]
    if chk.get("nhac_dau_tien"):
        m = re.search(chk["nhac_dau_tien"]["regex"], f)
        r["nhac_dau_tien=" + chk["nhac_dau_tien"]["gia_tri"]] = bool(m) and m.group(1) == chk["nhac_dau_tien"]["gia_tri"]
    return r


def cmd_them(a):
    os.makedirs(DIR, exist_ok=True)
    cases = load_cases()
    cid = "c%d" % (len(cases) + 1)
    chk = {}
    if a.phai_goi: chk["phai_goi"] = a.phai_goi
    if a.khong_goi: chk["khong_goi"] = a.khong_goi
    if a.args_chua: chk["args_chua"] = dict(x.split("=", 1) for x in a.args_chua)
    if a.tra_loi_chua: chk["tra_loi_chua"] = a.tra_loi_chua
    if a.tra_loi_mot_trong: chk["tra_loi_mot_trong"] = a.tra_loi_mot_trong
    if a.khong_chua: chk["khong_chua"] = a.khong_chua
    if a.hoi_lai: chk["hoi_lai"] = True
    if a.khong_bao_gia: chk["khong_bao_gia"] = True
    if a.khong_emoji: chk["khong_emoji"] = True
    if a.toi_da_hashtag is not None: chk["toi_da_hashtag"] = a.toi_da_hashtag
    if a.nhac_dau_tien:
        rg, gt = a.nhac_dau_tien.rsplit("=", 1)
        chk["nhac_dau_tien"] = {"regex": rg, "gia_tri": gt}
    mock = {}
    for m in a.mock or []:
        tool, path = m.split("=", 1)
        mock[tool] = open(path, encoding="utf-8").read()
    if not chk:
        sys.exit("Can it nhat mot kiem tra (--phai-goi, --tra-loi-chua, --hoi-lai, ...): khong co kiem tra thi khong do duoc.")
    cases.append({"id": cid, "yeu_cau": a.yeu_cau, "luat": a.luat, "kiem": chk, "mock": mock, "ngay": dt.date.today().isoformat()})
    json.dump(cases, open(CASES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("\n## %s | %s\n- Lệnh: %s\n- Quang sửa (nguyên văn): %s\n- Luật rút ra: %s\n- Ca hồi quy: %s, kiểm: %s\n" % (dt.date.today().strftime("%d/%m/%Y"), cid, a.yeu_cau, a.sua, a.luat, cid, json.dumps(chk, ensure_ascii=False)))
    with open(RULES, "a", encoding="utf-8") as f:
        f.write("- [%s, %s] %s  (CHƯA vào sổ tay; chạy `hoc_dan.py chay --luat \"...\"` rồi xin Quang duyệt)\n" % (cid, dt.date.today().isoformat(), a.luat))
    print("Da ghi nhat ky, tao ca %s va dua luat vao luat-cho-duyet.md (chua vao profile.md)." % cid)


async def cmd_chay(a):
    cases = [c for c in load_cases() if not a.ca or c["id"] in a.ca]
    if not cases:
        sys.exit("Chua co ca hoi quy. Dung 'them' truoc.")
    profile, voice = javis_agent.load_profile(), javis_agent.load_voice_dict()
    cfgs = [("A không sổ", "", {}), ("B có sổ", profile, voice)]
    if a.luat:
        cfgs.append(("C B+luật thử", profile + "\n\n## Luật đang thử (chưa được Quang duyệt)\n- " + a.luat + "\n", voice))
    if a.so_tay_thu:  # thu CA SO TAY UNG VIEN (luat da chen dung cho trong so tay): kiem tra vi tri/do dai cua luat, khong chi noi dung
        cfgs.append(("C sổ ứng viên", open(a.so_tay_thu, encoding="utf-8").read(), voice))
    rows = []
    async with javis_agent.open_toolbox() as box:
        for case in cases:
            for name, prof, vd in cfgs:
                for rep in range(1, a.lap + 1):
                    box.mock = case.get("mock") or {}
                    run = await javis_agent.run_agent(box, case["yeu_cau"], a.model, max_steps=4, time_limit=a.gioi_han, profile=prof, voice=vd)
                    box.mock = {}
                    flags = kiem(case, run)
                    rows.append({"ca": case["id"], "cfg": name, "lan": rep, "dat": all(flags.values()), "truot": [k for k, v in flags.items() if not v], "giay": run["seconds"], "tra_loi": run["answer"][:300]})
                    print("%-3s | %-13s | lan %d | %s | %5.0fs | %s" % (case["id"], name, rep, "ĐẠT " if rows[-1]["dat"] else "trượt", run["seconds"], ", ".join(rows[-1]["truot"]) or "-"), flush=True)
    out = os.path.join(OUT_ROOT, "hoc-dan_" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out, exist_ok=True)
    json.dump(rows, open(os.path.join(out, "ket_qua.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n== Tong: %s, moi o %d lan ==" % (a.model, a.lap))
    for name, _, _ in cfgs:
        rs = [r for r in rows if r["cfg"] == name]
        print("%-13s %d/%d dat | TB %.0fs/lan" % (name, sum(r["dat"] for r in rs), len(rs), sum(r["giay"] for r in rs) / len(rs)))
    if a.luat or a.so_tay_thu:
        b = {r["ca"] for r in rows if r["cfg"] == "B có sổ" and not r["dat"]}
        c = {r["ca"] for r in rows if r["cfg"] == cfgs[-1][0] and not r["dat"]}
        print("Luat/so tay thu: ca truot cua B = %s; ca truot cua C = %s -> %s" % (sorted(b) or "khong", sorted(c) or "khong",
              "AN TOAN (C khong them ca truot moi)" if c <= b else "GAY HONG ca %s" % sorted(c - b)))
    print("Da luu:", out)
    from agent_eval import unload_all  # noqa: E402 - nha VRAM sau khi do
    unload_all()


def main():
    ap = argparse.ArgumentParser(description="Vong sua loi -> luat -> kiem cho AI local")
    sub = ap.add_subparsers(dest="lenh", required=True)
    t = sub.add_parser("them")
    t.add_argument("--yeu-cau", required=True); t.add_argument("--sua", required=True); t.add_argument("--luat", required=True)
    t.add_argument("--phai-goi", nargs="*"); t.add_argument("--khong-goi", nargs="*"); t.add_argument("--args-chua", nargs="*")
    t.add_argument("--tra-loi-chua", nargs="*"); t.add_argument("--tra-loi-mot-trong", nargs="*"); t.add_argument("--khong-chua", nargs="*")
    t.add_argument("--hoi-lai", action="store_true"); t.add_argument("--khong-bao-gia", action="store_true"); t.add_argument("--khong-emoji", action="store_true")
    t.add_argument("--toi-da-hashtag", type=int); t.add_argument("--nhac-dau-tien"); t.add_argument("--mock", nargs="*")
    c = sub.add_parser("chay")
    c.add_argument("--model", default=local_llm.DEFAULT_MODEL, choices=local_llm.MODELS)
    c.add_argument("--luat"); c.add_argument("--so-tay-thu", help="duong dan file so tay ung vien (luat da chen vao dung cho) de do thay cho C"); c.add_argument("--ca", nargs="*"); c.add_argument("--lap", type=int, default=1); c.add_argument("--gioi-han", type=int, default=180)
    sub.add_parser("xem")
    a = ap.parse_args()
    if a.lenh == "them":
        cmd_them(a)
    elif a.lenh == "xem":
        for c in load_cases(): print(c["id"], "|", c["yeu_cau"], "|", c["luat"], "|", list(c["kiem"]))
    else:
        asyncio.run(cmd_chay(a))


if __name__ == "__main__":
    main()
