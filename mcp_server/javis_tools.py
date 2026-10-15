"""
Hai tool nho cho Javis: tim file va mo app. Ca hai la ham thuan (de test), server.py chi bao lai thanh MCP tool.

- find_files: quet ten file/thu muc tren cac o liet ke trong javis.config.json (searchRoots). Chi doc ten, khong doc noi dung.
  Khong dung Windows Search vi no chi lap chi muc thu muc nguoi dung tren o C, khong co D:/E:.
- open_app: mo dung cac app co trong danh sach trang "apps" cua javis.config.json (khong nhan duong dan hay tham so tu ben ngoai).
"""

import json
import os
import subprocess
import time
import unicodedata

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "javis.config.json")
START_MENU_DIRS = [
    os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
]
MAX_COLLECTED = 2000


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fold(text: str) -> str:
    """Bo dau tieng Viet va chu hoa de so khop 'ke hoach' voi 'Ke hoach'."""
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def find_files(query: str, config: dict, limit: int = 15, extension: str = None, all_drives: bool = False) -> dict:
    """Quet theo thu tu searchRoots; thay ket qua o mot goc la dung (tru khi all_drives) vi o cung HDD
    mo lan dau co the mat ca chuc giay."""
    words = fold(query).split()
    if not words:
        return {"ok": False, "error": "Tu khoa tim kiem trong."}
    ext = "." + extension.lstrip(".").lower() if extension else None
    exclude = {fold(name) for name in config["searchExclude"]}
    started = time.monotonic()
    deadline = started + config["searchTimeLimitSeconds"]

    matches = []
    partial = truncated = False
    scanned, searched, skipped = [], [], []
    for root in config["searchRoots"]:
        root = os.path.expandvars(root)
        if not os.path.isdir(root):
            continue
        if partial or truncated or (matches and not all_drives):
            skipped.append(root)
            continue
        searched.append(root)
        for dirpath, dirnames, filenames in os.walk(root):
            if time.monotonic() > deadline:
                partial = True
                break
            dirnames[:] = [
                d
                for d in dirnames
                if fold(d) not in exclude and os.path.normcase(os.path.join(dirpath, d)) not in scanned
            ]
            entries = [(d, "folder") for d in dirnames] + [(f, "file") for f in filenames]
            for name, kind in entries:
                folded = fold(name)
                if all(w in folded for w in words) and (not ext or (kind == "file" and folded.endswith(ext))):
                    matches.append((os.path.join(dirpath, name), kind))
            if len(matches) >= MAX_COLLECTED:
                truncated = True
                break
        scanned.append(os.path.normcase(root.rstrip("\\")))

    rows = []
    for path, kind in matches:
        try:
            info = os.stat(path)
        except OSError:
            continue
        rows.append(
            {
                "path": path,
                "type": kind,
                "size_mb": round(info.st_size / 1048576, 1) if kind == "file" else None,
                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(info.st_mtime)),
                "_mtime": info.st_mtime,
            }
        )
    rows.sort(key=lambda r: r["_mtime"], reverse=True)
    for r in rows:
        del r["_mtime"]

    return {
        "ok": True,
        "query": query,
        "found": len(rows),
        "shown": rows[:limit],
        "partial": partial,
        "truncated": truncated,
        "searched": searched,
        "not_searched": skipped,
        "seconds": round(time.monotonic() - started, 1),
    }


def _find_shortcut(stem: str):
    wanted = fold(stem)
    for base in START_MENU_DIRS:
        for dirpath, _, filenames in os.walk(base):
            for name in filenames:
                title, ext = os.path.splitext(name)
                if ext.lower() == ".lnk" and fold(title) == wanted:
                    return os.path.join(dirpath, name)
    return None


def open_app(name: str, config: dict) -> dict:
    query = fold(name).strip()
    apps = config["apps"]
    available = sorted(set(apps.values()))
    if not query:
        return {"ok": False, "error": "Chua noi ten app.", "available": available}

    targets = {stem for alias, stem in apps.items() if query in (fold(alias), fold(stem))}
    if not targets:
        targets = {stem for alias, stem in apps.items() if query in fold(alias) or query in fold(stem)}
    if len(targets) != 1:
        reason = "Khong co app nao khop" if not targets else f"Co {len(targets)} app khop: {', '.join(sorted(targets))}"
        return {"ok": False, "error": f"{reason} voi '{name}'.", "available": available}

    stem = targets.pop()
    shortcut = _find_shortcut(stem)
    if not shortcut:
        return {"ok": False, "error": f"Khong thay shortcut '{stem}' trong Start Menu (app da go?)."}
    # Nho explorer.exe (da chay san) mo shortcut de app khong la tien trinh con cua server: server tat thi app khong tat theo
    subprocess.Popen(["explorer.exe", shortcut])
    return {"ok": True, "opened": stem, "note": "Da gui lenh mo; app co the mat vai giay de hien cua so."}
