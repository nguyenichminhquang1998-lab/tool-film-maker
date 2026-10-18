"""
Ghi va bao cao dien nang cua may nay (uoc luong, khong phai cong to dien).

Cach tinh moi mau (mac dinh 15 giay mot lan):
  GPU   = DO THAT bang nvidia-smi (power.draw)
  CPU   = UOC LUONG theo muc tai: cpu_ranh_w + tai * (cpu_toi_da_w - cpu_ranh_w)   (may khong co dong ho do CPU)
  Con lai (bo mach chu, RAM, quat, 3 HDD + 1 SSD) = hang so phan_con_lai_w
  Tai o cam = (GPU + CPU + con lai) / hieu_suat_nguon * he_so_hieu_chinh + thiet_bi_ngoai_w
Sai so ban dau khoang +-15-20%. Muon sat hon: dung o cam do dien, doc W luc may ranh, chay `hieu-chinh`.

Dung:
  python dien-nang.py chay [--cach-giay 15]    # ghi lien tuc (dong cua so la dung); chi ghi khi dang chay
  python dien-nang.py bao-cao [--thang 2026-10]   # hom nay, 7 ngay, theo tuan, theo thang, tien neu da dat gia
  python dien-nang.py thu                      # do 1 mau, in ra man hinh
  python dien-nang.py hieu-chinh <W doc o o cam luc may ranh>
Du lieu: <thu_muc_du_lieu>\\luu\\YYYY-MM.csv. Khong gui di dau.
Do tu luc BAT may den luc TAT may: phai chay tu luc dang nhap Windows. Script khong tu cai gi; Quang tu tao loi tat (Startup) bang lenh trong javis-lich-su.md/ban giao hoac chay chay-ghi-dien.bat bang tay.
Tat may/ngu dong bang: mau cuoi cung mat toi da 1 chu ky (15 giay); thoi gian ngu/tat khong tinh (may ngu ~2-5 W, bo qua).
"""

import argparse, collections, csv, ctypes, datetime as dt, json, os, subprocess, sys, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "dien-nang.config.json")
DEFAULT = {
    "cach_giay": 15, "cpu_ranh_w": 12, "cpu_toi_da_w": 140, "phan_con_lai_w": 45, "hieu_suat_nguon": 0.88,
    "he_so_hieu_chinh": 1.0, "thiet_bi_ngoai_w": 0, "gia_kwh_dong": None, "thu_muc_du_lieu": r"D:\Quang\_dien-nang",
}
HEAD = ["thoi_diem", "dt_giay", "cpu_phan_tram", "gpu_w", "gpu_phan_tram", "cpu_w_uoc", "o_cam_w_uoc"]


def load_cfg():
    c = dict(DEFAULT)
    if os.path.exists(CONFIG):
        c.update(json.load(open(CONFIG, encoding="utf-8")))
    return c


def save_cfg(c):
    json.dump(c, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


class _FT(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]


def _times():
    i, k, u = _FT(), _FT(), _FT()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
    f = lambda x: (x.hi << 32) | x.lo
    return f(i), f(k), f(u)


def cpu_tai(prev):
    """Tra ve (ti le tai 0..1, moc moi). Moc dau tien chua co khoang de so -> tai 0."""
    now = _times()
    if prev is None:
        return 0.0, now
    di, dk, du = (now[n] - prev[n] for n in range(3))
    tot = dk + du  # nhan he thong tinh 'kernel' da gom ca thoi gian ranh
    return (max(0.0, min(1.0, 1 - di / tot)) if tot > 0 else 0.0), now


def gpu_do():
    """(cong suat W, tai %) cua card do hoa; khong doc duoc thi (0, 0)."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=power.draw,utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=15).stdout.strip().split("\n")[0]
        w, u = [x.strip() for x in out.split(",")]
        return float(w), float(u)
    except Exception:  # noqa: BLE001 - thieu nvidia-smi hay N/A: van ghi tiep phan con lai
        return 0.0, 0.0


def uoc_o_cam(cfg, tai, gpu_w):
    cpu_w = cfg["cpu_ranh_w"] + tai * (cfg["cpu_toi_da_w"] - cfg["cpu_ranh_w"])
    return cpu_w, (gpu_w + cpu_w + cfg["phan_con_lai_w"]) / cfg["hieu_suat_nguon"] * cfg["he_so_hieu_chinh"] + cfg["thiet_bi_ngoai_w"]


def cmd_thu(cfg):
    _, m = cpu_tai(None)
    time.sleep(2)
    tai, _ = cpu_tai(m)
    g, gu = gpu_do()
    cw, tot = uoc_o_cam(cfg, tai, g)
    print("CPU tai %.0f%% (uoc %.0f W) | GPU %.0f%% (do %.1f W) | con lai %d W | UOC LUC O CAM: %.0f W" % (tai * 100, cw, gu, g, cfg["phan_con_lai_w"], tot))


def cmd_chay(cfg, cach):
    root = cfg["thu_muc_du_lieu"]
    os.makedirs(os.path.join(root, "luu"), exist_ok=True)
    lock = os.path.join(root, "dang-chay.pid")
    if os.path.exists(lock):
        try:
            pid = int(open(lock).read().strip())
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], capture_output=True, text=True).stdout
            if str(pid) in out and "python" in out.lower():
                sys.exit("Da co mot may ghi dang chay (PID %d). Dong cua so do truoc." % pid)
        except ValueError:
            pass
    open(lock, "w").write(str(os.getpid()))
    print("Dang ghi dien nang moi %d giay vao %s\\luu. Dong cua so nay de dung." % (cach, root), flush=True)
    _, m = cpu_tai(None)
    last = time.time()
    try:
        while True:
            time.sleep(cach)
            now = time.time()
            tai, m = cpu_tai(m)
            g, gu = gpu_do()
            cw, tot = uoc_o_cam(cfg, tai, g)
            gap = now - last
            last = now
            d = gap if gap <= 3 * cach else cach  # nghi/ngu/tat may lau thi khong tinh thoi gian do
            ts = dt.datetime.now()
            path = os.path.join(root, "luu", ts.strftime("%Y-%m") + ".csv")
            new = not os.path.exists(path)
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(HEAD)
                w.writerow([ts.isoformat(timespec="seconds"), round(d, 1), round(tai * 100, 1), round(g, 1), round(gu, 1), round(cw, 1), round(tot, 1)])
    except KeyboardInterrupt:
        pass
    finally:
        if os.path.exists(lock):
            os.replace(lock, lock + ".cu")  # khong xoa file: doi ten de lan sau khong bi chan


def doc_het(cfg, thang=None):
    folder = os.path.join(cfg["thu_muc_du_lieu"], "luu")
    rows = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if fn.endswith(".csv") and (not thang or fn.startswith(thang)):
                with open(os.path.join(folder, fn), encoding="utf-8") as f:
                    for r in csv.DictReader(f):
                        rows.append((dt.datetime.fromisoformat(r["thoi_diem"]), float(r["dt_giay"]), float(r["o_cam_w_uoc"]), float(r["gpu_w"]), float(r["cpu_phan_tram"]), float(r["gpu_phan_tram"])))
    return rows


def tong(rows):
    kwh = sum(r[2] * r[1] for r in rows) / 3.6e6
    gio = sum(r[1] for r in rows) / 3600
    return kwh, gio, (kwh * 1000 / gio if gio else 0), max((r[2] for r in rows), default=0)


def trang_thai(r):
    """nang = AI/render/dung hinh nang (GPU >= 40% hoac CPU >= 60%); nhe = dang lam viec (GPU >= 5% hoac CPU >= 15%); ranh = bat may nhung khong lam gi."""
    if r[5] >= 40 or r[4] >= 60:
        return "nang (AI/render)"
    if r[5] >= 5 or r[4] >= 15:
        return "nhe (dang lam viec)"
    return "ranh (bat may, khong lam gi)"


def cmd_bao_cao(cfg, thang):
    rows = doc_het(cfg, thang)
    if not rows:
        print("Chua co du lieu. Bat may ghi bang chay-ghi-dien.bat.")
        return
    gia = cfg["gia_kwh_dong"]
    tien = (lambda k: " | %s dong" % format(round(k * gia), ",")) if gia else (lambda k: "")
    def dong(nhan, rs):
        k, g, tb, mx = tong(rs)
        return "%-16s %7.2f kWh | %5.1f gio ghi | TB %4.0f W | dinh %4.0f W%s" % (nhan, k, g, tb, mx, tien(k))
    today = dt.date.today()
    byday, byweek, bymonth = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for r in rows:
        d = r[0].date()
        byday[d].append(r)
        y, w, _ = d.isocalendar()
        byweek["%d-T%02d" % (y, w)].append(r)
        bymonth[d.strftime("%Y-%m")].append(r)
    print("== Moi lan bat may (tu luc bat den luc tat; 10 lan gan nhat) ==")
    sess, cur = [], [rows[0]]
    for r in rows[1:]:
        if (r[0] - cur[-1][0]).total_seconds() > 60:  # khoang trong > 60 giay = may da tat/ngu
            sess.append(cur)
            cur = []
        cur.append(r)
    sess.append(cur)
    for s in sess[-10:]:
        k, g, tb, mx = tong(s)
        bat = s[0][0] - dt.timedelta(seconds=s[0][1])
        con_chay = (dt.datetime.now() - s[-1][0]).total_seconds() <= 60
        tl = {n: sum(r[1] for r in s if trang_thai(r) == n) / max(sum(r[1] for r in s), 1) * 100 for n in ("ranh (bat may, khong lam gi)", "nhe (dang lam viec)", "nang (AI/render)")}
        print("%s -> %s (%s) %5.1f gio | %6.2f kWh | TB %3.0f W | dinh %3.0f W | ranh %2.0f%% nhe %2.0f%% nang %2.0f%%%s" % (
            bat.strftime("%d/%m %H:%M"), "DANG CHAY" if con_chay else s[-1][0].strftime("%H:%M" if s[-1][0].date() == bat.date() else "%d/%m %H:%M"),
            "may dang bat" if con_chay else "da tat/ngu", g, k, tb, mx, *tl.values(), tien(k)))
    print("== Hom nay (%s) ==" % today)
    print(dong("hom nay", byday.get(today, [])) if today in byday else "(chua co mau hom nay)")
    print("== 7 ngay gan nhat ==")
    for d in sorted(byday)[-7:]:
        print(dong(d.strftime("%d/%m (%a)"), byday[d]))
    print("== Theo tuan ==")
    for k in sorted(byweek)[-6:]:
        print(dong(k, byweek[k]))
    print("== Theo thang ==")
    for k in sorted(bymonth):
        print(dong(k, bymonth[k]))
    print("== Dien nang di vao dau (toan bo du lieu dang xem) ==")
    ktot, gtot, _, _ = tong(rows)
    for ten in ("ranh (bat may, khong lam gi)", "nhe (dang lam viec)", "nang (AI/render)"):
        rs = [r for r in rows if trang_thai(r) == ten]
        k, g, tb, _ = tong(rs) if rs else (0, 0, 0, 0)
        print("%-30s %5.1f%% thoi gian | %7.2f kWh (%4.1f%% dien) | TB %4.0f W" % (ten, 100 * g / gtot if gtot else 0, k, 100 * k / ktot if ktot else 0, tb))
    print("\nLuu y: day la UOC LUONG (GPU do that, CPU uoc theo tai, phan con lai hang so; he so hieu chinh=%.2f). Chi tinh luc may ghi dang chay; phan may bat ma khong ghi thi khong co mat o day." % cfg["he_so_hieu_chinh"])
    if not gia:
        print("Chua dat gia dien (gia_kwh_dong trong dien-nang.config.json) nen chua tinh tien.")


def cmd_hieu_chinh(cfg, w_that):
    _, m = cpu_tai(None)
    time.sleep(1)
    cs = []
    for _ in range(8):
        time.sleep(2.5)
        tai, m = cpu_tai(m)
        g, _ = gpu_do()
        cs.append(uoc_o_cam(dict(cfg, he_so_hieu_chinh=1.0), tai, g)[1] - cfg["thiet_bi_ngoai_w"])
    uoc = sum(cs) / len(cs)
    he = (w_that - cfg["thiet_bi_ngoai_w"]) / uoc
    print("Uoc trung binh 20 giay (chua hieu chinh): %.0f W | o cam do: %.0f W | he so moi: %.3f" % (uoc, w_that, he))
    if not 0.5 <= he <= 2.0:
        sys.exit("He so %.2f lech qua xa (0.5 den 2.0): kiem lai so doc o cam, hay may dang tai nang luc do." % he)
    cfg["he_so_hieu_chinh"] = round(he, 3)
    save_cfg(cfg)
    print("Da luu he so hieu chinh vao dien-nang.config.json.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ghi va bao cao dien nang (uoc luong)")
    sub = ap.add_subparsers(dest="lenh", required=True)
    p = sub.add_parser("chay"); p.add_argument("--cach-giay", type=int)
    p = sub.add_parser("bao-cao"); p.add_argument("--thang", help="vd 2026-10")
    sub.add_parser("thu")
    p = sub.add_parser("hieu-chinh"); p.add_argument("w", type=float, help="W doc tren o cam luc may ranh")
    a = ap.parse_args()
    cfg = load_cfg()
    if a.lenh == "chay":
        cmd_chay(cfg, a.cach_giay or cfg["cach_giay"])
    elif a.lenh == "bao-cao":
        cmd_bao_cao(cfg, a.thang)
    elif a.lenh == "thu":
        cmd_thu(cfg)
    else:
        cmd_hieu_chinh(cfg, a.w)
