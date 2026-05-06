"""
archive_tools.py — Utilities to inspect and preview archive contents.
"""

from __future__ import annotations
import zipfile
import tarfile
from pathlib import Path

try:
    import py7zr
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False


def list_archive_contents(path: str) -> list[dict[str, str]]:
    path_obj = Path(path)
    suffix = path_obj.suffix.lower()
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, 'r') as archive:
            return [
                {
                    'name': info.filename,
                    'size': str(info.file_size),
                    'compressed': str(info.compress_size),
                    'type': 'zip',
                }
                for info in archive.infolist()
            ]

    if tarfile.is_tarfile(path):
        with tarfile.open(path, 'r:*') as archive:
            return [
                {
                    'name': member.name,
                    'size': str(member.size),
                    'compressed': str(member.size),
                    'type': 'tar',
                }
                for member in archive.getmembers()
            ]

    if HAS_PY7ZR and suffix == '.7z':
        with py7zr.SevenZipFile(path, mode='r') as archive:
            return [
                {
                    'name': name,
                    'size': str(info.uncompressed),
                    'compressed': str(info.compressed),
                    'type': '7z',
                }
                for name, info in archive.list().items()
            ]

    return []