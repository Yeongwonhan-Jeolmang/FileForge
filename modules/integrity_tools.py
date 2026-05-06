"""
integrity_tools.py — Snapshot generation, verification, and audit trail storage.
"""

from __future__ import annotations
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Any

from modules.file_info import compute_hashes

def _app_data_dir() -> Path:
    if sys.platform.startswith('win'):
        base = Path(os.environ.get('APPDATA', Path.home() / 'Appdata' / 'Roaming'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path.home() / '.config'
    return base / 'FileForge'

def ensure_app_data_dir() -> Path:
    path = _app_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path

def create_snapshot(target: str) -> dict[str, Any]:
    p = Path(target)
    snapshot: dict[str, Any] = {
        'base': str(p.resolve()),
        'type': 'folder' if p.is_dir() else 'file',
        'created': time.time(),
        'entries': [],
    }

    if p.is_dir():
        for root, dirs, files in os.walk(p):
            for name in files:
                file_path = Path(root) / name
                try:
                    stat = file_path.stat()
                except (OSError, PermissionError):
                    continue
                checks = compute_hashes(str(file_path), ['sha256'])
                snapshot['entries'].append({
                    'relative_path': str(file_path.relative_to(p)),
                    'absolute_path': str(file_path.resolve()),
                    'size': stat.st_size,
                    'mtime': stat.st_mtime,
                    'sha256': checks.get('sha256', ''),
                })
    else:
        stat = p.stat()
        checks = compute_hashes(str(p), ['sha256'])
        snapshot['entries'].append({
            'relative_path': p.name,
            'absolute_path': str(p.resolve()),
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'sha256': checks.get('sha256', ''),
        })

    return snapshot

def save_snapshot(snapshot: dict[str, Any], output_path: str) -> tuple[bool, str]:
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
        return True, f"Snapshot written to {output_path}."
    except Exception as e:
        return False, str(e)
    
def load_snapshot(path: str) -> dict[str, Any] | None:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def verify_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    base = Path(snapshot.get('base', ''))
    result: dict[str, Any] = {
        'missing': [],
        'changed': [],
        'unchanged': [],
        'extra': [],
    }
    seen = set()

    for entry in snapshot.get('entries', []):
        rel = entry.get('relative_path', '')
        target_path = base / rel if snapshot.get('type') == 'folder' else Path(entry.get('absolute_path', ''))
        seen.add(str(target_path))
        if not target_path.exists():
            result['missing'].append(rel)
            continue
        try:
            stat = target_path.stat()
        except (OSError, PermissionError):
            result['changed'].append({'path': rel, 'reason': 'unreadable'})
            continue
        if stat.st_size != entry.get('size') or abs(stat.st_mtime - entry.get('mtime', 0)) > 1:
            result['changed'].append({'path': rel, 'reason': 'size or timestamp'} )
            continue
        checks = compute_hashes(str(target_path), ['sha256'])
        if checks.get('sha256') != entry.get('sha256'):
            result['changed'].append({'path': rel, 'reason': 'hash mismatch'})
        else:
            result['unchanged'].append(rel)

    if snapshot.get('type') == 'folder' and base.is_dir():
        current = set()
        for root, dirs, files in os.walk(base):
            for name in files:
                current.add(str(Path(root) / name))
        result['extra'] = sorted(current - seen)
    return result
