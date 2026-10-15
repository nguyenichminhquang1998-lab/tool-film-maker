"""Tinh so lieu tu bang hach toan (bang code, khong dung LLM de cong tru)."""
import datetime as dt, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_read import read_xlsx

COLS = ["ngay", "du_an", "doanh_thu", "chi_phi_ngoai", "kh_fx30", "kh_flycam", "kh_fisheye", "ngay_dung", "tong_kh", "loi_nhuan", "bien_pct",
        "ngay_tien_ve", "thuc_nhan", "cong_no", "quy_thiet_bi", "sinh_hoat", "tiet_kiem", "co_phieu", "bo_me", "phat_trien", "quy_khac"]
EPOCH = dt.date(1899, 12, 30)

def to_date(v):
    if isinstance(v, (int, float)) and 20000 < v < 80000: return EPOCH + dt.timedelta(days=int(v))
    if isinstance(v, str):
        m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", v)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3)); y += 2000 if y < 100 else 0
            try: return dt.date(y, mo, d)
            except ValueError: return None
    return None

def num(v):
    return float(v) if isinstance(v, (int, float)) else 0.0

def load(path):
    rows = []
    for sheet, data in read_xlsx(path).items():
        for i, r in enumerate(data[1:], start=2):
            r = list(r) + [None] * (21 - len(r))
            name = (r[1] or "").strip() if isinstance(r[1], str) else ""
            if not name: continue
            d = dict(zip(COLS, r[:21])); d["sheet"] = sheet; d["dong"] = i
            d["ngay_d"] = to_date(d["ngay"]); d["tien_ve_d"] = to_date(d["ngay_tien_ve"])
            for k in COLS[2:11] + COLS[12:13] + COLS[14:]: d[k + "_n"] = num(d[k])
            d["cong_no_s"] = (d["cong_no"] or "").strip() if isinstance(d["cong_no"], str) else ""
            rows.append(d)
    return rows

def facts(rows):
    out = {"so_du_an": len(rows), "theo_thang": [], "du_an": [], "canh_bao": []}
    months = {}
    for d in rows:
        key = d["sheet"]; months.setdefault(key, []).append(d)
    for sheet, rs in months.items():
        rev = sum(x["doanh_thu_n"] for x in rs); cb = sum(x["chi_phi_ngoai_n"] for x in rs); kh = sum(x["tong_kh_n"] for x in rs)
        ln = sum(x["loi_nhuan_n"] for x in rs); got = sum(x["thuc_nhan_n"] for x in rs); ndays = sum(x["ngay_dung_n"] for x in rs)
        out["theo_thang"].append({"thang": sheet, "so_du_an": len(rs), "doanh_thu": rev, "chi_phi_ngoai": cb, "khau_hao": kh, "loi_nhuan": ln,
                                   "bien_pct": round(100 * ln / rev, 1) if rev else None, "thuc_nhan": got, "ngay_dung": ndays,
                                   "chua_thu": sum(x["doanh_thu_n"] - x["thuc_nhan_n"] for x in rs if x["cong_no_s"] and "TẤT TOÁN" not in x["cong_no_s"].upper() or (not x["thuc_nhan_n"] and x["doanh_thu_n"]))})
    for d in rows:
        delay = (d["tien_ve_d"] - d["ngay_d"]).days if d["ngay_d"] and d["tien_ve_d"] else None
        out["du_an"].append({"thang": d["sheet"], "du_an": d["du_an"], "doanh_thu": d["doanh_thu_n"], "chi_phi_ngoai": d["chi_phi_ngoai_n"], "khau_hao": d["tong_kh_n"],
                              "loi_nhuan": d["loi_nhuan_n"], "bien_pct": round(100 * d["loi_nhuan_n"] / d["doanh_thu_n"], 1) if d["doanh_thu_n"] else None,
                              "ngay_dung": d["ngay_dung_n"], "loi_nhuan_moi_ngay_dung": round(d["loi_nhuan_n"] / d["ngay_dung_n"]) if d["ngay_dung_n"] else None,
                              "thuc_nhan": d["thuc_nhan_n"], "cong_no": d["cong_no_s"] or "(trống)", "so_ngay_cho_tien": delay})
    # canh bao do kiem tra du lieu bang code
    for d in rows:
        tag = f"{d['sheet']} dòng {d['dong']} '{d['du_an']}'"
        if d["doanh_thu_n"] and abs(d["doanh_thu_n"] - d["chi_phi_ngoai_n"] - d["tong_kh_n"] - d["loi_nhuan_n"]) > 1000:
            out["canh_bao"].append(f"{tag}: doanh thu - chi phí ngoài - khấu hao = {d['doanh_thu_n']-d['chi_phi_ngoai_n']-d['tong_kh_n']:,.0f} nhưng ô lợi nhuận ghi {d['loi_nhuan_n']:,.0f}")
        if d["doanh_thu_n"] and d["bien_pct_n"] and abs(d["bien_pct_n"] * (100 if d["bien_pct_n"] <= 1.5 else 1) - 100 * d["loi_nhuan_n"] / d["doanh_thu_n"]) > 1:
            out["canh_bao"].append(f"{tag}: ô biên lợi nhuận không khớp lợi nhuận/doanh thu")
        if not d["ngay_d"]: out["canh_bao"].append(f"{tag}: ô ngày thực hiện không đọc được ({d['ngay']!r})")
        if d["doanh_thu_n"] and not d["thuc_nhan_n"]: out["canh_bao"].append(f"{tag}: doanh thu {d['doanh_thu_n']:,.0f} chưa thu; tình trạng công nợ: {d['cong_no_s'] or 'trống'}")
        if d["cong_no_s"] and "TẤT TOÁN" in d["cong_no_s"].upper() and d["doanh_thu_n"] and d["thuc_nhan_n"] and abs(d["thuc_nhan_n"] - d["doanh_thu_n"]) > 1000:
            out["canh_bao"].append(f"{tag}: đã tất toán nhưng thực nhận {d['thuc_nhan_n']:,.0f} khác doanh thu {d['doanh_thu_n']:,.0f}")
    tot = {k: sum(m[k] for m in out["theo_thang"]) for k in ("so_du_an", "doanh_thu", "chi_phi_ngoai", "khau_hao", "loi_nhuan", "thuc_nhan", "ngay_dung")}
    tot["bien_pct"] = round(100 * tot["loi_nhuan"] / tot["doanh_thu"], 1) if tot["doanh_thu"] else None
    out["tong"] = tot
    return out

if __name__ == "__main__":
    import json
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    f = facts(load(r"D:\Bảng hoạch toán thu chi & Đầu tư.xlsx"))
    print("TONG:", json.dumps(f["tong"], ensure_ascii=False))
    for m in f["theo_thang"]: print(m)
    print("Canh bao du lieu:", len(f["canh_bao"]))
    for c in f["canh_bao"]: print(" -", c)
