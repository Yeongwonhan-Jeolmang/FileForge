"""
integrity_tools.py — Snapshot generation, verification, and audit trail storage.
"""

from __future__ import annotations
import os
import sys
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from modules.file_info import compute_hashes, fmt_time

ProgressCb = Optional[Callable[[int, int, str], None]]  # (done, total, current_path)
CancelCb = Optional[Callable[[], bool]]
SNAPSHOT_VERSION = 2


def _app_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "FileForge"


def ensure_app_data_dir() -> Path:
    path = _app_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _entry(file_path: Path, rel: str, st) -> dict[str, Any]:
    checks = compute_hashes(str(file_path), ["sha256"])
    return {
        "relative_path": rel,
        "absolute_path": str(file_path.resolve()),
        "size": st.st_size,
        "mtime": st.st_mtime,
        "mtime_str": fmt_time(st.st_mtime),
        "sha256": checks.get("sha256", ""),
    }


def create_snapshot(
    target: str, progress_cb: ProgressCb = None, cancel_cb: CancelCb = None
) -> dict[str, Any]:
    p = Path(target)
    snapshot: dict[str, Any] = {
        "version": SNAPSHOT_VERSION,
        "base": str(p.resolve()),
        "type": "folder" if p.is_dir() else "file",
        "created": time.time(),
        "created_str": fmt_time(time.time()),
        "entries": [],
        "errors": [],
    }

    if p.is_dir():
        files = []
        for root, dirs, names in os.walk(p):
            dirs.sort()
            for name in sorted(names):
                files.append(Path(root) / name)
        total = len(files)
        for idx, file_path in enumerate(files, start=1):
            if cancel_cb and cancel_cb():
                snapshot["cancelled"] = True
                break
            try:
                st = file_path.stat()
                snapshot["entries"].append(
                    _entry(file_path, file_path.relative_to(p).as_posix(), st)
                )
            except (OSError, PermissionError) as e:
                snapshot["errors"].append({"path": str(file_path), "error": str(e)})
            if progress_cb:
                progress_cb(idx, total, str(file_path))
    else:
        st = p.stat()
        snapshot["entries"].append(_entry(p, p.name, st))
        if progress_cb:
            progress_cb(1, 1, str(p))

    return snapshot


def save_snapshot(snapshot: dict[str, Any], output_path: str) -> tuple[bool, str]:
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        return True, f"Snapshot written to {output_path}."
    except Exception as e:
        return False, str(e)


def load_snapshot(path: str) -> dict[str, Any] | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def verify_snapshot(
    snapshot: dict[str, Any],
    progress_cb: ProgressCb = None,
    cancel_cb: CancelCb = None,
    deep: bool = False,
) -> dict[str, Any]:
    """
    Compare the file system against a snapshot.

    By default a file whose size *and* mtime are unchanged is trusted without
    re-hashing; pass deep=True to re-hash everything (catches tampering that
    restored the original timestamp).
    """
    base = Path(snapshot.get("base", ""))
    result: dict[str, Any] = {
        "missing": [],
        "changed": [],
        "unchanged": [],
        "extra": [],
    }
    seen = set()
    entries = snapshot.get("entries", [])
    total = len(entries)

    for idx, entry in enumerate(entries, start=1):
        if cancel_cb and cancel_cb():
            result["cancelled"] = True
            break
        rel = entry.get("relative_path", "")
        target_path = (
            base / rel
            if snapshot.get("type") == "folder"
            else Path(entry.get("absolute_path", ""))
        )
        seen.add(os.path.normcase(str(target_path)))
        if progress_cb:
            progress_cb(idx, total, rel)
        if not target_path.exists():
            result["missing"].append(rel)
            continue
        try:
            stat = target_path.stat()
        except (OSError, PermissionError):
            result["changed"].append({"path": rel, "reason": "unreadable"})
            continue
        if stat.st_size != entry.get("size"):
            result["changed"].append(
                {"path": rel, "reason": f"size {entry.get('size')} → {stat.st_size}"}
            )
            continue
        mtime_changed = abs(stat.st_mtime - entry.get("mtime", 0)) > 1
        if not mtime_changed and not deep:
            result["unchanged"].append(rel)
            continue
        checks = compute_hashes(str(target_path), ["sha256"])
        if checks.get("sha256") != entry.get("sha256"):
            result["changed"].append(
                {"path": rel, "reason": "content changed (hash mismatch)"}
            )
        elif mtime_changed:
            result["changed"].append(
                {"path": rel, "reason": "timestamp only (content identical)"}
            )
        else:
            result["unchanged"].append(rel)

    if snapshot.get("type") == "folder" and base.is_dir():
        current = {}
        for root, dirs, files in os.walk(base):
            for name in files:
                full = str(Path(root) / name)
                current[os.path.normcase(full)] = full
        result["extra"] = sorted(
            os.path.relpath(orig, base)
            for norm, orig in current.items()
            if norm not in seen
        )
    return result
