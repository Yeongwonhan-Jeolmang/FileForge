"""
folder_tools.py — Utilities for folder and duplicate analysis, summary reports, and export helpers.
"""

from __future__ import annotations

import csv
import hashlib
import heapq
import json
import os
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from modules.file_info import classify_path, fmt_time, human_size
from modules.metadata_cache import cached_hash

ProgressCb = Optional[Callable[[int, str], None]]  # (files_processed, current_path)
CancelCb = Optional[Callable[[], bool]]

_PARTIAL_BYTES = 64 * 1024
_HASH_CHUNK = 1 << 20


def _classify_path(path: str) -> str:
    return classify_path(path)


def iter_files(
    folder: str, include_hidden: bool = True, cancel_cb: CancelCb = None
) -> Iterator[tuple[str, os.stat_result]]:
    """
    Recursively yield (path, stat) for every regular file under `folder`.

    Uses os.scandir directly: DirEntry caches file-type info (and on Windows the
    full stat), so this is noticeably faster than os.walk + os.stat per file.
    Symlinks are not followed, which also prevents infinite loops.
    """
    stack = [folder]
    while stack:
        if cancel_cb and cancel_cb():
            return
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if not include_hidden and entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            yield entry.path, entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
        except (OSError, PermissionError):
            continue


@cached_hash
def _sha256(path: str, hash_type: str = "sha256") -> str:
    return _sha256_safe(path)


def scan_folder(
    folder: str,
    progress_cb: ProgressCb = None,
    cancel_cb: CancelCb = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Scan a folder and return summary information for reporting."""
    started = time.perf_counter()
    total_files = 0
    total_size = 0
    type_counts: dict[str, int] = defaultdict(int)
    type_sizes: dict[str, int] = defaultdict(int)
    extensions: dict[str, int] = defaultdict(int)
    largest: list[tuple[int, str]] = []  # min-heap of (size, path)
    newest: list[tuple[float, str]] = []  # min-heap of (mtime, path)
    oldest_mtime = None
    empty_files = 0

    for path, st in iter_files(folder, cancel_cb=cancel_cb):
        total_files += 1
        size = st.st_size
        total_size += size
        if size == 0:
            empty_files += 1
        kind = _classify_path(path)
        type_counts[kind] += 1
        type_sizes[kind] += size
        extensions[os.path.splitext(path)[1].lower() or "(none)"] += 1

        # O(log n) bounded heaps instead of re-sorting a list on every file
        if len(largest) < top_n:
            heapq.heappush(largest, (size, path))
        elif size > largest[0][0]:
            heapq.heapreplace(largest, (size, path))
        if len(newest) < top_n:
            heapq.heappush(newest, (st.st_mtime, path))
        elif st.st_mtime > newest[0][0]:
            heapq.heapreplace(newest, (st.st_mtime, path))
        if oldest_mtime is None or st.st_mtime < oldest_mtime:
            oldest_mtime = st.st_mtime

        if progress_cb and total_files % 500 == 0:
            progress_cb(total_files, path)

    return {
        "root": str(Path(folder).resolve()),
        "total_files": total_files,
        "total_size": total_size,
        "total_size_human": human_size(total_size),
        "empty_files": empty_files,
        "type_counts": dict(type_counts),
        "type_sizes": {k: v for k, v in type_sizes.items()},
        "extensions": dict(sorted(extensions.items(), key=lambda kv: -kv[1])),
        "top_largest": [
            {"path": p, "size": s, "size_human": human_size(s)}
            for s, p in sorted(largest, reverse=True)
        ],
        "recent_files": [
            {"path": p, "modified": m, "modified_str": fmt_time(m)}
            for m, p in sorted(newest, reverse=True)
        ],
        "oldest_modified_str": fmt_time(oldest_mtime) if oldest_mtime else "",
        "scan_seconds": round(time.perf_counter() - started, 3),
        "cancelled": bool(cancel_cb and cancel_cb()),
    }


def _partial_hash(path: str) -> str:
    """Hash of the first 64 KiB — a cheap pre-filter before full hashing."""
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        h.update(f.read(_PARTIAL_BYTES))
    return h.hexdigest()


def _group_by(paths: list[str], func, executor) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for path, digest in zip(paths, executor.map(_safe_call(func), paths)):
        if digest is not None:
            groups[digest].append(path)
    return groups


def _safe_call(func):
    def inner(path):
        try:
            return func(path)
        except (OSError, PermissionError):
            return None

    return inner


def find_duplicates(
    folder: str,
    min_size: int = 1,
    max_workers: int = 4,
    progress_cb: ProgressCb = None,
    cancel_cb: CancelCb = None,
) -> list[dict[str, Any]]:
    """
    Find duplicate files in a folder.

    Three-stage pipeline, each stage only looking at survivors of the previous one:
      1. group by exact size (free — from the directory scan)
      2. group by a hash of the first 64 KiB (one small read per candidate)
      3. full SHA-256 of what's left
    Hard links to the same inode are reported once, not as duplicates.
    """
    size_map: dict[int, list[str]] = defaultdict(list)
    seen_inodes: set[tuple[int, int]] = set()
    for path, st in iter_files(folder, cancel_cb=cancel_cb):
        if st.st_size < min_size:
            continue
        if st.st_ino:
            key = (st.st_dev, st.st_ino)
            if key in seen_inodes:
                continue
            seen_inodes.add(key)
        size_map[st.st_size].append(path)

    candidates = {size: paths for size, paths in size_map.items() if len(paths) > 1}
    duplicates: list[dict[str, Any]] = []
    processed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for size, paths in candidates.items():
            if cancel_cb and cancel_cb():
                break
            processed += len(paths)
            if progress_cb:
                progress_cb(processed, paths[0])

            # Small files: the partial hash already covers the whole content
            if size <= _PARTIAL_BYTES:
                groups = _group_by(paths, _partial_hash, executor).values()
                stage2 = [g for g in groups if len(g) > 1]
                final_groups = []
                for g in stage2:
                    full = _group_by(g, _sha256, executor)
                    final_groups.extend(full.items())
            else:
                partial = _group_by(paths, _partial_hash, executor)
                final_groups = []
                for group in partial.values():
                    if len(group) < 2:
                        continue
                    final_groups.extend(_group_by(group, _sha256, executor).items())

            for digest, group in final_groups:
                if len(group) > 1:
                    duplicates.append(
                        {
                            "hash": digest,
                            "size": size,
                            "size_human": human_size(size),
                            "wasted": size * (len(group) - 1),
                            "wasted_human": human_size(size * (len(group) - 1)),
                            "files": sorted(group),
                        }
                    )

    duplicates.sort(key=lambda item: (-item["wasted"], len(item["files"])))
    return duplicates


def _sha256_safe(path: str) -> str:
    """SHA256 with a reused 1 MiB read buffer."""
    h = hashlib.sha256()
    buf = bytearray(_HASH_CHUNK)
    view = memoryview(buf)
    with open(path, "rb", buffering=0) as f:
        while n := f.readinto(buf):
            h.update(view[:n])
    return h.hexdigest()


def export_report_json(report: dict[str, Any], output_path: str) -> tuple[bool, str]:
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return True, f"Exported report to {output_path}."
    except Exception as e:
        return False, str(e)


def export_report_csv(report: dict[str, Any], output_path: str) -> tuple[bool, str]:
    try:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Summary", "Value"])
            writer.writerow(["Root", report.get("root", "")])
            writer.writerow(["Total Files", report.get("total_files", 0)])
            writer.writerow(["Total Size", report.get("total_size", 0)])
            writer.writerow(["Total Size (human)", report.get("total_size_human", "")])
            writer.writerow(["Type Counts", json.dumps(report.get("type_counts", {}))])
            writer.writerow(["Extensions", json.dumps(report.get("extensions", {}))])
            writer.writerow([])
            writer.writerow(["Top Largest Files"])
            writer.writerow(["Size", "Size Human", "Path"])
            for item in report.get("top_largest", []):
                writer.writerow([item["size"], item["size_human"], item["path"]])
            if report.get("duplicates"):
                writer.writerow([])
                writer.writerow(["Duplicate Groups"])
                writer.writerow(["Group", "Size", "Wasted", "SHA-256", "Path"])
                for idx, group in enumerate(report["duplicates"], start=1):
                    for path in group["files"]:
                        writer.writerow(
                            [idx, group["size"], group["wasted"], group["hash"], path]
                        )
            return True, f"Exported CSV report to {output_path}."
    except Exception as e:
        return False, str(e)
