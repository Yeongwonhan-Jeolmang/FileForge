"""
folder_tools.py — Utilities for folder and duplicate analysis, summary reports, and export helpers.
"""

from __future__ import annotations
import os
import csv
import json
import hashlib
import mimetypes
from collections import defaultdict
from pathlib import Path
from typing import Any

from modules.file_info import human_size

_ARCHIVE_EXTENSIONS = {'.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.tgz', '.tar.gz', '.tar.bz2'}


def _classify_path(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    suffix = Path(path).suffix.lower()
    if mime:
        if mime.startswith('image/'):
            return 'image'
        if mime.startswith('audio/'):
            return 'audio'
        if mime.startswith('video/'):
            return 'video'
        if mime.startswith('text/'):
            return 'text'
    if suffix in {'.pdf', '.doc', '.docx', '.odt', '.xls', '.xlsx', '.ppt', '.pptx', '.rtf'}:
        return 'document'
    if suffix in _ARCHIVE_EXTENSIONS:
        return 'archive'
    return 'other'


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def scan_folder(folder: str) -> dict[str, Any]:
    """Scan a folder and return summary information for reporting."""
    summary: dict[str, Any] = {
        'root': str(Path(folder).resolve()),
        'total_files': 0,
        'total_size': 0,
        'type_counts': defaultdict(int),
        'top_largest': [],
        'recent_files': [],
        'extensions': defaultdict(int),
    }
    recent_files: list[tuple[float, str]] = []

    for dirpath, dirnames, filenames in os.walk(folder):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            try:
                stat = os.stat(path)
            except (OSError, PermissionError):
                continue
            summary['total_files'] += 1
            summary['total_size'] += stat.st_size
            kind = _classify_path(path)
            summary['type_counts'][kind] += 1
            summary['extensions'][Path(filename).suffix.lower() or ''] += 1

            if len(summary['top_largest']) < 5:
                summary['top_largest'].append((stat.st_size, path))
                summary['top_largest'].sort(reverse=True)
            elif stat.st_size > summary['top_largest'][-1][0]:
                summary['top_largest'][-1] = (stat.st_size, path)
                summary['top_largest'].sort(reverse=True)

            recent_files.append((stat.st_mtime, path))

    summary['top_largest'] = [
        {'path': p, 'size': s, 'size_human': human_size(s)}
        for s, p in summary['top_largest']
    ]
    recent_files.sort(reverse=True)
    summary['recent_files'] = [
        {'path': p, 'modified': m, 'modified_str': Path(p).name}
        for m, p in recent_files[:5]
    ]
    summary['type_counts'] = dict(summary['type_counts'])
    summary['extensions'] = dict(summary['extensions'])
    return summary


def find_duplicates(folder: str, min_size: int = 1) -> list[dict[str, Any]]:
    """Find duplicate files in a folder by size and SHA-256 hash."""
    size_map: dict[int, list[str]] = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(folder):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            try:
                size = os.path.getsize(path)
            except (OSError, PermissionError):
                continue
            if size < min_size:
                continue
            size_map[size].append(path)

    duplicates: list[dict[str, Any]] = []
    for size, paths in size_map.items():
        if len(paths) < 2:
            continue
        hash_map: dict[str, list[str]] = defaultdict(list)
        for path in paths:
            try:
                digest = _sha256(path)
                hash_map[digest].append(path)
            except (OSError, PermissionError):
                continue
        for digest, group in hash_map.items():
            if len(group) > 1:
                duplicates.append({
                    'hash': digest,
                    'size': size,
                    'size_human': human_size(size),
                    'files': sorted(group),
                })
    duplicates.sort(key=lambda item: (-item['size'], len(item['files'])))
    return duplicates


def export_report_json(report: dict[str, Any], output_path: str) -> tuple[bool, str]:
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        return True, f"Exported report to {output_path}."
    except Exception as e:
        return False, str(e)


def export_report_csv(report: dict[str, Any], output_path: str) -> tuple[bool, str]:
    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Summary', 'Value'])
            writer.writerow(['Root', report.get('root', '')])
            writer.writerow(['Total Files', report.get('total_files', 0)])
            writer.writerow(['Total Size', report.get('total_size', 0)])
            writer.writerow(['Type Counts', json.dumps(report.get('type_counts', {}))])
            writer.writerow(['Extensions', json.dumps(report.get('extensions', {}))])
            writer.writerow([])
            writer.writerow(['Top Largest Files'])
            writer.writerow(['Size', 'Size Human', 'Path'])
            for item in report.get('top_largest', []):
                writer.writerow([item['size'], item['size_human'], item['path']])
            return True, f"Exported CSV report to {output_path}."
    except Exception as e:
        return False, str(e)
