"""Keo (tai ve) cac muc Drive trong DANH SACH CHO PHEP ve D:\\Quang\\_drive\\ de AI local doc ban moi nhat.
Dung: python drive-keo.py            (keo tat ca muc trong drive-keo.json)
      python drive-keo.py <ten_muc>  (chi keo 1 muc)
      python drive-keo.py --ds       (liet ke ten muc, khong keo)

An toan (thiet ke 17/10): chi chay `rclone copy` TU Drive VE may. Khong sync, khong move, khong xoa, khong ghi len Drive.
Chi lay thu muc Drive + ten file nam trong drive-keo.json (khong nhan ID hay duong dan tu dong lenh), dich luon nam duoi
thu_muc_dich. Moi lan keo ghi de ban cu trong thu muc dich (do la muc dich: luon co ban moi nhat). Khong dua token vao day:
rclone tu giu dang nhap trong rclone.conf, AI local khong doc file do.
Dong cuoi cua dau ra la JSON (cho tool MCP drive_pull).
"""
import datetime as dt, json, os, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "drive-keo.json")


def keo(cfg, muc):
    root = os.path.abspath(cfg["thu_muc_dich"])
    dest = os.path.abspath(os.path.join(root, muc["ten"]))
    if not dest.startswith(root + os.sep):
        return {"ten": muc["ten"], "ok": False, "loi": "Thu muc dich nam ngoai thu_muc_dich"}
    os.makedirs(dest, exist_ok=True)
    cmd = [cfg.get("rclone_exe", "rclone"), "copy", cfg["rclone_remote"] + ":", dest,
           "--drive-root-folder-id", muc["folder_id"], "--drive-export-formats", muc["xuat"],
           "--max-depth", "1", "--max-transfer", "200M", "--retries", "3"]
    for p in muc["include"]:
        cmd += ["--include", p]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return {"ten": muc["ten"], "ok": False, "loi": "Khong tim thay rclone. Dat duong dan day du vao 'rclone_exe' trong drive-keo.json."}
    except subprocess.TimeoutExpired:
        return {"ten": muc["ten"], "ok": False, "loi": "rclone qua 300 giay, da dung."}
    canh_bao = []
    if "client_id" in p.stderr and "retire" in p.stderr:
        canh_bao.append("Remote gdrive dung client_id chung cua rclone, sap ngung hoat dong trong nam 2026: can tao client_id rieng (https://rclone.org/drive/#making-your-own-client-id).")
    if p.returncode != 0:
        loi = "\n".join(l for l in p.stderr.splitlines() if "NOTICE" not in l and l.strip())[-400:]
        return {"ten": muc["ten"], "ok": False, "loi": "rclone loi (exit %d): %s" % (p.returncode, loi), "canh_bao": canh_bao}
    files = []
    for name in muc["include"]:
        f = os.path.join(dest, name)
        if os.path.isfile(f):
            files.append({"ten": name, "duong_dan": f, "kb": round(os.path.getsize(f) / 1024), "drive_sua_luc": dt.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%d/%m/%Y %H:%M")})
        else:
            files.append({"ten": name, "duong_dan": None, "kb": None, "drive_sua_luc": None, "loi": "khong thay tren Drive (doi ten hoac xoa?)"})
    return {"ten": muc["ten"], "ok": all(x.get("duong_dan") for x in files), "thu_muc": dest, "files": files, "canh_bao": canh_bao}


def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    args = sys.argv[1:]
    if args == ["--ds"]:
        print(json.dumps({"ok": True, "muc": [{"ten": m["ten"], "mo_ta": m["mo_ta"], "file": m["include"]} for m in cfg["muc"]]}, ensure_ascii=False))
        return
    chon = [m for m in cfg["muc"] if not args or m["ten"] in args]
    thieu = [a for a in args if a not in [m["ten"] for m in cfg["muc"]]]
    if thieu:
        print(json.dumps({"ok": False, "loi": "Khong co muc %s trong danh sach cho phep. Co: %s" % (", ".join(thieu), ", ".join(m["ten"] for m in cfg["muc"]))}, ensure_ascii=False))
        sys.exit(2)
    ket_qua = [keo(cfg, m) for m in chon]
    for r in ket_qua:
        print("[%s] %s" % (r["ten"], "OK" if r["ok"] else "LOI: " + r.get("loi", "thieu file")))
        for f in r.get("files", []):
            print("  - %s: %s KB, sua tren Drive luc %s%s" % (f["ten"], f["kb"], f["drive_sua_luc"], (" (" + f["loi"] + ")") if f.get("loi") else ""))
        for w in r.get("canh_bao", []):
            print("  CANH BAO: " + w)
    print(json.dumps({"ok": all(r["ok"] for r in ket_qua), "ket_qua": ket_qua}, ensure_ascii=False))
    sys.exit(0 if all(r["ok"] for r in ket_qua) else 1)


if __name__ == "__main__":
    main()
