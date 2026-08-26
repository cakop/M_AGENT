import json
import os
from datetime import datetime

# 会话文件存到 src/agent/sessions/ 下
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")


def _ensure_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def save_session(history: list, session_id: str | None = None) -> str:
    """把 history 存成 JSON，返回 session_id。"""
    _ensure_dir()
    if not session_id:
        import time
        session_id = str(int(time.time() * 1000))   # 毫秒时间戳，如 1755568800000
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return session_id


def load_session(session_id: str) -> list | None:
    """读回历史；文件不存在返回 None。"""
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_sessions() -> list[str]:
    """列出所有会话 id，最新的在前。"""
    _ensure_dir()
    files = os.listdir(SESSIONS_DIR)
    return sorted(
        (f[:-5] for f in files if f.endswith(".json")),
        reverse=True,
    )