"""
file_info.py — Read every property we can about a file.
Returns a rich FileInfo dataclass used across the app.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import platform
import stat
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from modules.magic_sniffer import extension_mismatch, sniff_file

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"

# ── Optional deps (graceful degradation) ──────────────────────────────────
try:
    from mutagen._file import File as MutagenFile

    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
# Prefer the maintained `pypdf`; fall back to the deprecated PyPDF2 if that's all we have
try:
    from pypdf import PdfReader

    HAS_PYPDF2 = True
except ImportError:
    try:
        from PyPDF2 import PdfReader

        HAS_PYPDF2 = True
    except ImportError:
        HAS_PYPDF2 = False

try:
    from docx import Document as DocxDocument

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import openpyxl

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    from pptx import Presentation

    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

try:
    from pymediainfo import MediaInfo

    HAS_MEDIainfo = True
except ImportError:
    HAS_MEDIainfo = False


# ── Data structures ────────────────────────────────────────────────────────


@dataclass
class PermissionInfo:
    owner_read: bool
    owner_write: bool
    owner_exec: bool
    group_read: bool
    group_write: bool
    group_exec: bool
    other_read: bool
    other_write: bool
    other_exec: bool
    octal: str
    symbolic: str


@dataclass
class ImageMetadata:
    width: int
    height: int
    mode: str
    format: str
    dpi: tuple | None
    has_exif: bool
    exif: dict = field(default_factory=dict)


@dataclass
class AudioMetadata:
    duration: float | None
    bitrate: int | None
    sample_rate: int | None
    channels: int | None
    tags: dict = field(default_factory=dict)


@dataclass
class DocumentMetadata:
    doc_type: str = ""
    title: str = ""
    author: str = ""
    producer: str = ""
    subject: str = ""
    pages: int | None = None
    software: str = ""
    topic: str = ""
    comment: str = ""
    snippet: str = ""


@dataclass
class VideoMetadata:
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    bitrate: int | None = None
    codec: str = ""
    format: str = ""


@dataclass
class FileInfo:
    # Basics
    path: str
    name: str
    stem: str
    suffix: str
    size: int
    size_human: str

    # Timestamps
    created: float
    modified: float
    accessed: float
    created_str: str
    modified_str: str
    accessed_str: str

    # Type
    mime_type: str
    kind: str  # "image", "audio", "video", "document", "archive", "text", "other"
    is_symlink: bool
    is_hidden: bool

    # Permissions
    permissions: PermissionInfo
    owner: str
    group: str

    # Hashes (computed lazily)
    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None
    sha512: str | None = None
    blake2: str | None = None

    # Rich metadata
    image_meta: ImageMetadata | None = None
    audio_meta: AudioMetadata | None = None
    document_meta: DocumentMetadata | None = None
    video_meta: VideoMetadata | None = None

    # Extended attributes and platform-specific extras
    xattrs: dict = field(default_factory=dict)
    windows_ads: dict = field(default_factory=dict)

    # Content sniffing (magic bytes) — what the file *really* is
    detected_type: str = ""
    detected_mime: str = ""
    extension_mismatch: bool = False


# ── Helpers ────────────────────────────────────────────────────────────────

_SIZE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]


def human_size(n: int) -> str:
    val = float(n)
    for unit in _SIZE_UNITS:
        if val < 1024:
            return f"{val:.2f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024
    return f"{val:.2f} PB"


def fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d  %H:%M:%S", time.localtime(ts))


def _parse_permissions(mode: int) -> PermissionInfo:
    s = stat.filemode(mode)
    return PermissionInfo(
        owner_read=bool(mode & stat.S_IRUSR),
        owner_write=bool(mode & stat.S_IWUSR),
        owner_exec=bool(mode & stat.S_IXUSR),
        group_read=bool(mode & stat.S_IRGRP),
        group_write=bool(mode & stat.S_IWGRP),
        group_exec=bool(mode & stat.S_IXGRP),
        other_read=bool(mode & stat.S_IROTH),
        other_write=bool(mode & stat.S_IWOTH),
        other_exec=bool(mode & stat.S_IXOTH),
        octal=oct(stat.S_IMODE(mode)),
        symbolic=s,
    )


def _owner_group(st) -> tuple[str, str]:
    if _IS_WINDOWS:
        return "N/A", "N/A"
    try:
        import grp
        import pwd

        owner = pwd.getpwuid(st.st_uid).pw_name
        group = grp.getgrgid(st.st_gid).gr_name
        return owner, group
    except Exception:
        return str(getattr(st, "st_uid", "?")), str(getattr(st, "st_gid", "?"))


DOCUMENT_SUFFIXES = frozenset(
    (
        ".doc",
        ".docx",
        ".odt",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".ods",
        ".odp",
        ".rtf",
        ".pdf",
        ".epub",
    )
)
ARCHIVE_SUFFIXES = frozenset(
    (
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".zst",
        ".tgz",
        ".tbz2",
        ".txz",
    )
)
EXECUTABLE_SUFFIXES = frozenset(
    (
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".msi",
        ".sys",
        ".elf",
        ".app",
        ".com",
        ".scr",
        ".wasm",
    )
)


def _classify(mime: str, suffix: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("text/"):
        return "text"
    if "pdf" in mime or suffix in DOCUMENT_SUFFIXES:
        return "document"
    if suffix in ARCHIVE_SUFFIXES:
        return "archive"
    if suffix in EXECUTABLE_SUFFIXES:
        return "executable"
    if mime in (
        "application/json",
        "application/xml",
        "application/javascript",
        "application/x-sh",
        "application/x-yaml",
        "application/toml",
    ):
        return "text"
    return "other"


def classify_path(path: str) -> str:
    """Cheap, extension-only classification (no disk I/O). Used by list views."""
    mime, _ = mimetypes.guess_type(path)
    return _classify(mime or "application/octet-stream", Path(path).suffix.lower())


def _image_meta(path: str) -> ImageMetadata | None:
    if not HAS_PIL:
        return None
    try:
        with Image.open(path) as img:
            exif_raw = {}
            try:
                raw = img.getexif()
            except Exception:
                raw = None
            if raw:
                from PIL.ExifTags import TAGS

                # Merge the main IFD with the Exif sub-IFD (camera settings live there)
                items = dict(raw)
                try:
                    items.update(raw.get_ifd(0x8769))
                except Exception:
                    pass
                for tag_id, val in items.items():
                    if tag_id in (0x8769, 0x8825):  # IFD pointers, not real values
                        continue
                    tag = TAGS.get(tag_id, tag_id)
                    try:
                        if isinstance(val, bytes):
                            val = val.decode("utf-8", errors="replace").strip("\x00 ")
                        exif_raw[str(tag)] = str(val)
                    except Exception:
                        pass
            has_exif = bool(exif_raw)
            return ImageMetadata(
                width=img.width,
                height=img.height,
                mode=img.mode,
                format=img.format or "?",
                dpi=img.info.get("dpi"),
                has_exif=has_exif,
                exif=exif_raw,
            )
    except Exception:
        return None


def _audio_meta(path: str) -> AudioMetadata | None:
    if not HAS_MUTAGEN:
        logger.debug("Mutagen not installed, skipping audio metadata")
        return None
    try:
        mf = MutagenFile(path, easy=True)
        if mf is None:
            return None
        info = getattr(mf, "info", None)
        tags = {}
        if mf.tags:
            for k, v in mf.tags.items():
                tags[k] = str(v[0]) if isinstance(v, list) else str(v)
        return AudioMetadata(
            duration=getattr(info, "length", None),
            bitrate=getattr(info, "bitrate", None),
            sample_rate=getattr(info, "sample_rate", None),
            channels=getattr(info, "channels", None),
            tags=tags,
        )
    except Exception as e:
        logger.warning(f"Failed to read audio metadata from {path}: {e}")
        return None


def _document_meta(path: str, suffix: str) -> DocumentMetadata | None:
    if suffix == ".pdf" and HAS_PYPDF2:
        try:
            reader = PdfReader(path)
            meta = reader.metadata or {}
            title = getattr(meta, "title", "") or ""
            author = getattr(meta, "author", "") or ""
            producer = getattr(meta, "producer", "") or ""
            subject = getattr(meta, "subject", "") or ""
            software = getattr(meta, "producer", "") or ""
            pages = len(reader.pages)
            snippet = ""
            if pages:
                try:
                    snippet = reader.pages[0].extract_text() or ""
                    snippet = snippet[:1200].replace("\n", " ")
                except Exception:
                    snippet = ""
            return DocumentMetadata(
                doc_type="PDF",
                title=title,
                author=author,
                producer=producer,
                subject=subject,
                pages=pages,
                software=software,
                comment=str(getattr(meta, "keywords", "") or ""),
                topic=subject,
                snippet=snippet,
            )
        except Exception:
            return None

    if suffix == ".docx" and HAS_DOCX:
        try:
            doc = DocxDocument(path)
            props = doc.core_properties
            snippet = " ".join(p.text for p in doc.paragraphs[:40] if p.text)[:1200]
            return DocumentMetadata(
                doc_type="DOCX",
                title=props.title or "",
                author=props.author or "",
                subject=props.subject or "",
                software=props.last_modified_by or "",
                comment=props.comments or "",
                topic=props.keywords or "",
                snippet=snippet,
            )
        except Exception:
            return None

    if suffix in (".xlsx", ".xls") and HAS_OPENPYXL:
        try:
            from openpyxl import load_workbook

            wb = load_workbook(path, read_only=True, data_only=True)
            try:
                props = wb.properties
                meta = DocumentMetadata(
                    doc_type="Spreadsheet",
                    title=props.title or Path(path).name,
                    author=props.creator or "",
                    subject=props.subject or "",
                    software=props.lastModifiedBy or "",
                    pages=len(wb.sheetnames),
                    snippet="Sheets: " + ", ".join(wb.sheetnames[:20]),
                )
            finally:
                wb.close()
            return meta
        except Exception:
            return None

    if suffix == ".pptx" and HAS_PPTX:
        try:
            prs = Presentation(path)
            props = prs.core_properties
            return DocumentMetadata(
                doc_type="Presentation",
                title=props.title or Path(path).name,
                author=props.author or "",
                subject=props.subject or "",
                software=props.last_modified_by or "",
                pages=len(prs.slides),
                snippet="",
            )
        except Exception:
            return None

    return None


def _video_meta(path: str) -> VideoMetadata | None:
    if not HAS_MEDIainfo:
        return None
    try:
        info = MediaInfo.parse(path)
        for track in info.tracks:
            if track.track_type == "Video":
                duration_ms = getattr(track, "duration", None)
                duration = duration_ms / 1000 if duration_ms else None
                return VideoMetadata(
                    duration=duration,
                    width=getattr(track, "width", None),
                    height=getattr(track, "height", None),
                    bitrate=getattr(track, "bit_rate", None)
                    or getattr(track, "bitrate", None),
                    codec=getattr(track, "codec", "") or getattr(track, "format", ""),
                    format=getattr(track, "format", ""),
                )
    except Exception:
        pass
    return None


def _windows_ads(path: str) -> dict:
    """Get NTFS Alternate Data Streams using subprocess (only for large files)."""
    if not _IS_WINDOWS:
        return {}

    try:
        # Only check ADS for files larger than 1MB to avoid overhead
        file_size = os.path.getsize(path)
        if file_size < 1_000_000:  # 1MB threshold
            return {}

        # Use timeout to prevent hanging
        result = subprocess.run(
            ["cmd.exe", "/c", "dir", "/r", str(Path(path))],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        ads = {}
        for line in result.stdout.splitlines():
            if ":$DATA" in line and "Directory of" not in line and line.strip():
                parts = line.split()
                if parts and parts[0].isdigit():
                    size = int(parts[0])
                    stream = parts[-1]
                    ads[stream] = size
        return ads
    except (subprocess.SubprocessError, OSError, ValueError):
        return {}


def _xattrs(path: str) -> dict:
    if not hasattr(os, "getxattr"):
        return {}
    try:
        attrs = {}
        for name in os.listxattr(path):
            try:
                attrs[name] = os.getxattr(path, name).decode(errors="replace")
            except Exception:
                attrs[name] = "<unreadable>"
        return attrs
    except Exception:
        return {}


# ── Public API ─────────────────────────────────────────────────────────────


def read_file_info(path: str) -> FileInfo:
    """Return a fully populated FileInfo for the given path."""
    p = Path(path)
    st = p.lstat()
    mode = st.st_mode

    mime, _ = mimetypes.guess_type(str(p))
    mime = mime or "application/octet-stream"
    suffix = p.suffix.lower()
    kind = _classify(mime, suffix)

    # Look at the actual bytes: catches renamed files and unknown extensions
    sniffed = sniff_file(path) if p.is_file() else None
    if sniffed and (kind == "other" or mime == "application/octet-stream"):
        kind = sniffed.kind
        if mime == "application/octet-stream":
            mime = sniffed.mime

    is_sym = stat.S_ISLNK(mode)
    is_hidden = p.name.startswith(".")
    if _IS_WINDOWS and hasattr(st, "st_file_attributes"):
        is_hidden = is_hidden or bool(
            st.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN
        )

    created_ts = getattr(st, "st_birthtime", st.st_ctime)
    owner, group = _owner_group(st)

    info = FileInfo(
        path=str(p),
        name=p.name,
        stem=p.stem,
        suffix=p.suffix,
        size=st.st_size,
        size_human=human_size(st.st_size),
        created=created_ts,
        modified=st.st_mtime,
        accessed=st.st_atime,
        created_str=fmt_time(created_ts),
        modified_str=fmt_time(st.st_mtime),
        accessed_str=fmt_time(st.st_atime),
        mime_type=mime,
        kind=kind,
        is_symlink=is_sym,
        is_hidden=is_hidden,
        permissions=_parse_permissions(mode),
        owner=owner,
        group=group,
        image_meta=_image_meta(path) if kind == "image" else None,
        audio_meta=_audio_meta(path) if kind == "audio" else None,
        document_meta=_document_meta(path, suffix) if kind == "document" else None,
        video_meta=_video_meta(path) if kind == "video" else None,
        xattrs=_xattrs(path),
        windows_ads=_windows_ads(path),
        detected_type=sniffed.description if sniffed else "",
        detected_mime=sniffed.mime if sniffed else "",
        extension_mismatch=extension_mismatch(sniffed, suffix),
    )
    return info


class HashCancelled(Exception):
    """Raised by compute_hashes when the caller's cancel check returns True."""


HASH_CHUNK = 1 << 20  # 1 MiB reads — far fewer syscalls / Python iterations than 64 KiB


def _new_hasher(algo: str):
    if algo == "blake2":
        return hashlib.blake2b()
    return hashlib.new(algo)


def compute_hashes(
    path: str,
    algorithms: list[str] | None = None,
    progress_cb=None,
    cancel_cb: Callable[[], bool] | None = None,
) -> dict[str, str]:
    """
    Compute file hashes. algorithms: list of 'md5','sha1','sha256','sha512','blake2'.

    - Reads in 1 MiB chunks into a reused buffer (no per-chunk allocation).
    - When several algorithms are requested they are updated in parallel threads;
      hashlib releases the GIL, so this scales with CPU cores.
    - progress_cb(done, total) is throttled to ~1% steps so a GUI thread isn't
      flooded with thousands of cross-thread signals.
    - cancel_cb() is polled each chunk; returning True raises HashCancelled.
    """
    if algorithms is None:
        algorithms = ["md5", "sha1", "sha256"]

    hashers = {a: _new_hasher(a) for a in algorithms}
    total = os.path.getsize(path)
    done = 0
    step = max(total // 100, HASH_CHUNK)
    next_report = step

    buf = bytearray(HASH_CHUNK)
    view = memoryview(buf)
    pool = (
        ThreadPoolExecutor(max_workers=len(hashers))
        if len(hashers) > 1 and total > 4 * HASH_CHUNK
        else None
    )

    try:
        with open(path, "rb", buffering=0) as f:
            while True:
                if cancel_cb and cancel_cb():
                    raise HashCancelled()
                n = f.readinto(buf)
                if not n:
                    break
                chunk = view[:n]
                if pool:
                    # list() forces completion and re-raises any worker exception
                    list(pool.map(lambda h: h.update(chunk), hashers.values()))
                else:
                    for h in hashers.values():
                        h.update(chunk)
                done += n
                if progress_cb and done >= next_report:
                    progress_cb(done, total)
                    next_report = done + step
    finally:
        view.release()
        if pool:
            pool.shutdown(wait=True)

    if progress_cb:
        progress_cb(total, total)
    return {a: hashers[a].hexdigest() for a in algorithms}
