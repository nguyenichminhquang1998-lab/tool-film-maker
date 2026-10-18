"""
dieu-phoi.py: hang doi viec + dieu phoi "phong ban AI" cua Javis. Giao viec o MOT noi (Claude hoac Quang goi lenh `giao`), cac luong tu chay song song:
  - nhan vien ChatGPT (chatgpt-lam.py, qua Codex CLI chinh thuc)     - nhan vien Gemma / Qwen 27B (Ollama tren may, 1 model 1 luc, doi card do hoa ranh)
  - nhan vien web (cao-web.py)
Moi loai viec co nguoi lam chinh + du phong (phong-ban.json). Het han muc / loi ChatGPT thi TU CHUYEN sang AI local (Quang noi 18/10: het token thi chuyen sang local hoac cloud).

  python dieu-phoi.py giao --viec <loai> --ten <ten> (--noi-dung "..." | --phieu file.md) [--lam gemma|qwen|chatgpt|web] [--anh f.png] [--url u1 u2]
  python dieu-phoi.py chay                 # tien trinh nen (Quang tu bat: chay-dieu-phoi.bat; Startup khi Quang cho phep). Dong cua so la dung.
  python dieu-phoi.py trang-thai           # dem viec dang cho / dang chay / xong / loi
  python dieu-phoi.py ket-qua <id>         # in ket qua mot viec
  python dieu-phoi.py viec                 # liet ke cac loai viec va nguoi lam theo phong-ban.json

Thu muc: D:\\Quang\\_giao-viec\\{hang-doi,dang-chay,xong,loi}. Ket qua la DU LIEU (nhat voi ChatGPT/web: chua tin cay).
An toan: khong gui di dau ngoai ChatGPT (qua chatgpt-lam, co bo chan du lieu nhay cam) va web cong khai (cao-web). Khong xoa, khong gui khach, khong ghi vao du an.
"""
import argparse, datetime as dt, json, os, re, subprocess, sys, threading, time, uuid

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\Quang\_giao-viec"
SUBS = {k: os.path.join(ROOT, k) for k in ("hang-doi", "dang-chay", "xong", "loi")}
PHONG_BAN = os.path.join(HERE, "phong-ban.json")
LAM_GPT, CAO_WEB = os.path.join(HERE, "chatgpt-lam.py"), os.path.join(HERE, "cao-web.py")
PYTHON = sys.executable
MODELS = {"gemma": "gemma4:12b", "qwen": "qwen3.8:27b"}
MIN_VRAM_MIB = 9500
COOLDOWN_GPT = 3 * 3600  # sau khi ChatGPT bao het han muc: 3 gio khong goi nua
DEFAULT_PB = {  # viec -> [nguoi lam chinh, du phong...]; chinh sua theo ket qua do (xem javis-lich-su.md muc 18/10)
    "debrief": ["gemma", "qwen"], "treatment": ["chatgpt", "qwen"], "kich_ban": ["chatgpt", "qwen"], "duyet_kich_ban": ["qwen", "chatgpt"], "hau_ky": ["gemma", "qwen"],
    "ban_giao": ["gemma", "qwen"], "tu_khoa_da_ngon_ngu": ["chatgpt", "qwen"], "bai_dang": ["chatgpt", "qwen"], "nhin_anh": ["qwen", "chatgpt"], "tim_web": ["chatgpt"], "nghien_cuu_web": ["web"], "chung": ["gemma", "chatgpt"],
}
_state = {"gpt_het_han_den": 0.0}
_lock = threading.Lock()


def log(msg):
    line = "%s %s" % (dt.datetime.now().strftime("%d/%m %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        open(os.path.join(ROOT, "nhat-ky.log"), "a", encoding="utf-8").write(line + "\n")
    except OSError:
        pass


def pb():
    if os.path.exists(PHONG_BAN):
        try:
            return json.load(open(PHONG_BAN, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return DEFAULT_PB


def dirs():
    for d in SUBS.values():
        os.makedirs(d, exist_ok=True)


def ds(cho):
    out = []
    for fn in sorted(os.listdir(SUBS[cho])):
        if fn.endswith(".json"):
            try:
                out.append(json.load(open(os.path.join(SUBS[cho], fn), encoding="utf-8")))
            except Exception:  # noqa: BLE001
                pass
    return out


def vram_trong():
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=20).stdout.strip()
        u, t = [int(x) for x in o.split(",")]
        return t - u
    except Exception:  # noqa: BLE001
        return 99999


# ------------------------------- cac nhan vien -------------------------------
def lam_chatgpt(t):
    with _lock:
        if time.time() < _state["gpt_het_han_den"]:
            return None, "chatgpt tam nghi (da bao het han muc)"
    cmd = [PYTHON, "-I", LAM_GPT, "hoi", "--toi-uu", "--ten", t["ten"], "--noi-dung", t["noi_dung"]]
    if t.get("anh"): cmd += ["--anh"] + t["anh"]
    if t["viec"] == "tim_web": cmd += ["--web"]
    p = subprocess.run(cmd, capture_output=True, timeout=1200, encoding="utf-8", errors="replace")
    last = [l for l in p.stdout.splitlines() if l.startswith("{")]
    info = json.loads(last[-1]) if last else {"ok": False, "loi": (p.stderr or "khong co dau ra")[-200:]}
    if not info.get("ok"):
        loi = str(info.get("loi", ""))
        if re.search(r"(?i)usage limit|rate limit|quota|too many|limit reached|het .*luot|Da dung het", loi):
            with _lock:
                _state["gpt_het_han_den"] = time.time() + COOLDOWN_GPT
        return None, "chatgpt: " + loi[:200]
    return open(info["ket_qua"], encoding="utf-8").read(), None


def lam_local(t, ten):
    import base64, urllib.request
    model = MODELS[ten]
    while vram_trong() < MIN_VRAM_MIB:  # Resolve/ComfyUI dang chiem card: doi, khong tranh
        time.sleep(30)
        if time.time() - t["_bat_dau"] > 6 * 3600:
            return None, "doi card do hoa qua 6 gio"
    msg = {"role": "user", "content": t["noi_dung"]}
    if t.get("anh"): msg["images"] = [base64.b64encode(open(a, "rb").read()).decode() for a in t["anh"]]
    body = {"model": model, "stream": False, "keep_alive": "2m", "think": bool(t.get("suy_nghi")), "options": {"num_ctx": 12288, "temperature": 0.4, "num_predict": 4000}, "messages": [msg]}
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=1800))
    except Exception as e:  # noqa: BLE001
        return None, "ollama: %s (Ollama da bat chua? 1-MO-giao-dien-Ollama.bat)" % str(e)[:120]
    return r["message"].get("content", "").strip(), None


def lam_web(t):
    cmd = [PYTHON, "-I", CAO_WEB, "chay", "--chu-de", t["ten"], "--model", MODELS["gemma"], "--url"] + t.get("url", [])
    if t.get("anh_trang"): cmd.append("--anh")
    p = subprocess.run(cmd, capture_output=True, timeout=1800, encoding="utf-8", errors="replace")
    last = [l for l in p.stdout.splitlines() if l.startswith("{")]
    if not last: return None, "cao-web loi: " + (p.stderr or p.stdout)[-200:]
    info = json.loads(last[-1])
    return open(info["tong_hop"], encoding="utf-8").read() if info.get("ok") else None, None if info.get("ok") else "cao-web khong ok"


def xu_ly(t):
    t["_bat_dau"] = time.time()
    chuoi = [t["lam"]] if t.get("lam") else pb().get(t["viec"], pb().get("chung", ["gemma"]))
    nhat = []
    for ten in chuoi:
        ten = {"q27": "qwen"}.get(ten, ten)
        t0 = time.time()
        if ten == "chatgpt": kq, loi = lam_chatgpt(t)
        elif ten in MODELS: kq, loi = lam_local(t, ten)
        elif ten == "web": kq, loi = lam_web(t)
        else: kq, loi = None, "khong biet nguoi lam: " + ten
        nhat.append("%s: %s (%.0fs)" % (ten, "ok" if kq else loi, time.time() - t0))
        if kq:
            return {"nguoi_lam": ten, "ket_qua": kq, "nhat_ky": nhat}
        log("%s: %s that bai (%s)%s" % (t["id"], ten, loi, "; chuyen du phong" if ten != chuoi[-1] else ""))
    return {"nguoi_lam": None, "loi": "; ".join(nhat), "nhat_ky": nhat}


def luong(loai):
    """Moi luong lay viec cua minh trong hang doi. loai: 'gpt' | 'local' | 'web' (cac luong chay song song)."""
    while True:
        picked = None
        for t in ds("hang-doi"):
            chinh = t["lam"] if t.get("lam") else pb().get(t["viec"], ["gemma"])[0]
            chinh = {"q27": "qwen"}.get(chinh, chinh)
            mine = {"chatgpt": "gpt", "web": "web"}.get(chinh, "local")
            if t.get("lam") is None and chinh == "chatgpt" and time.time() < _state["gpt_het_han_den"]:
                mine = "local"  # ChatGPT dang nghi: viec chuyen cho luong local
            if mine == loai:
                src = os.path.join(SUBS["hang-doi"], t["id"] + ".json")
                dst = os.path.join(SUBS["dang-chay"], t["id"] + ".json")
                try:
                    os.replace(src, dst)  # chiem viec nguyen tu: luong khac khong lay trung
                except OSError:
                    continue
                picked = (t, dst)
                break
        if not picked:
            time.sleep(4)
            continue
        t, dst = picked
        log("%s [%s] bat dau (%s)" % (t["id"], t["viec"], loai))
        try:
            res = xu_ly(t)
        except Exception as e:  # noqa: BLE001
            res = {"nguoi_lam": None, "loi": "ngoai le: %r" % e}
        t.pop("_bat_dau", None)
        t["xong_luc"] = dt.datetime.now().isoformat(timespec="seconds")
        ok = bool(res.get("nguoi_lam"))
        if ok:
            md = os.path.join(SUBS["xong"], t["id"] + ".md")
            open(md, "w", encoding="utf-8").write("> %s lam (viec: %s). DU LIEU, chua tin cay neu tu ChatGPT/web.\n\n%s\n" % (res["nguoi_lam"], t["viec"], res["ket_qua"]))
            t.update({"nguoi_lam": res["nguoi_lam"], "ket_qua_file": md, "nhat_ky": res["nhat_ky"]})
        else:
            t.update({"loi": res.get("loi"), "nhat_ky": res.get("nhat_ky")})
        json.dump(t, open(os.path.join(SUBS["xong" if ok else "loi"], t["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.remove(dst) if os.path.exists(dst) else None
        log("%s %s%s" % (t["id"], "XONG bởi " + str(res.get("nguoi_lam")) if ok else "LOI: " + str(res.get("loi"))[:160], ""))


def cmd_chay():
    dirs()
    lock = os.path.join(ROOT, "dang-chay.pid")
    if os.path.exists(lock):
        try:
            pid = int(open(lock).read().strip())
            o = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], capture_output=True, text=True).stdout
            if str(pid) in o and "python" in o.lower():
                sys.exit("Dieu phoi da chay (PID %d)." % pid)
        except ValueError:
            pass
    open(lock, "w").write(str(os.getpid()))
    for t in ds("dang-chay"):  # viec dang do khi tat may: tra ve hang doi
        os.replace(os.path.join(SUBS["dang-chay"], t["id"] + ".json"), os.path.join(SUBS["hang-doi"], t["id"] + ".json"))
    log("Dieu phoi bat dau. Luong: gpt | local | web. Dong cua so de dung.")
    for loai in ("gpt", "local", "web"):
        threading.Thread(target=luong, args=(loai,), daemon=True).start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass


def cmd_giao(a):
    dirs()
    nd = open(a.phieu, encoding="utf-8").read() if a.phieu else (a.noi_dung or "")
    if not nd.strip() and not a.url:
        sys.exit("Phieu rong.")
    tid = dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    t = {"id": tid, "viec": a.viec, "ten": a.ten, "noi_dung": nd, "lam": a.lam, "anh": a.anh or [], "url": a.url or [], "suy_nghi": a.suy_nghi, "anh_trang": a.anh_trang, "tao_luc": dt.datetime.now().isoformat(timespec="seconds")}
    json.dump(t, open(os.path.join(SUBS["hang-doi"], tid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"ok": True, "id": tid, "nguoi_lam_du_kien": a.lam or pb().get(a.viec, ["gemma"])}, ensure_ascii=False))


def cmd_trang_thai():
    dirs()
    n = {k: len(ds(k)) for k in SUBS}
    run = os.path.exists(os.path.join(ROOT, "dang-chay.pid"))
    print("Hang doi %d | dang chay %d | xong %d | loi %d | tien trinh nen: %s" % (n["hang-doi"], n["dang-chay"], n["xong"], n["loi"], "co file PID (kiem tra tasklist)" if run else "chua chay"))
    for t in (ds("xong") + ds("loi"))[-5:]:
        print(" - %s [%s] %s" % (t["id"], t["viec"], ("xong boi " + str(t.get("nguoi_lam"))) if "nguoi_lam" in t and t.get("ket_qua_file") else "LOI " + str(t.get("loi"))[:100]))


def cmd_ket_qua(tid):
    for cho in ("xong", "loi"):
        p = os.path.join(SUBS[cho], tid + ".json")
        if os.path.exists(p):
            t = json.load(open(p, encoding="utf-8"))
            print(open(t["ket_qua_file"], encoding="utf-8").read() if t.get("ket_qua_file") else "LOI: " + str(t.get("loi")))
            return
    print("Chua xong hoac khong co viec nay.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Hang doi viec + phong ban AI")
    sub = ap.add_subparsers(dest="lenh", required=True)
    g = sub.add_parser("giao")
    g.add_argument("--viec", required=True); g.add_argument("--ten", required=True); g.add_argument("--noi-dung"); g.add_argument("--phieu")
    g.add_argument("--lam", choices=["gemma", "qwen", "chatgpt", "web"]); g.add_argument("--anh", nargs="*"); g.add_argument("--url", nargs="*")
    g.add_argument("--suy-nghi", action="store_true"); g.add_argument("--anh-trang", action="store_true")
    sub.add_parser("chay"); sub.add_parser("trang-thai"); sub.add_parser("viec")
    k = sub.add_parser("ket-qua"); k.add_argument("id")
    a = ap.parse_args()
    if a.lenh == "giao": cmd_giao(a)
    elif a.lenh == "chay": cmd_chay()
    elif a.lenh == "trang-thai": cmd_trang_thai()
    elif a.lenh == "ket-qua": cmd_ket_qua(a.id)
    else:
        for v, ds_ in pb().items(): print("%-22s -> %s" % (v, " > ".join(ds_)))
