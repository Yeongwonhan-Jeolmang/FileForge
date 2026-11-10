"""
magic_sniffer.py — Detect a file's real type from its leading "magic" bytes.

Extensions can lie (a renamed .exe, a .dat that is really a PNG…). This module
inspects the first bytes of a file and reports what the content actually is,
so FileForge can flag extension mismatches.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SniffResult:
    description: str  # Human-readable, e.g. "PNG image"
    mime: str  # Best-guess MIME type
    kind: (
        str  # FileForge kind: image/audio/video/document/archive/text/executable/other
    )
    extensions: tuple  # Extensions that legitimately carry this content


# (offset, magic bytes, description, mime, kind, extensions)
_SIGNATURES: list[tuple[int, bytes, str, str, str, tuple]] = [
    (0, b"\x89PNG\r\n\x1a\n", "PNG image", "image/png", "image", (".png",)),
    (
        0,
        b"\xff\xd8\xff",
        "JPEG image",
        "image/jpeg",
        "image",
        (".jpg", ".jpeg", ".jpe", ".jfif"),
    ),
    (0, b"GIF87a", "GIF image", "image/gif", "image", (".gif",)),
    (0, b"GIF89a", "GIF image", "image/gif", "image", (".gif",)),
    (0, b"BM", "BMP image", "image/bmp", "image", (".bmp", ".dib")),
    (
        0,
        b"II*\x00",
        "TIFF image",
        "image/tiff",
        "image",
        (".tif", ".tiff", ".dng", ".nef", ".cr2", ".arw"),
    ),
    (
        0,
        b"MM\x00*",
        "TIFF image",
        "image/tiff",
        "image",
        (".tif", ".tiff", ".dng", ".nef"),
    ),
    (0, b"\x00\x00\x01\x00", "ICO icon", "image/x-icon", "image", (".ico",)),
    (0, b"8BPS", "Photoshop document", "image/vnd.adobe.photoshop", "image", (".psd",)),
    (0, b"%PDF-", "PDF document", "application/pdf", "document", (".pdf",)),
    (0, b"{\\rtf", "RTF document", "application/rtf", "document", (".rtf",)),
    (
        0,
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
        "MS Office legacy (OLE2)",
        "application/x-ole-storage",
        "document",
        (".doc", ".xls", ".ppt", ".msi", ".msg"),
    ),
    (
        0,
        b"PK\x03\x04",
        "ZIP archive",
        "application/zip",
        "archive",
        (
            ".zip",
            ".docx",
            ".xlsx",
            ".pptx",
            ".odt",
            ".ods",
            ".odp",
            ".jar",
            ".apk",
            ".epub",
            ".whl",
            ".xpi",
            ".vsix",
            ".ipa",
        ),
    ),
    (0, b"PK\x05\x06", "ZIP archive (empty)", "application/zip", "archive", (".zip",)),
    (0, b"\x1f\x8b", "GZIP archive", "application/gzip", "archive", (".gz", ".tgz")),
    (0, b"BZh", "BZIP2 archive", "application/x-bzip2", "archive", (".bz2", ".tbz2")),
    (0, b"\xfd7zXZ\x00", "XZ archive", "application/x-xz", "archive", (".xz", ".txz")),
    (0, b"(\xb5/\xfd", "Zstandard archive", "application/zstd", "archive", (".zst",)),
    (
        0,
        b"7z\xbc\xaf\x27\x1c",
        "7-Zip archive",
        "application/x-7z-compressed",
        "archive",
        (".7z",),
    ),
    (0, b"Rar!\x1a\x07", "RAR archive", "application/vnd.rar", "archive", (".rar",)),
    (257, b"ustar", "TAR archive", "application/x-tar", "archive", (".tar",)),
    (
        0,
        b"MZ",
        "Windows executable (PE)",
        "application/vnd.microsoft.portable-executable",
        "executable",
        (".exe", ".dll", ".sys", ".scr", ".ocx", ".cpl", ".efi", ".com"),
    ),
    (
        0,
        b"\x7fELF",
        "ELF executable",
        "application/x-elf",
        "executable",
        (".so", ".o", ".elf", ".bin", ".out", ""),
    ),
    (
        0,
        b"\xcf\xfa\xed\xfe",
        "Mach-O executable (64-bit)",
        "application/x-mach-binary",
        "executable",
        (".dylib", ".bundle", ""),
    ),
    (
        0,
        b"\xce\xfa\xed\xfe",
        "Mach-O executable (32-bit)",
        "application/x-mach-binary",
        "executable",
        (".dylib", ".bundle", ""),
    ),
    (
        0,
        b"\xca\xfe\xba\xbe",
        "Java class / Mach-O universal",
        "application/java-vm",
        "executable",
        (".class", ".dylib", ""),
    ),
    (0, b"\x00asm", "WebAssembly module", "application/wasm", "executable", (".wasm",)),
    (0, b"#!", "Script (shebang)", "text/x-script", "text", ()),
    (
        0,
        b"SQLite format 3\x00",
        "SQLite database",
        "application/vnd.sqlite3",
        "other",
        (".sqlite", ".sqlite3", ".db", ".db3"),
    ),
    (0, b"ID3", "MP3 audio (ID3)", "audio/mpeg", "audio", (".mp3",)),
    (0, b"\xff\xfb", "MP3 audio", "audio/mpeg", "audio", (".mp3",)),
    (0, b"\xff\xf3", "MP3 audio", "audio/mpeg", "audio", (".mp3",)),
    (0, b"fLaC", "FLAC audio", "audio/flac", "audio", (".flac",)),
    (
        0,
        b"OggS",
        "Ogg container",
        "audio/ogg",
        "audio",
        (".ogg", ".oga", ".opus", ".ogv"),
    ),
    (0, b"MThd", "MIDI audio", "audio/midi", "audio", (".mid", ".midi")),
    (
        0,
        b"\x1aE\xdf\xa3",
        "Matroska / WebM video",
        "video/x-matroska",
        "video",
        (".mkv", ".webm", ".mka"),
    ),
    (0, b"FLV\x01", "Flash video", "video/x-flv", "video", (".flv",)),
    (0, b"wOFF", "WOFF font", "font/woff", "other", (".woff",)),
    (0, b"wOF2", "WOFF2 font", "font/woff2", "other", (".woff2",)),
    (0, b"OTTO", "OpenType font", "font/otf", "other", (".otf",)),
    (0, b"\x00\x01\x00\x00\x00", "TrueType font", "font/ttf", "other", (".ttf",)),
]

# How many leading bytes we need to read to evaluate every signature
SNIFF_BYTES = 512


def _sniff_riff(head: bytes) -> SniffResult | None:
    """RIFF containers: WAV, AVI, WEBP share the same 4-byte prefix."""
    if len(head) < 12 or head[:4] != b"RIFF":
        return None
    sub = head[8:12]
    if sub == b"WAVE":
        return SniffResult("WAV audio", "audio/wav", "audio", (".wav",))
    if sub == b"AVI ":
        return SniffResult("AVI video", "video/x-msvideo", "video", (".avi",))
    if sub == b"WEBP":
        return SniffResult("WebP image", "image/webp", "image", (".webp",))
    return SniffResult(
        "RIFF container", "application/octet-stream", "other", (".riff",)
    )


def _sniff_iso_bmff(head: bytes) -> SniffResult | None:
    """ISO base media (MP4, MOV, M4A, HEIC, AVIF) — 'ftyp' box at offset 4."""
    if len(head) < 12 or head[4:8] != b"ftyp":
        return None
    brand = head[8:12]
    if brand in (b"heic", b"heix", b"mif1", b"msf1", b"hevc"):
        return SniffResult("HEIF image", "image/heic", "image", (".heic", ".heif"))
    if brand in (b"avif", b"avis"):
        return SniffResult("AVIF image", "image/avif", "image", (".avif",))
    if brand in (b"M4A ", b"M4B ", b"M4P "):
        return SniffResult(
            "MPEG-4 audio", "audio/mp4", "audio", (".m4a", ".m4b", ".m4p")
        )
    if brand == b"qt  ":
        return SniffResult(
            "QuickTime video", "video/quicktime", "video", (".mov", ".qt")
        )
    return SniffResult(
        "MPEG-4 video", "video/mp4", "video", (".mp4", ".m4v", ".mov", ".3gp", ".3g2")
    )


def _looks_like_text(head: bytes) -> bool:
    """Heuristic: no NUL bytes and mostly printable / whitespace."""
    if not head:
        return False
    if head.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")):
        return True  # UTF-8 / UTF-16 BOM
    if b"\x00" in head:
        return False
    printable = sum(1 for b in head if b >= 0x20 or b in (0x09, 0x0A, 0x0D))
    return printable / len(head) > 0.95


def sniff_bytes(head: bytes) -> SniffResult | None:
    """Identify content from its first bytes. Returns None when unknown."""
    if not head:
        return None

    riff = _sniff_riff(head)
    if riff:
        return riff
    bmff = _sniff_iso_bmff(head)
    if bmff:
        return bmff

    is_text = _looks_like_text(head)
    for offset, magic, desc, mime, kind, exts in _SIGNATURES:
        # Very short magics ("BM", "MZ") collide with ordinary text — skip them for text content
        if len(magic) <= 2 and is_text:
            continue
        if head[offset : offset + len(magic)] == magic:
            return SniffResult(desc, mime, kind, exts)

    stripped = head.lstrip()
    if stripped[:5].lower() == b"<?xml":
        if b"<svg" in head:
            return SniffResult("SVG image", "image/svg+xml", "image", (".svg",))
        return SniffResult(
            "XML document",
            "application/xml",
            "text",
            (".xml", ".svg", ".plist", ".xaml", ".csproj", ".config"),
        )
    if stripped[:9].lower() in (b"<!doctype",) or stripped[:5].lower() == b"<html":
        return SniffResult(
            "HTML document", "text/html", "text", (".html", ".htm", ".xhtml")
        )

    if is_text:
        return SniffResult("Plain text", "text/plain", "text", ())
    return None


def sniff_file(path: str) -> SniffResult | None:
    """Read the file header and identify it. Never raises."""
    try:
        with open(path, "rb") as f:
            head = f.read(SNIFF_BYTES)
    except (OSError, PermissionError):
        return None
    return sniff_bytes(head)


def extension_mismatch(result: SniffResult | None, suffix: str) -> bool:
    """
    True when the detected content clearly contradicts the file extension.
    Plain text and unknown content never count as a mismatch (too ambiguous).
    """
    if result is None or not result.extensions:
        return False
    suffix = suffix.lower()
    if suffix in result.extensions:
        return False
    # Files with no extension are only flagged when the format normally has one
    if suffix == "" and "" in result.extensions:
        return False
    return True
