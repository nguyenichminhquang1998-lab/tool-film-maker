"""Doi chieu job giua bang hach toan va Database (CHI DOC: khong ghi file nguon, khong noi mang, khong dung LLM de so so).
Dung: python job_doi_chieu.py <hach_toan.xlsx> <database.xlsx> [--thang 8,9,10] [--nam 2026] [--ra bao_cao.md] [--y-kien-thu-hai [MODEL]]
--y-kien-thu-hai: voi cac cap "ghep uoc chung" (do code khong chac), hoi them AI local (mac dinh qwen3.8:27b; Quang cham 18/10 thay Qwen dung hon Gemma)
"cung job / khac job / khong chac" kem ly do. CHI THAM KHAO de Quang xac nhan: so tien/ngay van do code so, AI khong sua gi, khong tu ket luan.

Quang xuat 2 Google Sheet ra .xlsx (File > Tai xuong > .xlsx) roi chay lenh nay. Claude chi nhan bang tom tat cac dong LECH
(toi da MAX_DONG dong moi muc); chi tiet day du ghi ra file bao cao. Khong co cot Ma Job o bang hach toan nen ghep theo
ten + khach + thang (+ doanh thu trung): moi cap ghep khong chac chan deu bi gan nhan CAN XAC NHAN, khong tu ket luan.
"""
import argparse, collections, datetime as dt, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from xlsx_read import read_xlsx
import fin_facts

TOL_TIEN = 1000      # lech duoi 1.000 dong coi nhu khop
TOL_NGAY = 0.01
MAX_DONG = 12
NGUONG_UOC_CHUNG = 0.6

# truong Database -> (cach khop tieu de, tu khoa da bo dau, chu thuong, khoang trang)
DB_COLS = {
    "ma_job": ("start", "ma job"), "ten_job": ("start", "ten job"), "thang": ("eq", "thang"), "nam": ("eq", "nam"),
    "khach": ("start", "ten khach hang"), "gia_chot": ("start", "gia chot"), "gia_bao": ("start", "gia bao"),
    "chi_phi_ngoai": ("start", "chi phi thue ngoai"), "d_fx30": ("start", "ngay quay fx30"), "d_flycam": ("start", "ngay bay flycam"),
    "d_fisheye": ("start", "ngay lens fisheye"), "d_pc": ("start", "ngay dung pc"), "khau_hao": ("start", "khau hao"),
    "loi_nhuan": ("start", "loi nhuan thuan"), "da_thu": ("start", "da thu"),
}
# (nhan, truong bang hach toan, truong Database, kieu)
SO_SANH = [
    ("doanh thu", "doanh_thu_n", "doanh_thu", "tien"), ("chi phí ngoài", "chi_phi_ngoai_n", "chi_phi_ngoai", "tien"),
    ("ngày FX30", "kh_fx30_n", "d_fx30", "ngay"), ("ngày flycam", "kh_flycam_n", "d_flycam", "ngay"),
    ("ngày fisheye", "kh_fisheye_n", "d_fisheye", "ngay"), ("ngày dựng PC", "ngay_dung_n", "d_pc", "ngay"),
    ("khấu hao", "tong_kh_n", "khau_hao", "tien"), ("lợi nhuận", "loi_nhuan_n", "loi_nhuan", "tien"), ("đã thu", "thuc_nhan_n", "da_thu", "tien"),
]


def fold(s):
    s = unicodedata.normalize("NFD", str(s).lower().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip()


def tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", fold(s)) if len(t) > 1}


def vnum(v):
    """So tu o Excel: giu nguyen so; chuoi kieu '1.800.000 d' hoac '0,50' thi doc theo cach viet Viet Nam."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if not isinstance(v, str):
        return None
    s = re.sub(r"[^\d.,-]", "", v)
    if not re.search(r"\d", s):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def load_db(path):
    for sheet, rows in read_xlsx(path).items():
        for hi, r in enumerate(rows[:10]):
            if not any(isinstance(c, str) and fold(c).startswith("ma job") for c in r):
                continue
            cmap, folded = {}, [fold(c) if isinstance(c, str) else "" for c in r]
            for key, (how, kw) in DB_COLS.items():
                for i, f in enumerate(folded):
                    if (how == "start" and f.startswith(kw)) or (how == "eq" and f == kw):
                        cmap[key] = i
                        break
            thieu = [k for k in DB_COLS if k not in cmap]
            jobs = []
            for i, row in enumerate(rows[hi + 1:], start=hi + 2):
                cell = lambda k: row[cmap[k]] if k in cmap and cmap[k] < len(row) else None
                ma = cell("ma_job")
                if not (isinstance(ma, str) and re.fullmatch(r"P\d+", ma.strip().upper())):
                    continue
                j = {"dong": i, "ma": ma.strip().upper(), "ten": str(cell("ten_job") or "").strip(), "khach": str(cell("khach") or "").strip(),
                     "thang": vnum(cell("thang")), "nam": vnum(cell("nam"))}
                gia = vnum(cell("gia_chot")) or 0.0
                j["doanh_thu"], j["doanh_thu_goc"] = (gia, "giá chốt") if gia else (vnum(cell("gia_bao")) or 0.0, "giá báo (giá chốt trống)")
                for k in ("chi_phi_ngoai", "d_fx30", "d_flycam", "d_fisheye", "d_pc", "khau_hao", "loi_nhuan", "da_thu"):
                    j[k] = vnum(cell(k)) or 0.0
                jobs.append(j)
            return jobs, sheet, thieu
    raise SystemExit("Không thấy dòng tiêu đề có cột 'Mã Job' trong 10 dòng đầu của file Database.")


def nam_cua_sheet(rows):
    c = collections.Counter(d["ngay_d"].year for d in rows if d["ngay_d"])
    return c.most_common(1)[0][0] if c else None


def thang_cua_sheet(name):
    m = re.search(r"\d+", name)
    return int(m.group()) if m else None


def idx_thang(nam, thang):
    return nam * 12 + thang


def so_sanh(h, j):
    lech = []
    for nhan, kh, kd, kieu in SO_SANH:
        a, b = h[kh], j[kd]
        tol = TOL_TIEN if kieu == "tien" else TOL_NGAY
        if abs(a - b) > tol:
            lech.append((nhan, a, b))
    return lech


def fmt(v, kieu_ngay=False):
    return ("%g" % v) if kieu_ngay else "{:,.0f}".format(v).replace(",", ".")


def diem(h, j):
    th = tokens(h["du_an"])
    if not th:
        return 0.0
    s = len(th & tokens(j["ten"] + " " + j["khach"])) / len(th)
    if h["doanh_thu_n"] > 0 and abs(h["doanh_thu_n"] - j["doanh_thu"]) <= TOL_TIEN:
        s += 0.3
    return min(s, 1.3)


Y_KIEN_SYS = ("Bạn là trợ lý đối chiếu danh sách job quay dựng. Hai bảng ghi cùng một job nhưng tên viết khác nhau, hoặc là hai job khác nhau. "
              "Chỉ dựa vào dữ liệu được đưa, không đoán thêm. Trả lời đúng một JSON: {\"ket_luan\": \"cung_job\" | \"khac_job\" | \"khong_chac\", \"ly_do\": \"một câu ngắn\"}. "
              "Chọn khong_chac nếu bằng chứng chưa đủ.")
Y_KIEN_NHAN = {"cung_job": "CÙNG job", "khac_job": "KHÁC job", "khong_chac": "không chắc"}


def hoi_y_kien(uoc, model):
    """Y kien thu hai cua AI local cho cac cap ghep uoc chung. Tra ve {ma: 'chuoi them vao dong'}. Loi mang/model thi bo qua, khong lam hong bao cao."""
    import json, urllib.request
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server"))
    try:
        import local_llm
    except Exception as e:  # noqa: BLE001
        print("Khong nap duoc local_llm, bo qua y kien thu hai: %s" % e)
        return {}
    out = {}
    for tag, ma, ten, khach, goc, lech, s, th in uoc:
        user = ("Bảng hạch toán: %s\nDatabase: \"%s\" (khách: %s, tháng %d)\nCác con số (doanh thu, ngày công, khấu hao) giữa hai dòng: %s.\nHai dòng này có phải cùng một job không?"
                % (tag, ten, khach, th, "có chỗ khác nhau" if lech else "TRÙNG NHAU"))
        try:
            r = local_llm.chat([{"role": "system", "content": Y_KIEN_SYS}, {"role": "user", "content": user}], model, None, False, 0.0, 8192, 300, 200)
            m = re.search(r"\{.*\}", r["message"].get("content") or "", re.S)
            d = json.loads(m.group(0))
            out[ma] = "  ↳ ý kiến thứ hai (%s, chỉ tham khảo): %s, %s" % (model, Y_KIEN_NHAN.get(d.get("ket_luan"), "?"), str(d.get("ly_do", ""))[:160])
        except Exception as e:  # noqa: BLE001
            out[ma] = "  ↳ ý kiến thứ hai: không lấy được (%s)" % str(e)[:60]
    try:  # nha VRAM
        urllib.request.urlopen(urllib.request.Request(local_llm.OLLAMA_URL + "/api/generate", json.dumps({"model": model, "keep_alive": 0}).encode(), {"Content-Type": "application/json"}), timeout=60).read()
    except Exception:  # noqa: BLE001
        pass
    return out


def main():
    ap = argparse.ArgumentParser(description="Doi chieu bang hach toan voi Database (chi doc)")
    ap.add_argument("hach_toan")
    ap.add_argument("database")
    ap.add_argument("--thang", help="vd 8,9,10 (mac dinh: tat ca cac thang co trong bang hach toan)")
    ap.add_argument("--nam", type=int, help="nam neu khong doc duoc tu cot ngay thuc hien")
    ap.add_argument("--ra", help="duong dan file bao cao .md day du")
    ap.add_argument("--y-kien-thu-hai", nargs="?", const="qwen3.8:27b", default=None, metavar="MODEL", help="hoi AI local them y kien cho cac cap ghep uoc chung (chi tham khao)")
    a = ap.parse_args()

    ht = fin_facts.load(a.hach_toan)
    db, db_sheet, thieu = load_db(a.database)
    loc = {int(x) for x in a.thang.split(",")} if a.thang else None
    nam_sheet = {}
    for d in ht:
        d["thang"] = thang_cua_sheet(d["sheet"])
        nam_sheet.setdefault(d["sheet"], nam_cua_sheet([x for x in ht if x["sheet"] == d["sheet"]]) or a.nam or dt.date.today().year)
        d["nam"] = nam_sheet[d["sheet"]]
    ht = [d for d in ht if d["thang"] and (not loc or d["thang"] in loc)]
    ht_thang = {idx_thang(d["nam"], d["thang"]) for d in ht}
    db_loc = [j for j in db if j["thang"] and j["nam"] and idx_thang(int(j["nam"]), int(j["thang"])) in ht_thang]

    # ghep: tinh diem moi cap (Database trong cua so thang -2..+1 so voi thang cua hach toan), gan tham lam tu diem cao
    cap = []
    for hi, h in enumerate(ht):
        t = idx_thang(h["nam"], h["thang"])
        for j in db:
            if j["thang"] and j["nam"] and -2 <= idx_thang(int(j["nam"]), int(j["thang"])) - t <= 1:
                s = diem(h, j)
                if s >= NGUONG_UOC_CHUNG:
                    cap.append((s, hi, j["ma"]))
    cap.sort(key=lambda x: -x[0])
    ghep, dung = {}, set()
    mo_ho = {}
    top = collections.defaultdict(list)
    for s, hi, ma in cap:
        top[hi].append((s, ma))
    for hi, lst in top.items():
        if len(lst) > 1 and abs(lst[0][0] - lst[1][0]) < 1e-9:
            mo_ho[hi] = [m for s, m in lst if abs(s - lst[0][0]) < 1e-9][:3]
    for s, hi, ma in cap:
        if hi in ghep or ma in dung or hi in mo_ho:
            continue
        ghep[hi] = (ma, s)
        dung.add(ma)
    by_ma = {j["ma"]: j for j in db}

    khop, lech_list, uoc, chi_ht = [], [], [], []
    for hi, h in enumerate(ht):
        tag = "%s dòng %d '%s'" % (h["sheet"], h["dong"], h["du_an"])
        if hi in mo_ho:
            chi_ht.append((tag, "MƠ HỒ: ghép được với %s (điểm bằng nhau), CẦN XÁC NHẬN" % ", ".join(mo_ho[hi])))
        elif hi in ghep:
            ma, s = ghep[hi]
            j = by_ma[ma]
            lech = so_sanh(h, j)
            chac = s >= 1.0 and (tokens(h["du_an"]) <= tokens(j["ten"] + " " + j["khach"]))
            info = (tag, ma, j["ten"], j["khach"], j["doanh_thu_goc"], lech, round(s, 2), int(j["thang"]))
            if not chac:
                uoc.append(info)
            elif lech:
                lech_list.append(info)
            else:
                khop.append(info)
        else:
            chi_ht.append((tag, "không thấy job nào trong Database (cửa sổ tháng -2..+1)"))
    chi_db = [j for j in db_loc if j["ma"] not in dung]

    cap_dong = lambda lst: lst[:MAX_DONG]
    out = []
    out.append("job_doi_chieu: hạch toán %d dòng (tháng %s) | Database %d job cùng kỳ (sheet %s)" % (
        len(ht), ",".join(str(x % 12 or 12) for x in sorted(ht_thang)), len(db_loc), db_sheet))
    if thieu:
        out.append("LƯU Ý: không thấy các cột Database: %s (các so sánh liên quan bị bỏ qua thành 0)" % ", ".join(thieu))
    tom = "Khớp đầy đủ: %d | Lệch: %d | Ghép ước chừng, cần xác nhận: %d | Chỉ có ở hạch toán: %d | Chỉ có ở Database: %d" % (
        len(khop), len(lech_list), len(uoc), len(chi_ht), len(chi_db))
    out.append(tom)
    if loc:
        out.append("LƯU Ý: Database tính tháng theo ngày chốt, có thể khác tháng thực hiện; thấy nhiều dòng 'chỉ có ở' thì chạy không --thang để đối chiếu cả năm.")

    def dong_lech(info, ghi_chu=""):
        tag, ma, ten, khach, goc, lech, s, th = info
        ds = "; ".join("%s: hạch toán %s | Database %s" % (n, fmt(x, "ngày" in n), fmt(y, "ngày" in n)) for n, x, y in lech) or "các số trùng nhau"
        return "- [%s ↔ %s '%s' / %s, tháng %d, điểm %s%s] %s" % (tag, ma, ten, khach, th, s, ghi_chu, ds)

    sec = []
    if lech_list:
        sec.append(("LỆCH (job đã ghép chắc, số khác nhau)", [dong_lech(i, "; doanh thu so với " + i[4]) for i in lech_list]))
    if uoc:
        y_kien = hoi_y_kien(uoc, a.y_kien_thu_hai) if a.y_kien_thu_hai else {}
        sec.append(("GHÉP ƯỚC CHỪNG, CẦN QUANG XÁC NHẬN (rồi mới xét lệch)", [dong_lech(i) + ("\n" + y_kien[i[1]] if i[1] in y_kien else "") for i in uoc]))
    if chi_ht:
        sec.append(("CHỈ CÓ Ở HẠCH TOÁN", ["- [%s] %s" % t for t in chi_ht]))
    if chi_db:
        sec.append(("CHỈ CÓ Ở DATABASE (cùng kỳ)", ["- %s '%s' / %s, tháng %d: doanh thu %s" % (j["ma"], j["ten"], j["khach"], j["thang"], fmt(j["doanh_thu"])) for j in chi_db]))
    for title, lines in sec:
        out.append("-- %s: %d --" % (title, len(lines)))
        out.extend(cap_dong(lines))
        if len(lines) > MAX_DONG:
            out.append("  … và %d dòng nữa (xem file báo cáo)" % (len(lines) - MAX_DONG))
    print("\n".join(out))

    if a.ra:
        full = ["# Báo cáo đối chiếu job (%s)" % dt.datetime.now().strftime("%d/%m/%Y %H:%M"), "", out[0], tom, ""]
        for title, lines in sec:
            full += ["## %s (%d)" % (title, len(lines)), ""] + lines + [""]
        full += ["## Khớp đầy đủ (%d)" % len(khop), ""] + ["- %s ↔ %s" % (i[0], i[1]) for i in khop]
        os.makedirs(os.path.dirname(os.path.abspath(a.ra)), exist_ok=True)
        open(a.ra, "w", encoding="utf-8", newline="\n").write("\n".join(full) + "\n")
        print("Báo cáo đầy đủ: " + a.ra)


if __name__ == "__main__":
    main()
