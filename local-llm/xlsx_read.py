"""Doc file .xlsx khong can thu vien ngoai (zipfile + xml)."""
import re, zipfile, xml.etree.ElementTree as ET
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

def col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0); n = 0
    for ch in letters: n = n * 26 + ord(ch) - 64
    return n - 1

def read_xlsx(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    sheets = {}
    for s in wb.find("m:sheets", NS):
        target = rels[s.get("{%s}id" % NS["r"])]
        target = target.lstrip("/"); target = target if target.startswith("xl/") else "xl/" + target
        rows = []
        for row in ET.fromstring(z.read(target)).iter("{%s}row" % NS["m"]):
            vals = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS); t = c.get("t")
                if t == "inlineStr": val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
                elif v is None: continue
                elif t == "s": val = shared[int(v.text)]
                elif t in ("str", "e", "b"): val = v.text
                else:
                    try: val = float(v.text); val = int(val) if val.is_integer() else val
                    except Exception: val = v.text
                vals[col_index(c.get("r"))] = val
            if vals: rows.append([vals.get(i) for i in range(max(vals) + 1)])
        sheets[s.get("name")] = rows
    return sheets
