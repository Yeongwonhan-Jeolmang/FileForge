"""
archive_tools.py — Utilities to inspect and preview archive contents.
"""

from __future__ import annotations
import zipfile
import tarfile
from pathlib import Path
from typing import Optional

from modules.file_info import human_size

try:
    import py7zr

    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False


def _row(
    name: str,
    size: int,
    compressed: Optional[int],
    kind: str,
    is_dir: bool = False,
    encrypted: bool = False,
) -> dict[str, str]:
    return {
        "name": name,
        "size": str(size),
        "compressed": str(compressed) if compressed is not None else "",
        "size_human": "" if is_dir else human_size(size),
        "compressed_human": ""
        if (is_dir or compressed is None)
        else human_size(compressed),
        "type": kind,
        "is_dir": "yes" if is_dir else "",
        "encrypted": "yes" if encrypted else "",
    }


def list_archive_contents(
    path: str, limit: Optional[int] = None
) -> list[dict[str, str]]:
    """
    List entries in a ZIP / TAR(.gz/.bz2/.xz) / 7z archive.

    `limit` caps how many entries are returned. For TAR archives this matters a
    lot: members are streamed, so a preview of a multi-GB .tar.gz stops reading
    after `limit` headers instead of decompressing the whole thing.
    """
    path_obj = Path(path)
    suffix = path_obj.suffix.lower()
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as archive:
                infos = archive.infolist()
                if limit is not None:
                    infos = infos[:limit]
                return [
                    _row(
                        info.filename,
                        info.file_size,
                        info.compress_size,
                        "zip",
                        info.is_dir(),
                        bool(info.flag_bits & 0x1),
                    )
                    for info in infos
                ]

        if tarfile.is_tarfile(path):
            rows = []
            with tarfile.open(path, "r:*") as archive:
                for member in archive:
                    rows.append(
                        _row(member.name, member.size, None, "tar", member.isdir())
                    )
                    if limit is not None and len(rows) >= limit:
                        break
            return rows

        if HAS_PY7ZR and suffix == ".7z":
            with py7zr.SevenZipFile(path, mode="r") as archive:
                rows = []
                for info in archive.list():
                    rows.append(
                        _row(
                            info.filename,
                            info.uncompressed or 0,
                            info.compressed,
                            "7z",
                            info.is_directory,
                        )
                    )
                    if limit is not None and len(rows) >= limit:
                        break
                return rows
    except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError, ValueError):
        return []
    except Exception:
        # py7zr raises its own exception hierarchy for corrupt / encrypted archives
        return []

    return []


def archive_entry_count(path: str) -> Optional[int]:
    """Total number of entries when it is cheap to know (ZIP central directory), else None."""
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as archive:
                return len(archive.infolist())
    except (OSError, zipfile.BadZipFile):
        pass
    return None
