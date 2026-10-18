"""
Goi AI local (Ollama tren chinh may nay, 127.0.0.1:11434). Dung chung cho:
- tool ask_local_llm trong server.py (Claude hoi Gemma/Qwen mot cau, khong dung cong cu)
- local-llm/javis_agent.py (Gemma/Qwen tu goi cong cu MCP trong vong lap)

Chi dung thu vien chuan (Python 3.12 cua may khong co requests). Du lieu khong roi khoi may.
"""

import json
import urllib.request

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma4:12b"
MODELS = ("gemma4:12b", "qwen3.8:27b")
SLOW_TIMEOUTS = {"qwen3.8:27b": 900}  # 27B chay ~6 token/s (mot phan tren CPU): 300 giay mac dinh khong du cho cau tra loi dai


def chat(
    messages: list,
    model: str = DEFAULT_MODEL,
    tools: list = None,
    think: bool = False,
    temperature: float = 0.3,
    num_ctx: int = 16384,
    timeout: int = 300,
    num_predict: int = 4096,
) -> dict:
    """Goi /api/chat (khong stream), tra ve nguyen JSON cua Ollama.

    Nem URLError neu Ollama chua bat, TimeoutError neu qua `timeout` giay.
    num_predict: tran so token sinh ra. Neu thieu, model co the ket vong lap sinh chu vo hinh den khi day ngu canh (da gap: 127 giay, tra loi rong).
    keep_alive 5m: model tu nha VRAM sau 5 phut khong dung, de khong chiem GPU cua ComfyUI/Resolve.
    """
    timeout = max(timeout, SLOW_TIMEOUTS.get(model, 0))
    payload = {
        "model": model,
        "stream": False,
        "think": think,
        "messages": messages,
        "options": {"num_ctx": num_ctx, "temperature": temperature, "num_predict": num_predict},
        "keep_alive": "5m",
    }
    if tools:
        payload["tools"] = tools
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        r = json.load(resp)
    msg = r.get("message") or {}
    content = msg.get("content") or ""
    if "<channel|>" in content:  # Gemma doi khi ro nhan kenh 'thought' vao noi dung: chi giu phan sau nhan
        msg["content"] = content.split("<channel|>")[-1].strip()
    return r
