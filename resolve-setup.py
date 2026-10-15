"""resolve-setup: mo DaVinci Resolve, tao du an theo thu muc du an, nhap clip trong goc\\ va link proxy (link-proxy.py).

    python resolve-setup.py "<thu muc du an>"                 # chi XEM KE HOACH, khong lam gi
    python resolve-setup.py "<thu muc du an>" --yes           # lam that
    python resolve-setup.py "<thu muc du an>" --yes --name "Ten du an Resolve"

An toan: KHONG BAO GIO ghi de. Ten du an Resolve da co thi dung lai (exit 2) va chi cach doi ten.
Khong tao proxy (nang GPU, chi khi Quang yeu cau): chi link nhung proxy da co o <thu muc du an>\\proxy\\.
Ket qua: 1 dong JSON cuoi cung tren stdout; tien trinh in ra stderr. Exit 0 = ok, 1 = loi, 2 = bi tu choi (trung ten).
Can: Preferences > System > General > External scripting = Local.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from importlib.machinery import ExtensionFileLoader

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "mcp_server"))
import javis_tools  # noqa: E402  (open_app: mo Resolve qua shortcut Start Menu)

FUSIONSCRIPT = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
UNTITLED = "Untitled Project"
PROXY_MODE = "1"  # perfProxyMediaMode: 0 tat, 1 dung proxy khi co (Quang chon), 2 chi khi mat file goc
LAUNCH_WAIT_SECONDS = 120

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def finish(data, code=0):
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(code)


def load_module():
    loader = ExtensionFileLoader("fusionscript", FUSIONSCRIPT)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("fusionscript", loader))
    loader.exec_module(module)
    return module


def clips_and_proxies(project_dir):
    with open(os.path.join(HERE, "ingest.config.json"), encoding="utf-8") as f:
        video_folder = json.load(f)["subfolders"]["video"]
    goc = os.path.join(project_dir, video_folder)
    if not os.path.isdir(goc):
        finish({"ok": False, "loi": f"Khong thay thu muc video '{video_folder}' trong {project_dir}"}, 1)
    clips = sorted(f for f in os.listdir(goc) if os.path.isfile(os.path.join(goc, f)))
    proxy_dir = os.path.join(project_dir, "proxy")
    have = [c for c in clips if os.path.isfile(os.path.join(proxy_dir, os.path.splitext(c)[0] + ".mp4"))]
    return goc, clips, have


def resolve_path(ms, path):
    """Tien trinh Python thuong goi truc tiep duoc (ky tu co dau di qua dung). Chi khi Resolve khong thay thu muc moi di tung cap
    theo chuoi do CHINH Resolve tra ve (script chay trong sandbox cua Resolve MCP tung lech ma). Luu y: GetSubFolderList("D:\\") tra ve
    rong, nen di tung cap phai bat dau tu cap thu 2 (D:\\Quang)."""
    if ms.GetFileList(path):
        return path
    parts = os.path.normpath(path).split(os.sep)
    current = os.sep.join(parts[:2])
    for part in parts[2:]:
        want = unicodedata.normalize("NFC", part).lower()
        subs = ms.GetSubFolderList(current) or []
        current = next((s for s in subs if unicodedata.normalize("NFC", os.path.basename(s)).lower() == want), None)
        if current is None:
            return None
    return current


def walk(folder):
    yield from folder.GetClipList() or []
    for sub in folder.GetSubFolderList() or []:
        yield from walk(sub)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("project_dir")
    p.add_argument("--yes", action="store_true", help="lam that (mac dinh chi xem ke hoach)")
    p.add_argument("--name", help="ten du an Resolve (mac dinh: ten thu muc du an)")
    a = p.parse_args()

    project_dir = os.path.normpath(a.project_dir)
    if not os.path.isdir(project_dir):
        finish({"ok": False, "loi": f"Khong co thu muc: {project_dir}"}, 1)
    goc, clips, have = clips_and_proxies(project_dir)
    name = a.name or os.path.basename(project_dir)

    module = load_module()
    resolve = module.scriptapp("Resolve")
    plan = {
        "thu_muc_du_an": project_dir,
        "ten_du_an_resolve": name,
        "so_clip_trong_goc": len(clips),
        "so_clip_da_co_proxy": len(have),
        "so_clip_thieu_proxy": len(clips) - len(have),
        "resolve_dang_mo": resolve is not None,
        "chinh_sach": "khong ghi de du an co san; khong tao proxy; dat perfProxyMediaMode = " + PROXY_MODE + " cho du an moi",
    }
    if resolve:
        pm = resolve.GetProjectManager()
        cur = pm.GetCurrentProject()
        plan["du_an_dang_mo"] = cur.GetName() if cur else None
        plan["trung_ten_voi_du_an_co_san"] = name in (pm.GetProjectListInCurrentFolder() or [])
    else:
        plan["trung_ten_voi_du_an_co_san"] = "chua biet (Resolve chua mo)"

    if not a.yes:
        plan["se_lam"] = ["mo Resolve neu chua mo", f"tao du an '{name}'", f"nhap {len(clips)} clip", f"link {len(have)} proxy", "luu du an"]
        finish({"ok": True, "che_do": "ke_hoach", "da_lam_gi": "khong co gi, chi xem", **plan})

    # ---- lam that ----
    if not resolve:
        log("Resolve chua mo, dang mo ...")
        r = javis_tools.open_app("resolve", javis_tools.load_config())
        if not r.get("ok"):
            finish({"ok": False, "loi": "Khong mo duoc Resolve: " + str(r.get("error"))}, 1)
        deadline = time.time() + LAUNCH_WAIT_SECONDS
        while time.time() < deadline and not resolve:
            time.sleep(3)
            resolve = module.scriptapp("Resolve")
        if not resolve:
            finish({"ok": False, "loi": f"Resolve khong san sang sau {LAUNCH_WAIT_SECONDS} giay (External scripting = Local chua?)"}, 1)
        time.sleep(3)

    pm = resolve.GetProjectManager()
    if name in (pm.GetProjectListInCurrentFolder() or []):
        finish({"ok": False, "bi_tu_choi": True, "loi": f"Da co du an Resolve ten '{name}'. Khong ghi de.", "goi_y": "Dung --name (hoac resolve_project_name) de dat ten khac."}, 2)

    cur = pm.GetCurrentProject()
    saved_current = None
    if cur and cur.GetName() != UNTITLED:
        pm.SaveProject()  # luu du an dang mo truoc khi chuyen sang du an moi, de khong mat viec
        saved_current = cur.GetName()
        log(f"Da luu du an dang mo: {saved_current}")

    project = pm.CreateProject(name)
    if not project:
        finish({"ok": False, "loi": f"CreateProject('{name}') that bai"}, 1)
    log(f"Da tao du an Resolve: {name}")

    ms = resolve.GetMediaStorage()
    goc_in_resolve = resolve_path(ms, goc)
    files = ms.GetFileList(goc_in_resolve) if goc_in_resolve else []
    items = ms.AddItemListToMediaPool(files) if files else []
    log(f"Nhap clip: Resolve thay {len(files)} file, nhap duoc {len(items or [])}")
    project.SetSetting("perfProxyMediaMode", PROXY_MODE)

    link = subprocess.run(
        [sys.executable, "-I", os.path.join(HERE, "link-proxy.py")], capture_output=True, timeout=300, cwd=HERE
    )
    link_out = link.stdout.decode("utf-8", errors="replace")
    m = re.search(r"Moi link: (\d+) \| Da co san: (\d+) \| Chua co file proxy: (\d+) \| Link that bai: (\d+)", link_out)
    log(link_out.strip())

    all_clips = list(walk(project.GetMediaPool().GetRootFolder()))
    verified = sum(1 for c in all_clips if c.GetClipProperty("Proxy") not in (None, "", "None"))
    pm.SaveProject()

    ok = len(items or []) == len(clips) and (m is not None) and int(m.group(4)) == 0
    finish(
        {
            "ok": ok,
            "che_do": "da_lam",
            **plan,
            "resolve_dang_mo": True,
            "da_luu_du_an_dang_mo_truoc_do": saved_current,
            "clip_nhap_duoc": len(items or []),
            "clip_trong_media_pool": len(all_clips),
            "proxy_moi_link": int(m.group(1)) if m else None,
            "proxy_link_that_bai": int(m.group(4)) if m else None,
            "clip_co_proxy_kiem_lai_bang_resolve": verified,
            "perfProxyMediaMode": project.GetSetting("perfProxyMediaMode"),
            "ghi_chu": "" if ok else "Co cho khong khop, xem tien trinh o stderr/log",
        },
        0 if ok else 1,
    )


if __name__ == "__main__":
    main()
