"""Persistent download task history."""

import json
import os
import tempfile
import time
from typing import Any, Dict, List

HISTORY_FILE = os.environ.get("TMD_TASK_HISTORY_FILE", "task_history.json")
FLUSH_INTERVAL = 2.0

_history: Dict[str, Dict[str, Any]] = {}
_loaded = False
_last_flush = 0.0


def configure_history_file(path: str):
    """Set the history file path, mainly for tests."""
    global HISTORY_FILE
    global _loaded
    global _last_flush
    HISTORY_FILE = path
    _loaded = False
    _last_flush = 0.0
    _history.clear()


def _task_key(chat_id, message_id) -> str:
    return f"{chat_id}:{message_id}"


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    if not os.path.isfile(HISTORY_FILE):
        return
    try:
        with open(HISTORY_FILE, encoding="utf-8") as history_file:
            data = json.load(history_file)
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(data, dict):
        _history.update(data)


def _flush(force: bool = False):
    global _last_flush
    now = time.time()
    if not force and now - _last_flush < FLUSH_INTERVAL:
        return
    _last_flush = now
    directory = os.path.dirname(os.path.abspath(HISTORY_FILE))
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".task_history.", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            json.dump(_history, temp_file, ensure_ascii=False, indent=2)
        os.replace(temp_path, HISTORY_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def record_task(
    chat_id,
    message_id,
    down_byte: int,
    total_size: int,
    file_name: str,
    download_speed: float,
):
    """Record a task snapshot and persist it periodically."""
    _load()
    total_size = total_size or 0
    down_byte = down_byte or 0
    status = "done" if total_size > 0 and down_byte >= total_size else "downloading"
    _history[_task_key(chat_id, message_id)] = {
        "chat": f"{chat_id}",
        "id": f"{message_id}",
        "down_byte": down_byte,
        "total_size": total_size,
        "file_name": file_name or "",
        "download_speed": download_speed or 0,
        "status": status,
        "updated_at": int(time.time()),
    }
    _flush(force=status == "done")


def list_history(status: str = "") -> List[Dict[str, Any]]:
    """Return persisted task snapshots, newest first."""
    _load()
    items = list(_history.values())
    if status:
        items = [item for item in items if item.get("status") == status]
    return sorted(items, key=lambda item: item.get("updated_at", 0), reverse=True)


def clear_history():
    """Clear in-memory and on-disk history."""
    _history.clear()
    if os.path.exists(HISTORY_FILE):
        os.unlink(HISTORY_FILE)
