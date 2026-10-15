"""link-proxy: link proxy do proxy-maker tao vao cac clip trong Media Pool cua DaVinci Resolve dang mo.

Voi moi clip nam trong thu muc video goc (mac dinh "goc", lay tu ingest.config.json), tim proxy cung ten o
<thu muc du an>\\proxy\\<ten>.mp4 roi LinkProxyMedia. Clip da co proxy thi bo qua; clip chua co file proxy duoc bao.
Chay lai bao nhieu lan cung duoc. Can Resolve dang mo va Preferences > System > General > External scripting = Local.

    python link-proxy.py
"""
import importlib.util
import json
import os
import sys
from importlib.machinery import ExtensionFileLoader

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FUSIONSCRIPT = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"


def connect():
    loader = ExtensionFileLoader("fusionscript", FUSIONSCRIPT)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("fusionscript", loader))
    loader.exec_module(module)
    return module.scriptapp("Resolve")


def walk(folder):
    yield from folder.GetClipList() or []
    for sub in folder.GetSubFolderList() or []:
        yield from walk(sub)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "ingest.config.json"), encoding="utf-8") as f:
        video_folder = json.load(f)["subfolders"]["video"]

    resolve = connect()
    if not resolve:
        sys.exit("Khong ket noi duoc Resolve. Resolve da mo chua? External scripting dang la Local chua?")
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        sys.exit("Resolve chua mo du an nao.")
    print(f"Du an Resolve: {project.GetName()}")

    linked, already, missing, failed = [], [], [], []
    for clip in walk(project.GetMediaPool().GetRootFolder()):
        path = clip.GetClipProperty("File Path")
        if not path or os.path.basename(os.path.dirname(path)).lower() != video_folder.lower():
            continue
        name = os.path.basename(path)
        if clip.GetClipProperty("Proxy") not in (None, "", "None"):
            already.append(name)
            continue
        proxy = os.path.join(os.path.dirname(os.path.dirname(path)), "proxy", os.path.splitext(name)[0] + ".mp4")
        if not os.path.isfile(proxy):
            missing.append(name)
        elif clip.LinkProxyMedia(proxy):
            linked.append(name)
        else:
            failed.append(name)

    print(f"Moi link: {len(linked)} | Da co san: {len(already)} | Chua co file proxy: {len(missing)} | Link that bai: {len(failed)}")
    for label, names in (("Chua co file proxy", missing), ("Link that bai", failed)):
        if names:
            print(f"{label}: {', '.join(names[:10])}{' ...' if len(names) > 10 else ''}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
