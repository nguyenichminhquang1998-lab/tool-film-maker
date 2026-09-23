#!/usr/bin/env python3
"""
MCP server cho tool-film-maker.

Cho phep Claude Desktop (hoac bat ky MCP client nao) ra lenh truc tiep cho
quy trinh do the nho: liet ke o dia, quet nhanh 1 the, bat dau do the
(copy -> phan loai -> nen -> upload), va theo doi tien trinh.

Server nay CHI la lop cau noi - toan bo logic thuc su (copy, nen, upload,
integrity check...) nam trong ingest.functions.ps1 / ingest.ps1 da co san
va da duoc test rieng. Server goi lai dung nhung file do qua powershell.exe,
khong viet lai logic.

PHAI chay tren chinh may Windows co the doc/rclone/7-Zip - khong chay duoc
tu xa, vi no can quyen truy cap o dia that cua may.
"""

import asyncio
import json
import os
import time
import uuid
from enum import Enum
from typing import Optional

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# Hang so
# ============================================================

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SERVER_DIR)
INGEST_PS1 = os.path.join(REPO_ROOT, "ingest.ps1")
SCAN_HELPER_PS1 = os.path.join(SERVER_DIR, "scan_card_json.ps1")
JOBS_DIR = os.path.join(SERVER_DIR, "_mcp_jobs")
POWERSHELL_TIMEOUT_SECONDS = 60

mcp = MCPServer("tool_film_maker_mcp")

# job_id -> {"process": asyncio.subprocess.Process, "log_path": str, "started": float}
JOBS: dict[str, dict] = {}


# ============================================================
# Tien ich dung chung
# ============================================================


class DestChoice(str, Enum):
    """Dich upload: gg Drive / OneDrive / ca hai."""

    DRIVE = "drive"
    ONEDRIVE = "onedrive"
    BOTH = "both"


async def _run_powershell_json(args: list[str]) -> dict:
    """Chay 1 lenh PowerShell mong doi tra ve dung 1 dong JSON tren stdout.

    Dung chung cho moi tool goi ra ngoai PowerShell de tranh lap code xu ly
    subprocess + parse JSON + timeout o tung tool rieng le.
    """
    full_args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", *args]
    try:
        proc = await asyncio.create_subprocess_exec(
            *full_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=POWERSHELL_TIMEOUT_SECONDS
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "Khong tim thay powershell.exe. Server nay phai chay tren Windows.",
        }
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "error": f"PowerShell khong phan hoi sau {POWERSHELL_TIMEOUT_SECONDS}s (qua thoi gian cho).",
        }

    if proc.returncode != 0 and not stdout.strip():
        return {
            "ok": False,
            "error": f"PowerShell loi (exit code {proc.returncode}): {stderr.decode('utf-8', errors='replace').strip()}",
        }

    text = stdout.decode("utf-8", errors="replace").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": f"Khong parse duoc JSON tu PowerShell. Output tho: {text[:500]}",
        }


_DEST_ALIASES = {
    "download": "Downloads",
    "downloads": "Downloads",
    "tải xuống": "Downloads",
    "tai xuong": "Downloads",
    "desktop": "Desktop",
    "màn hình": "Desktop",
    "man hinh": "Desktop",
    "document": "Documents",
    "documents": "Documents",
    "tài liệu": "Documents",
    "tai lieu": "Documents",
}


def _resolve_dest_folder(dest_folder: str) -> tuple[Optional[str], Optional[str]]:
    """Doi 'downloads' / '%USERPROFILE%\\X' / 'E:\\Backup' thanh duong dan tuyet doi.

    Tra ve (duong_dan, None) neu hop le, hoac (None, thong_bao_loi).
    """
    raw = dest_folder.strip().strip('"')
    alias = _DEST_ALIASES.get(raw.lower())
    if alias:
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        return os.path.join(home, alias), None

    expanded = os.path.expanduser(os.path.expandvars(raw))
    if not os.path.isabs(expanded):
        return None, (
            f"dest_folder '{dest_folder}' khong phai duong dan day du. Dung ten quen thuoc "
            "('downloads', 'desktop', 'documents') hoac duong dan day du, vi du 'E:\\Backup'."
        )
    return expanded, None


def _normalize_drive(drive: str) -> str:
    """Chuan hoa 'E' / 'E:' / 'E:\\' ve dung dang 'E:\\'."""
    drive = drive.strip().rstrip("\\")
    if not drive.endswith(":"):
        drive = drive + ":"
    return drive + "\\"


# ============================================================
# Tool 1: liet ke o dia roi (the nho / USB) dang cam vao may
# ============================================================


@mcp.tool(
    name="ingest_list_drives",
    annotations={
        "title": "Liet ke the nho / USB dang cam",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def ingest_list_drives() -> str:
    """Liet ke cac o dia roi (the nho qua card reader, hoac USB) dang cam vao may.

    Dung tool nay truoc khi doi thu quet hoac do the, de biet dung ky hieu o
    dia can truyen cho ingest_scan_card / ingest_start (vi du 'E:').

    Khong nhan tham so.

    Returns:
        str: JSON voi cau truc:
        {
            "ok": true,
            "drives": [
                {"deviceId": "E:", "volumeName": "EOS_DIGITAL", "sizeGB": 64.0, "freeGB": 12.3}
            ]
        }
        Neu khong the nao dang cam: "drives" la mang rong (khong phai loi).
        Loi: {"ok": false, "error": "..."}
    """
    ps_cmd = (
        "Get-CimInstance -ClassName Win32_LogicalDisk "
        "| Where-Object { $_.DriveType -eq 2 -or $_.DriveType -eq 3 } "
        "| Select-Object DeviceID,VolumeName,Size,FreeSpace "
        "| ConvertTo-Json -Compress"
    )
    raw = await asyncio.create_subprocess_exec(
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            raw.communicate(), timeout=POWERSHELL_TIMEOUT_SECONDS
        )
    except FileNotFoundError:
        return json.dumps(
            {"ok": False, "error": "Khong tim thay powershell.exe. Server nay phai chay tren Windows."}
        )
    except asyncio.TimeoutError:
        return json.dumps({"ok": False, "error": "PowerShell qua thoi gian cho."})

    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return json.dumps({"ok": True, "drives": []})

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return json.dumps(
            {"ok": False, "error": f"Khong parse duoc danh sach o dia: {text[:300]}"}
        )

    if isinstance(data, dict):
        data = [data]

    drives = [
        {
            "deviceId": d.get("DeviceID"),
            "volumeName": d.get("VolumeName") or "(khong ten)",
            "sizeGB": round((d.get("Size") or 0) / (1024**3), 1),
            "freeGB": round((d.get("FreeSpace") or 0) / (1024**3), 1),
        }
        for d in data
    ]
    return json.dumps({"ok": True, "drives": drives}, ensure_ascii=False)


# ============================================================
# Tool 2: quet nhanh 1 the (chi doc) - so file, dung luong, uoc tinh thoi gian
# ============================================================


class ScanCardInput(BaseModel):
    """Input cho ingest_scan_card."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    card_drive: str = Field(
        ...,
        description="Ky hieu o dia the nho can quet, vi du 'E:' hoac 'E' (lay tu ingest_list_drives).",
        min_length=1,
        max_length=10,
    )
    dest: DestChoice = Field(
        default=DestChoice.BOTH,
        description="Dich upload du dinh dung, anh huong toi so phut uoc tinh (upload ca 2 noi mat gap doi thoi gian upload so voi 1 noi).",
    )


@mcp.tool(
    name="ingest_scan_card",
    annotations={
        "title": "Quet nhanh 1 the nho (chi doc)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def ingest_scan_card(params: ScanCardInput) -> str:
    """Quet 1 the nho (chi doc, KHONG copy/xoa gi) va tra ve so file, dung luong,
    va uoc tinh thoi gian de do the xong (copy + nen + upload).

    Dung tool nay truoc khi goi ingest_start, de bao cho nguoi dung biet truoc
    khoang bao lau va bao nhieu du lieu se duoc xu ly.

    Args:
        params (ScanCardInput): gom card_drive (vd 'E:') va dest du dinh.

    Returns:
        str: JSON voi cau truc:

        Thanh cong:
        {
            "ok": true,
            "fileCount": int,       # tong so file tren the
            "photoCount": int,
            "videoCount": int,
            "totalGB": float,       # tong dung luong
            "estimatedMinutes": float   # UOC TINH, dua tren toc do gia dinh
                                          # trong ingest.config.json, co the
                                          # chenh lech nhieu so voi thuc te
        }

        Loi (vi du o dia khong ton tai): {"ok": false, "error": "..."}

    Luu y quan trong: estimatedMinutes la con so UOC TINH dua tren gia dinh
    toc do doc the / mang trong ingest.config.json, KHONG PHAI do toc do thuc
    te luc goi. Neu nguoi dung hoi "chinh xac bao lau", noi ro day la uoc
    tinh, khong phai cam ket.
    """
    drive = _normalize_drive(params.card_drive)
    result = await _run_powershell_json(
        ["-File", SCAN_HELPER_PS1, "-CardDrive", drive, "-Dest", params.dest.value]
    )
    return json.dumps(result, ensure_ascii=False)


# ============================================================
# Tool 3: bat dau do the (chay nen, khong cho ket qua ngay)
# ============================================================


class StartIngestInput(BaseModel):
    """Input cho ingest_start."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    card_drive: str = Field(
        ...,
        description="Ky hieu o dia the nho can do, vi du 'E:' hoac 'E'.",
        min_length=1,
        max_length=10,
    )
    project_name: str = Field(
        ...,
        description="Ten du an, dung de dat ten folder va file nen (vi du 'Kid dance bsixteen'). Khong dung ky tu \\ / : * ? \" < > |.",
        min_length=1,
        max_length=150,
    )
    dest: DestChoice = Field(
        default=DestChoice.BOTH,
        description="Upload len dau: 'drive' (Google Drive), 'onedrive', hoac 'both' (ca hai, mac dinh).",
    )
    skip_upload: bool = Field(
        default=False,
        description="True neu chi muon copy + phan loai + nen, KHONG upload (vi du khi dang khong co mang).",
    )
    dest_folder: Optional[str] = Field(
        default=None,
        description=(
            "Thu muc CHA tren may de do the vao; folder du an duoc tao ben trong voi DUNG ten "
            "project_name (khong them ngay, khong long nam/thang). Chap nhan 'downloads', "
            "'desktop', 'documents' hoac duong dan day du nhu 'E:\\Backup'. Bo trong = thu muc "
            "chuan theo ingest.config.json (D:\\Quang\\<nam>\\thang <x>\\<ngay> - <ten>). "
            "KHONG anh huong toi upload: upload van theo 'dest', chi tat khi skip_upload=True."
        ),
        max_length=500,
    )


@mcp.tool(
    name="ingest_start",
    annotations={
        "title": "Bat dau do the nho",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def ingest_start(params: StartIngestInput) -> str:
    """Bat dau toan bo quy trinh do the: copy tu the -> tao folder du an theo
    nam/thang -> phan loai anh/video -> xac minh copy day du -> nen goc/
    (raw footage) -> upload Google Drive/OneDrive -> thong bao Windows
    toast + Telegram (neu da cau hinh).

    Day la tac vu CHAY NEN va co the mat vai phut den vai chuc phut tuy
    dung luong the va toc do mang (dung ingest_scan_card truoc de biet uoc
    tinh). Tool nay KHONG CHO doi ket qua cuoi cung - no tra ve ngay 1
    job_id, roi phai goi ingest_get_status(job_id) de theo doi/biet khi nao
    xong.

    An toan du lieu: quy trinh KHONG BAO GIO tu dong xoa/format the nho,
    va se dung lai (khong nen/upload) neu buoc xac minh copy phat hien
    thieu file.

    Args:
        params (StartIngestInput): gom card_drive, project_name, dest,
            skip_upload.

    Returns:
        str: JSON voi cau truc:

        Thanh cong (da bat dau, chua biet ket qua):
        {
            "ok": true,
            "job_id": "a1b2c3d4",
            "message": "Da bat dau do the. Dung ingest_get_status voi job_id nay de theo doi."
        }

        Loi ngay luc bat dau (vi du sai duong dan): {"ok": false, "error": "..."}

    Examples:
        - "Đổ thẻ E: cho dự án Kid dance bsixteen" -> card_drive="E:", project_name="Kid dance bsixteen"
        - "Chỉ copy và nén thẻ F:, đừng upload, mạng đang yếu" -> card_drive="F:", skip_upload=True
        - "Đổ thẻ H: vào Downloads, folder test đổ file" -> card_drive="H:",
          project_name="test đổ file", dest_folder="downloads" (upload giữ mặc định)
    """
    os.makedirs(JOBS_DIR, exist_ok=True)

    if not os.path.isfile(INGEST_PS1):
        return json.dumps(
            {"ok": False, "error": f"Khong tim thay ingest.ps1 tai {INGEST_PS1}"}
        )

    drive = _normalize_drive(params.card_drive)
    job_id = uuid.uuid4().hex[:8]
    log_path = os.path.join(JOBS_DIR, f"{job_id}.log")

    args = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        INGEST_PS1,
        "-CardDrive",
        drive,
        "-ProjectName",
        params.project_name,
        "-Dest",
        params.dest.value,
    ]
    if params.skip_upload:
        args.append("-SkipUpload")

    local_folder = None
    if params.dest_folder:
        dest_root, err = _resolve_dest_folder(params.dest_folder)
        if err:
            return json.dumps({"ok": False, "error": err}, ensure_ascii=False)
        args.extend(["-DestRoot", dest_root])
        local_folder = os.path.join(dest_root, params.project_name)

    log_file = open(log_path, "w", encoding="utf-8")
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
            cwd=REPO_ROOT,
        )
    except FileNotFoundError:
        log_file.close()
        return json.dumps(
            {"ok": False, "error": "Khong tim thay powershell.exe. Server nay phai chay tren Windows."}
        )

    JOBS[job_id] = {
        "process": proc,
        "log_path": log_path,
        "log_file": log_file,
        "started": time.time(),
        "project_name": params.project_name,
    }

    return json.dumps(
        {
            "ok": True,
            "job_id": job_id,
            "local_folder": local_folder or "(thu muc chuan theo ingest.config.json)",
            "message": "Da bat dau do the. Dung ingest_get_status voi job_id nay de theo doi.",
        },
        ensure_ascii=False,
    )


# ============================================================
# Tool 4: kiem tra tien trinh 1 job da bat dau bang ingest_start
# ============================================================


class GetIngestStatusInput(BaseModel):
    """Input cho ingest_get_status."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_id: str = Field(
        ...,
        description="job_id tra ve tu ingest_start.",
        min_length=1,
        max_length=64,
    )


@mcp.tool(
    name="ingest_get_status",
    annotations={
        "title": "Kiem tra tien trinh do the",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def ingest_get_status(params: GetIngestStatusInput) -> str:
    """Kiem tra 1 job do the da bat dau bang ingest_start: dang chay, da
    xong (thanh cong), hay bi loi - kem theo phan cuoi nhat ky de biet dang
    o buoc nao (copy / nen / upload) hoac loi cu the la gi.

    Goi lai tool nay cach nhau vai chuc giay neu job con dang "running" -
    khong can goi lien tuc, quy trinh khong tu bao khi xong (khong co
    webhook/callback), phai chu dong hoi lai.

    Args:
        params (GetIngestStatusInput): gom job_id tra ve tu ingest_start.

    Returns:
        str: JSON voi cau truc:
        {
            "ok": true,
            "status": "running" | "success" | "failed",
            "elapsed_seconds": int,
            "log_tail": ["...", "..."]   # 30 dong cuoi cua nhat ky
        }
        Neu job_id khong ton tai (sai, hoac server da khoi dong lai mat
        theo doi): {"ok": false, "error": "..."}
    """
    job = JOBS.get(params.job_id)
    if not job:
        return json.dumps(
            {
                "ok": False,
                "error": (
                    f"Khong tim thay job_id '{params.job_id}'. Co the sai job_id, "
                    "hoac MCP server da khoi dong lai va mat theo doi cac job cu "
                    "(quy trinh PowerShell ban dau van co the van chay binh thuong "
                    "tren may, chi la server nay khong con theo doi duoc no)."
                ),
            }
        )

    proc: asyncio.subprocess.Process = job["process"]
    returncode = proc.returncode
    if returncode is None:
        status = "running"
    elif returncode == 0:
        status = "success"
    else:
        status = "failed"

    log_tail: list[str] = []
    try:
        with open(job["log_path"], "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            log_tail = [line.rstrip("\n") for line in lines[-30:]]
    except OSError as e:
        log_tail = [f"(khong doc duoc log: {e})"]

    return json.dumps(
        {
            "ok": True,
            "status": status,
            "project_name": job.get("project_name"),
            "elapsed_seconds": round(time.time() - job["started"]),
            "log_tail": log_tail,
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    mcp.run()
