"""Append-only audit trail: output/audit_trail.json.

The file is one JSON array. Each call to append() reads it, adds one entry,
and writes it back atomically. It is never wiped between runs. If the file is
ever unreadable, it is set aside (renamed, not deleted) and a new one starts.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from config import AUDIT_PATH, AUDIT_PREVIEW_CHARS

_lock = threading.Lock()


def clip(value: Any, limit: int = AUDIT_PREVIEW_CHARS) -> Any:
    """Keep audit entries readable: long text is cut, structures pass through."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [{len(value) - limit} more chars]"
    return value


def _load() -> list[dict]:
    if not AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]")
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    AUDIT_PATH.rename(AUDIT_PATH.with_name(f"audit_trail.unreadable-{stamp}.json"))
    return []


def _write(entries: list[dict]) -> None:
    tmp = AUDIT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")
    for attempt in range(5):  # OneDrive can hold the file for a moment
        try:
            os.replace(tmp, AUDIT_PATH)
            return
        except PermissionError:
            time.sleep(0.2 * (attempt + 1))
    os.replace(tmp, AUDIT_PATH)


def read(since_seq: int = 0) -> list[dict]:
    """Entries with seq > since_seq, oldest first (read-only; never changes the file)."""
    with _lock:
        if not AUDIT_PATH.exists():
            return []
        try:
            entries = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
    return [e for e in entries if e.get("seq", 0) > since_seq]


def append(event: str, **fields: Any) -> dict:
    """Add one entry to the audit trail and return it."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event, **fields}
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        entries = _load()
        entry["seq"] = len(entries) + 1
        entries.append(entry)
        _write(entries)
    return entry
