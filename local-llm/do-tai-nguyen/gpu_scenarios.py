"""Do muc su dung tai nguyen khi chay LLM (Gemma) + proxy NVENC, co/khong co gpu-queue. Dung: python gpu_scenarios.py <thu_muc_ra> [S0,S1,S2,S3]"""
import ctypes, json, os, re, statistics, subprocess, sys, threading, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = sys.argv[1]; WHICH = (sys.argv[2] if len(sys.argv) > 2 else "S0,S1,S2,S3").split(",")
os.makedirs(OUT, exist_ok=True)
PY = sys.executable
ZALO = os.path.normpath(os.path.join(HERE, "..", "danh-gia", "zalo_summarize.py"))
LIB = os.path.normpath(os.path.join(HERE, "..", "..", "gpu-queue.functions.ps1")).replace("\\", "/")  # dau / de PowerShell 5.1 khong hong duong dan co dau tieng Viet
BASE = "http://127.0.0.1:11434"

def ram_free_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ("tp", "ap", "tpf", "apf", "tv", "av", "ave")]
    s = MS(); s.dwLength = ctypes.sizeof(s); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)); return s.ap / 1e9

def smi():
    o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu,utilization.encoder,power.draw,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip().split(",")
    return [float(x) for x in o]

def unload_and_settle():
    try:
        ps = json.load(urllib.request.urlopen(BASE + "/api/ps", timeout=10))["models"]
        for m in ps:
            urllib.request.urlopen(urllib.request.Request(BASE + "/api/generate", data=json.dumps({"model": m["name"], "keep_alive": 0}).encode(), headers={"Content-Type": "application/json"}), timeout=30)
    except Exception: pass
    for _ in range(40):
        if smi()[0] < 3200: break
        time.sleep(1)
    time.sleep(2)

_n = [0]
def launch(args):
    _n[0] += 1; path = os.path.join(OUT, f"job_{_n[0]}.txt"); f = open(path, "w", encoding="utf-8", errors="replace")
    p = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"] + args, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT)
    p._out = path; p._f = f; return p

def collect(p, limit):
    try: p.wait(timeout=limit); timed_out = False
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True); timed_out = True
    p._f.close(); txt = open(p._out, encoding="utf-8", errors="replace").read()
    return txt + (" HARD_TIMEOUT" if timed_out else "")

def run(name, jobs):
    unload_and_settle(); base = smi()[0]; samples = []; stop = threading.Event()
    def sampler():
        while not stop.is_set():
            try: samples.append((time.time(), *smi(), ram_free_gb()))
            except Exception: pass
            time.sleep(0.4)
    th = threading.Thread(target=sampler, daemon=True); th.start(); t0 = time.time()
    procs = []
    for delay, args in jobs:
        time.sleep(max(0, delay - (time.time() - t0))); procs.append(launch(args))
    outs = [collect(p, 240) for p in procs]; t1 = time.time(); stop.set(); th.join()
    ev = {}; text = "\n".join(outs)
    for m in re.finditer(r"TS ([\d.]+) (\w+)", text): ev[m.group(2)] = float(m.group(1)) - t0
    z = re.search(r"ZALO_RESULT .*?wall=([\d.]+)s tokens=(\d+) tok_s=([\d.]+) facts=(\d+)/(\d+)", text); n = re.search(r"NVENC_RESULT frames=(\d+) fps=([\d.]+) exit=(\d+)", text)
    waits = re.findall(r"\[gpu-queue\] (.*)", text)
    win = [s for s in samples if s[0] >= t0]
    r = {"kich_ban": name, "tong_thoi_gian_s": round(t1 - t0, 1), "vram_nen_mib": base, "vram_dinh_mib": max(s[1] for s in win), "vram_con_lai_toi_thieu_mib": round(12227 - max(s[1] for s in win)),
         "gpu_util_dinh_pct": max(s[2] for s in win), "gpu_util_tb_pct": round(statistics.mean(s[2] for s in win), 1), "encoder_dinh_pct": max(s[3] for s in win),
         "cong_suat_dinh_w": max(s[4] for s in win), "nhiet_dinh_c": max(s[5] for s in win), "ram_trong_toi_thieu_gb": round(min(s[6] for s in win), 1)}
    if z: r.update({"llm_wall_s": float(z.group(1)), "llm_tok_s": float(z.group(3)), "llm_facts": f"{z.group(4)}/{z.group(5)}"})
    if n: r.update({"nvenc_fps": float(n.group(2)), "nvenc_frames": int(n.group(1)), "nvenc_exit": int(n.group(3))})
    for k in ("LLM_REQUEST", "LLM_START", "LLM_END", "NVENC_REQUEST", "NVENC_START", "NVENC_END"):
        if k in ev: r["t_" + k] = round(ev[k], 1)
    if "LLM_START" in ev: r["llm_cho_s"] = round(ev["LLM_START"] - ev["LLM_REQUEST"], 1)
    if "NVENC_START" in ev: r["nvenc_cho_s"] = round(ev["NVENC_START"] - ev["NVENC_REQUEST"], 1)
    r["hang_doi_ghi"] = list(dict.fromkeys(waits))[:6]; r["treo_cung"] = "HARD_TIMEOUT" in text
    open(os.path.join(OUT, name + ".csv"), "w").write("t,vram_mib,gpu_util,enc_util,power_w,temp_c,ram_free_gb\n" + "\n".join(",".join(f"{v:.1f}" for v in (s[0] - t0, *s[1:])) for s in win))
    print(json.dumps(r, ensure_ascii=False)); return r

NV = lambda extra=(): [os.path.join(HERE, "job-nvenc.ps1"), "-Lib", LIB, "-Log", os.path.join(OUT, "nvenc.log")] + list(extra)
LL = lambda keep, extra=(): [os.path.join(HERE, "job-llm.ps1"), "-Lib", LIB, "-Py", PY, "-Script", ZALO, "-KeepAlive", keep, "-Tmp", os.path.join(OUT, "llm_tmp")] + list(extra)
res = []
if "S0" in WHICH: res.append(run("S0_proxy_NVENC_mot_minh", [(0, NV(["-NoQueue"]))]))
if "S1" in WHICH: res.append(run("S1_LLM_mot_minh_qua_gpuqueue", [(0, LL("0"))]))
if "S2" in WHICH: res.append(run("S2_LLM+proxy_cung_luc_KHONG_hang_doi", [(0, LL("0", ["-NoQueue"])), (0, NV(["-NoQueue"]))]))
if "S3" in WHICH: res.append(run("S3_LLM+proxy_QUA_hang_doi", [(0, LL("30s")), (3, NV())]))
unload_and_settle()
json.dump(res, open(os.path.join(OUT, "ket-qua-do.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
