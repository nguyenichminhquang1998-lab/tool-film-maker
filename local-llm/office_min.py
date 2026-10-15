"""Ghi file .xlsx va .docx toi gian, khong can thu vien ngoai (chi zipfile + xml)."""
import zipfile
from xml.sax.saxutils import escape

def _col(n):
    s = ""
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s

# ---------------- XLSX ----------------
def write_xlsx(path, sheets, widths=None):
    """sheets: {ten: [[o, o, ...], ...]}; dong dau la tieu de. So -> dinh dang #,##0; chuoi -> text."""
    widths = widths or {}
    names = list(sheets)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          + "".join(f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(len(names)))
          + "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
          + "".join(f'<sheet name="{escape(n[:31])}" sheetId="{i+1}" r:id="rId{i+1}"/>' for i, n in enumerate(names)) + "</sheets></workbook>")
    wbrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
              + "".join(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i+1}.xml"/>' for i in range(len(names)))
              + f'<Relationship Id="rId{len(names)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<numFmts count="1"><numFmt numFmtId="164" formatCode="0.0"/></numFmts>'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8EFE4"/></patternFill></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment wrapText="1" vertical="center"/></xf>'
              '<xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
              '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
              '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels); z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wbrels); z.writestr("xl/styles.xml", styles)
        for i, n in enumerate(names):
            rows = sheets[n]; ws = widths.get(n, [])
            x = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>']
            if ws: x.append("<cols>" + "".join(f'<col min="{j+1}" max="{j+1}" width="{w}" customWidth="1"/>' for j, w in enumerate(ws)) + "</cols>")
            x.append("<sheetData>")
            for r, row in enumerate(rows, start=1):
                x.append(f'<row r="{r}">')
                for c, v in enumerate(row, start=1):
                    ref = f"{_col(c)}{r}"
                    if v is None or v == "": continue
                    if r == 1: x.append(f'<c r="{ref}" s="1" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>')
                    elif isinstance(v, bool): x.append(f'<c r="{ref}" t="inlineStr"><is><t>{"Có" if v else "Không"}</t></is></c>')
                    elif isinstance(v, float) and not v.is_integer(): x.append(f'<c r="{ref}" s="3"><v>{v}</v></c>')
                    elif isinstance(v, (int, float)): x.append(f'<c r="{ref}" s="2"><v>{int(v)}</v></c>')
                    else: x.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>')
                x.append("</row>")
            x.append("</sheetData></worksheet>")
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", "".join(x))

# ---------------- DOCX ----------------
def _run(text, bold=False, size=None, color=None):
    pr = ("<w:b/>" if bold else "") + (f'<w:color w:val="{color}"/>' if color else "") + (f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else "")
    return f'<w:r>{"<w:rPr>" + pr + "</w:rPr>" if pr else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'

def _inline(text, size=None):
    """Ho tro **dam** trong van ban."""
    parts = text.split("**"); out = []
    for i, p in enumerate(parts):
        if p: out.append(_run(p, bold=(i % 2 == 1), size=size))
    return "".join(out)

def write_docx(path, blocks):
    """blocks: ('h1', text) | ('h2', text) | ('p', text) | ('bullet', text) | ('table', [[...], ...]) | ('note', text)"""
    body = []
    for kind, content in blocks:
        if kind == "h1": body.append(f'<w:p><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>{_run(content, bold=True, size=36)}</w:p>')
        elif kind == "h2": body.append(f'<w:p><w:pPr><w:spacing w:before="200" w:after="80"/></w:pPr>{_run(content, bold=True, size=28, color="2F6F4F")}</w:p>')
        elif kind == "p": body.append(f'<w:p><w:pPr><w:spacing w:after="100"/></w:pPr>{_inline(content, 22)}</w:p>')
        elif kind == "note": body.append(f'<w:p><w:pPr><w:spacing w:after="100"/></w:pPr>{_run(content, size=20, color="777777")}</w:p>')
        elif kind == "bullet": body.append(f'<w:p><w:pPr><w:ind w:left="360" w:hanging="260"/><w:spacing w:after="60"/></w:pPr>{_run("•  ", size=22)}{_inline(content, 22)}</w:p>')
        elif kind == "table":
            b = '<w:top w:val="single" w:sz="4" w:color="BBBBBB"/><w:left w:val="single" w:sz="4" w:color="BBBBBB"/><w:bottom w:val="single" w:sz="4" w:color="BBBBBB"/><w:right w:val="single" w:sz="4" w:color="BBBBBB"/><w:insideH w:val="single" w:sz="4" w:color="BBBBBB"/><w:insideV w:val="single" w:sz="4" w:color="BBBBBB"/>'
            t = [f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{b}</w:tblBorders></w:tblPr>']
            for ri, row in enumerate(content):
                t.append("<w:tr>")
                for cell in row:
                    shade = '<w:shd w:val="clear" w:color="auto" w:fill="E8EFE4"/>' if ri == 0 else ""
                    t.append(f'<w:tc><w:tcPr>{shade}</w:tcPr><w:p>{_run(str(cell), bold=(ri == 0), size=19)}</w:p></w:tc>')
                t.append("</w:tr>")
            t.append("</w:tbl><w:p/>"); body.append("".join(t))
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           + "".join(body) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels); z.writestr("word/document.xml", doc)
