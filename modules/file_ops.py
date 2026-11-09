"""
file_ops.py — All write / mutate operations on files.
Every function returns (success: bool, message: str).
"""

from __future__ import annotations
import os
import re
import shutil
import time
import platform
import stat
import uuid
from pathlib import Path
from typing import Optional

_IS_WINDOWS = platform.system() == "Windows"

# Characters that can never appear in a single path component
_INVALID_NAME_CHARS = set('<>:"/\\|?*') if _IS_WINDOWS else {"/", "\0"}


def validate_filename(name: str) -> Optional[str]:
    """Return an error message if `name` is not a valid bare filename, else None."""
    if not name or name in (".", ".."):
        return "Filename cannot be empty."
    bad = sorted(c for c in set(name) if c in _INVALID_NAME_CHARS or ord(c) < 32)
    if bad:
        return "Filename contains invalid character(s): " + " ".join(
            repr(c) for c in bad
        )
    if os.sep in name or (os.altsep and os.altsep in name):
        return "Filename cannot contain a path separator — use Move instead."
    if _IS_WINDOWS and name.rstrip(" .") != name:
        return "Windows filenames cannot end with a space or a dot."
    return None


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def _safe_rename(src: Path, dest: Path):
    """
    Rename src → dest. Handles case-only renames on case-insensitive file systems
    (Windows / default macOS), where `dest.exists()` is True because it *is* src.
    """
    if _same_file(src, dest) and src.name != dest.name:
        tmp = src.with_name(f".{src.name}.{uuid.uuid4().hex[:8]}.tmp")
        src.rename(tmp)
        tmp.rename(dest)
    else:
        src.rename(dest)


# ── Rename / Move ──────────────────────────────────────────────────────────


def rename_file(path: str, new_name: str) -> tuple[bool, str]:
    """Rename file within the same directory"""
    err = validate_filename(new_name)
    if err:
        return False, err
    p = Path(path)
    dest = p.parent / new_name
    if new_name == p.name:
        return True, "Name unchanged."
    if dest.exists() and not _same_file(p, dest):
        return False, f"A file named '{new_name}' already exists."
    try:
        _safe_rename(p, dest)
        return True, f"Renamed to '{new_name}'."
    except Exception as e:
        return False, str(e)


def move_destination(path: str, dest: str) -> str:
    """Final path a file will have after move_file(path, dest)."""
    if os.path.isdir(dest):
        return os.path.join(dest, os.path.basename(path))
    return dest


def move_file(path: str, dest_dir: str, overwrite: bool = False) -> tuple[bool, str]:
    """Move file to a different directory (or to an explicit target path)."""
    target = move_destination(path, dest_dir)
    if os.path.exists(target) and not overwrite:
        return False, f"'{target}' already exists."
    try:
        dest = shutil.move(path, target)
        return True, f"Moved to '{dest}'."
    except Exception as e:
        return False, str(e)


def copy_file(path: str, dest: str, overwrite: bool = False) -> tuple[bool, str]:
    """Copy file, preserving metadata. Refuses to clobber an existing file unless asked."""
    target = move_destination(path, dest)
    if os.path.abspath(target) == os.path.abspath(path):
        return False, "Source and destination are the same file."
    if os.path.exists(target) and not overwrite:
        return False, f"'{target}' already exists."
    try:
        shutil.copy2(path, target)
        return True, f"Copied to '{target}'."
    except Exception as e:
        return False, str(e)


# ── Timestamps ────────────────────────────────────────────────────────────


def set_timestamps(
    path: str, modified: Optional[float] = None, accessed: Optional[float] = None
) -> tuple[bool, str]:
    """Set atime and/or mtime. Pass None to leave unchanged."""
    try:
        st = os.stat(path)
        atime = accessed if accessed is not None else st.st_atime
        mtime = modified if modified is not None else st.st_mtime
        os.utime(path, (atime, mtime))
        return True, "Timestamps updated."
    except Exception as e:
        return False, str(e)


def can_set_created_time() -> bool:
    """Creation time is only writable through the Win32 API."""
    return _IS_WINDOWS


def set_created_time(path: str, created: float) -> tuple[bool, str]:
    """Set the file creation (birth) time. Windows only."""
    if not _IS_WINDOWS:
        return False, "Changing the creation time is only supported on Windows."
    try:
        import ctypes
        from ctypes import wintypes

        # FILETIME = 100-ns intervals since 1601-01-01
        ft_int = int((created + 11644473600) * 10_000_000)
        ft = wintypes.FILETIME(ft_int & 0xFFFFFFFF, ft_int >> 32)

        kernel32 = ctypes.windll.kernel32
        FILE_WRITE_ATTRIBUTES = 0x100
        OPEN_EXISTING = 3
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
        kernel32.CreateFileW.restype = wintypes.HANDLE
        handle = kernel32.CreateFileW(
            str(path),
            FILE_WRITE_ATTRIBUTES,
            0x7,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle in (None, wintypes.HANDLE(-1).value):
            return False, f"Could not open file (error {ctypes.GetLastError()})."
        try:
            ok = kernel32.SetFileTime(handle, ctypes.byref(ft), None, None)
        finally:
            kernel32.CloseHandle(handle)
        return (
            (True, "Creation time updated.")
            if ok
            else (False, f"SetFileTime failed (error {ctypes.GetLastError()}).")
        )
    except Exception as e:
        return False, str(e)


def touch_file(path: str) -> tuple[bool, str]:
    """Update modified and accessed time to now."""
    try:
        now = time.time()
        os.utime(path, (now, now))
        return True, "Timestamps set to now."
    except Exception as e:
        return False, str(e)


# ── Permissions ───────────────────────────────────────────────────────────


def set_permissions_octal(path: str, octal_str: str) -> tuple[bool, str]:
    """Set permissions via octal string like '0755' (also accepts '755' or '0o755')."""
    if _IS_WINDOWS:
        return False, "Octal permissions are not supported on Windows."
    try:
        mode = int(octal_str.strip().lower().replace("0o", ""), 8)
        if not 0 <= mode <= 0o7777:
            return False, f"Octal value out of range: '{octal_str}'."
        os.chmod(path, mode)
        return True, f"Permissions set to {octal_str}."
    except ValueError:
        return False, f"Invalid octal: '{octal_str}'."
    except Exception as e:
        return False, str(e)


def set_permissions_bits(path: str, **bits) -> tuple[bool, str]:
    """
    Set individual permission bits.
    kwargs: owner_read, owner_write, owner_exec,
            group_read, group_write, group_exec,
            other_read, other_write, other_exec  (bool)
    """
    if _IS_WINDOWS:
        # Windows: only handle read-only flag
        try:
            current = os.stat(path).st_mode
            if "owner_write" in bits:
                if bits["owner_write"]:
                    os.chmod(path, current | stat.S_IWRITE)
                else:
                    os.chmod(path, current & ~stat.S_IWRITE)
            return True, "Permissions updated (Windows: read-only flag)."
        except Exception as e:
            return False, str(e)

    bit_map = {
        "owner_read": stat.S_IRUSR,
        "owner_write": stat.S_IWUSR,
        "owner_exec": stat.S_IXUSR,
        "group_read": stat.S_IRGRP,
        "group_write": stat.S_IWGRP,
        "group_exec": stat.S_IXGRP,
        "other_read": stat.S_IROTH,
        "other_write": stat.S_IWOTH,
        "other_exec": stat.S_IXOTH,
    }
    try:
        current = stat.S_IMODE(os.stat(path).st_mode)
        for key, val in bits.items():
            if key in bit_map:
                if val:
                    current |= bit_map[key]
                else:
                    current &= ~bit_map[key]
        os.chmod(path, current)
        return True, f"Permissions updated -> {oct(current)}."
    except Exception as e:
        return False, str(e)


def hidden_target_path(path: str, hidden: bool) -> str:
    """Path the file will have after set_hidden() (Unix renames; Windows doesn't)."""
    p = Path(path)
    if _IS_WINDOWS:
        return str(p)
    if hidden and not p.name.startswith("."):
        return str(p.parent / f".{p.name}")
    if not hidden and p.name.startswith("."):
        return str(p.parent / p.name.lstrip("."))
    return str(p)


def set_hidden(path: str, hidden: bool) -> tuple[bool, str]:
    """Toggle hidden attribute (Unix: prepend dot; Windows: attrib)."""
    p = Path(path)
    if _IS_WINDOWS:
        try:
            import ctypes

            FILE_ATTRIBUTE_HIDDEN = 0x02
            INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.GetFileAttributesW.restype = ctypes.c_uint32
            attrs = kernel32.GetFileAttributesW(str(p))
            if attrs == INVALID_FILE_ATTRIBUTES:
                # Without this check the error value (all bits set) would be written back
                # as the file's attributes (read-only, system, …)
                return (
                    False,
                    f"Could not read file attributes (error {ctypes.GetLastError()}).",
                )  # type: ignore[attr-defined]
            if hidden:
                attrs |= FILE_ATTRIBUTE_HIDDEN
            else:
                attrs &= ~FILE_ATTRIBUTE_HIDDEN
            ok = kernel32.SetFileAttributesW(str(p), attrs)
            if not ok:
                return False, "Failed to set attribute."
            return (
                True,
                "Hidden attribute set." if hidden else "Hidden attribute cleared.",
            )
        except Exception as e:
            return False, str(e)
    else:
        # Unix: rename with/without leading dot
        dest = Path(hidden_target_path(path, hidden))
        if dest == p:
            return True, "No change needed."
        if not dest.name:
            return False, "File name would be empty after removing the leading dot."
        if dest.exists():
            return False, f"'{dest.name}' already exists."
        try:
            p.rename(dest)
            return True, f"Renamed to '{dest.name}'"
        except Exception as e:
            return False, str(e)


# ── Extension ─────────────────────────────────────────────────────────────


def extension_target_path(path: str, new_ext: str) -> str:
    """Path the file will have after change_extension()."""
    if new_ext and not new_ext.startswith("."):
        new_ext = "." + new_ext
    return str(Path(path).with_suffix(new_ext))


def change_extension(path: str, new_ext: str) -> tuple[bool, str]:
    """Change the file extension (new_ext may or may not include dot)."""
    p = Path(path)
    if not new_ext.startswith("."):
        new_ext = "." + new_ext
    if new_ext == "." or validate_filename("x" + new_ext):
        return False, f"Invalid extension: '{new_ext}'."
    try:
        dest = p.with_suffix(new_ext)
    except ValueError:
        return False, f"Invalid extension: '{new_ext}'."
    if dest == p:
        return True, "Extension unchanged."
    # Case-only change (.JPG -> .jpg) on a case-insensitive file system: dest "exists" because it *is* p
    if dest.exists() and not _same_file(p, dest):
        return False, f"'{dest.name}' already exists."
    try:
        _safe_rename(p, dest)
        return True, f"Extension changed to '{new_ext}'."
    except Exception as e:
        return False, str(e)


# ── Content truncation / zeroing ──────────────────────────────────────────


def truncate_file(path: str, size: int) -> tuple[bool, str]:
    """Truncate file to given byte size."""
    try:
        with open(path, "r+b") as f:
            f.truncate(size)
        return True, f"File truncated to {size} bytes"
    except Exception as e:
        return False, str(e)


def zero_file(path: str) -> tuple[bool, str]:
    """Empty file contents (zero bytes)."""
    try:
        with open(path, "wb"):
            pass
        return True, "File zeroed (0 bytes)."
    except Exception as e:
        return False, str(e)


# ── Audio tags (mutagen) ──────────────────────────────────────────────────


def write_audio_tags(path: str, tags: dict[str, str]) -> tuple[bool, str]:
    """Write audio metadata tags via mutagen (easy interface)."""
    try:
        from mutagen._file import File as MutagenFile

        mf = MutagenFile(path, easy=True)
        if mf is None:
            return False, "Mutagen cannot handle this file format."
        if mf.tags is None:
            mf.add_tags()
        mf_tags = mf.tags
        if mf_tags is None:
            return False, "Could not create a tag block for this file."
        for k, v in tags.items():
            try:
                mf_tags[k] = [v]
            except Exception:
                pass
        mf.save()
        return True, "Audio tags saved."
    except ImportError:
        return False, "mutagen is not installed."
    except Exception as e:
        return False, str(e)


def delete_audio_tags(path: str) -> tuple[bool, str]:
    """Delete all audio tags from a file."""
    try:
        from mutagen._file import File as MutagenFile

        mf = MutagenFile(path)
        if mf is None:
            return False, "Mutagen cannot handle this file format."
        mf.delete()
        return True, "All audio tags deleted."
    except ImportError:
        return False, "mutagen is not installed."
    except Exception as e:
        return False, str(e)


# ── Batch rename helpers ───────────────────────────────────────────────────


def _substitute(name: str, pattern: str, replacement: str) -> str:
    """re.sub with a literal fallback. An empty pattern means "no find/replace"."""
    if not pattern:
        return name
    try:
        return re.sub(pattern, replacement, name)
    except re.error:
        return name.replace(pattern, replacement)


def batch_rename_preview(
    paths: list[str], pattern: str, replacement: str
) -> list[tuple[str, str]]:
    """
    Preview batch rename: find `pattern` in filename, replace with `replacement`.
    Returns list of (old_name, new_name).
    """
    return [
        (Path(p).name, _substitute(Path(p).name, pattern, replacement)) for p in paths
    ]


def batch_rename_conflicts(paths: list[str], new_names: list[str]) -> dict[int, str]:
    """
    Detect problems before renaming anything.
    Returns {index: reason} for every entry that would fail or clobber another file.
    """
    problems: dict[int, str] = {}
    targets: dict[str, int] = {}
    sources = {os.path.normcase(os.path.abspath(p)) for p in paths}
    for i, (path, new_name) in enumerate(zip(paths, new_names)):
        p = Path(path)
        if new_name == p.name:
            continue
        err = validate_filename(new_name)
        if err:
            problems[i] = err
            continue
        dest = os.path.normcase(os.path.abspath(p.parent / new_name))
        if dest in targets:
            problems[i] = f"Duplicate target name '{new_name}'."
            problems.setdefault(targets[dest], f"Duplicate target name '{new_name}'.")
            continue
        targets[dest] = i
        if (
            os.path.exists(dest)
            and dest not in sources
            and not _same_file(p, Path(dest))
        ):
            problems[i] = f"'{new_name}' already exists."
    return problems


def batch_rename_to(
    paths: list[str], new_names: list[str]
) -> list[tuple[str, bool, str, str]]:
    """
    Rename each path to the matching new name (same directory).
    Validates the whole batch first so a collision can't leave it half-applied,
    and goes through temporary names so swaps (a→b, b→a) work.
    Returns list of (original_path, success, message, new_path).
    """
    problems = batch_rename_conflicts(paths, new_names)
    results: list[tuple[str, bool, str, str]] = []
    staged: list[tuple[int, Path, Path]] = []

    for i, (path, new_name) in enumerate(zip(paths, new_names)):
        p = Path(path)
        if i in problems:
            results.append((path, False, problems[i], path))
        elif new_name == p.name:
            results.append((path, True, "No change.", path))
        else:
            results.append((path, True, "", path))
            staged.append((i, p, p.parent / new_name))

    # Phase 1: move every source out of the way
    temps: list[tuple[int, Path, Path, Path]] = []
    for i, src, dest in staged:
        tmp = src.with_name(f".ffbatch-{uuid.uuid4().hex[:10]}.tmp")
        try:
            src.rename(tmp)
            temps.append((i, src, tmp, dest))
        except Exception as e:
            results[i] = (str(src), False, str(e), str(src))

    # Phase 2: temp → final (restore original name on failure)
    for i, src, tmp, dest in temps:
        try:
            if dest.exists():
                raise FileExistsError(f"'{dest.name}' already exists.")
            tmp.rename(dest)
            results[i] = (str(src), True, f"-> '{dest.name}'", str(dest))
        except Exception as e:
            try:
                tmp.rename(src)
            except Exception:
                pass
            results[i] = (str(src), False, str(e), str(src))
    return results


def batch_rename_apply(
    paths: list[str], pattern: str, replacement: str
) -> list[tuple[str, bool, str]]:
    """
    Apply batch rename. Returns list of (original_path, success, message).
    """
    new_names = [_substitute(Path(p).name, pattern, replacement) for p in paths]
    return [(orig, ok, msg) for orig, ok, msg, _ in batch_rename_to(paths, new_names)]
