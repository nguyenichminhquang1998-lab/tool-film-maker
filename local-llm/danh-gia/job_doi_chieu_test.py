"""Kiem job_doi_chieu bang du lieu GIA (khong dung du lieu that). Dung: python job_doi_chieu_test.py
Dung 2 file xlsx gia trong thu muc tam: bang hach toan (21 cot, moi thang 1 sheet) va Database (tieu de co xuong dong nhu ban that)."""
import os, subprocess, sys, tempfile
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
LD = os.path.dirname(HERE)
sys.path.insert(0, LD)
from office_min import write_xlsx

HT_HEAD = ["Ngày thực hiện", "Tên Dự án", "Doanh thu thô (A)", "Chi phí ngoài (B)", "Khấu hao FX30/ ngày", "Khấu hao Flycam/ngày",
           "Khấu hao Lens Fisheye/ngày", "Số ngày dựng PC", "Tổng Khấu hao (C)", "Lợi nhuận thuần (D)", "Biên lợi nhuận thuần %",
           "Ngày Tiền Về Thực Tế", "Số Tiền Thực Nhận", "Trạng thái Công nợ", "Quỹ", "a", "b", "c", "d", "e", "f"]
DB_HEAD = ["Mã Job", "Tên Job / Mô Tả", "Ngày Chốt", "Tháng", "Năm", "Nguồn Khách", "Tên Khách Hàng", "Giá Báo\n(VNĐ)", "Giá Chốt\n(VNĐ)",
           "Chi Phí Thuê Ngoài\n(Nhân sự/Sản xuất)", "Ngày Quay\nFX30", "Ngày Bay\nFlycam", "Ngày Lens\nFisheye", "Ngày Dựng\nPC",
           "Khấu Hao Thiết Bị\n& Vận Hành", "Lợi Nhuận Thuần\n(VNĐ)", "Đã Thu\n(VNĐ)"]


def ht_row(ngay, ten, dt, cp, fx, fly, fish, pc, kh, ln, thu):
    return [ngay, ten, dt, cp, fx, fly, fish, pc, kh, ln, 0.5, ngay, thu, "ĐÃ TẤT TOÁN", 0, 0, 0, 0, 0, 0, 0]


def db_row(ma, ten, khach, th, dt, cp, fx, fly, fish, pc, kh, ln, thu, gia_bao=None):
    return [ma, ten, "01/%02d/2026" % th, th, 2026, "x", khach, gia_bao if gia_bao is not None else dt, dt, cp, fx, fly, fish, pc, kh, ln, thu]


def main():
    tmp = tempfile.mkdtemp(prefix="jdc_test_")
    # 46000 ~ 2025-12; dung so serial ngay Excel 46245 (2026-08-10)
    d8 = 46245
    ht = {
        "tháng 8": [HT_HEAD,
                    ht_row(d8, "Lam homstay", 6300000, 0, 1, 0, 0.5, 2, 400000, 5900000, 6300000),       # 1: khop day du
                    ht_row(d8, "Sữa BeeFast", 2000000, 0, 1, 0, 0, 1, 200000, 1800000, 0),              # 2: lech (doanh thu + ngay PC)
                    ht_row(d8, "MV Moon dance", 2000000, 0, 1, 0, 0, 1, 200000, 1800000, 0),            # 3: ten rat khac, trung doanh thu -> uoc chung
                    ht_row(d8, "Job chỉ ở hạch toán", 1111000, 0, 1, 0, 0, 0, 100000, 1011000, 0),      # 4: khong co trong Database
                    ht_row(d8, "Video giống nhau", 3000000, 0, 1, 0, 0, 1, 300000, 2700000, 0)],         # 5: mo ho (2 job y het)
    }
    db = [DB_HEAD,
          db_row("P101", "Quay Lam homstay", "Lam homstay", 8, 6300000, 0, 1, 0, 0.5, 2, 400000, 5900000, 6300000),
          db_row("P102", "Sữa BeeFast", "BeeFast", 8, 2500000, 0, 1, 0, 0, 2, 200000, 2300000, 0),
          db_row("P103", "Quay clip nhảy", "chị Moon", 7, 2000000, 0, 1, 0, 0, 1, 200000, 1800000, 0),    # thang 7 -> trong cua so -2..+1
          db_row("P104", "Job chỉ ở Database", "Khách Z", 8, 4444000, 0, 1, 0, 0, 1, 100000, 4344000, 0),
          db_row("P105", "Video giống nhau", "Khách A", 8, 3000000, 0, 1, 0, 0, 1, 300000, 2700000, 0),
          db_row("P106", "Video giống nhau", "Khách A", 8, 3000000, 0, 1, 0, 0, 1, 300000, 2700000, 0)]
    f_ht, f_db, f_out = os.path.join(tmp, "hach_toan.xlsx"), os.path.join(tmp, "database.xlsx"), os.path.join(tmp, "bao_cao.md")
    write_xlsx(f_ht, ht)
    write_xlsx(f_db, {"1_DATA_MASTER": db})
    p = subprocess.run([sys.executable, "-I", os.path.join(LD, "job_doi_chieu.py"), f_ht, f_db, "--thang", "8", "--ra", f_out],
                       capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
    print(p.stdout)
    if p.returncode:
        print("LOI:", p.stderr[-800:])
        sys.exit(1)
    out = p.stdout
    loi = []

    def kiem(dieu_kien, mo_ta):
        print(("DAT  " if dieu_kien else "TRUOT"), mo_ta)
        if not dieu_kien:
            loi.append(mo_ta)

    kiem("Khớp đầy đủ: 1 " in out, "1 job khop day du (Lam homstay)")
    kiem("Lệch: 1 " in out and "P102" in out and "doanh thu: hạch toán 2.000.000 | Database 2.500.000" in out, "job lech doanh thu duoc bao dung so")
    kiem("ngày dựng PC: hạch toán 1 | Database 2" in out, "lech so ngay duoc bao")
    kiem("Ghép ước chừng, cần xác nhận: 1" in out and "P103" in out, "ten khac + trung doanh thu -> uoc chung, can xac nhan")
    kiem("Chỉ có ở hạch toán: 2" in out, "2 dong chi co o hach toan (1 that + 1 mo ho)")
    kiem("MƠ HỒ" in out and "P105" in out and "P106" in out, "2 job y het -> bao mo ho, khong tu chon")
    kiem("P104" in out and "Chỉ có ở Database" in out, "job chi co o Database duoc liet ke")
    kiem(os.path.isfile(f_out) and "Báo cáo đối chiếu job" in open(f_out, encoding="utf-8").read(), "co file bao cao day du")
    print("\nKET QUA:", "TAT CA DAT" if not loi else "%d bai truot" % len(loi))
    sys.exit(1 if loi else 0)


if __name__ == "__main__":
    main()
