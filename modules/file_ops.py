"""
file_ops.py — All write / mutate operations on files.
Every function returns (success: bool, message: str).
"""

from __future__ import annotations
import os
import shutil
import time
import platform
import stat
from pathlib import Path
from typing import Optional

# ── Rename / Move ──────────────────────────────────────────────────────────

def rename_file(path: str, new_name: str) -> tuple[bool, str]:
    """Rename file within the same directory"""
    p = Path(path)
    dest = p.parent / new_name
    if dest.exists():
        return False, f"A file named '{new_name}' already exists."
    try:
        p.rename(dest)
        return True, f"Renamed to '{new_name}'."
    except Exception as e:
        return False, str(e)
    
def move_file(path: str, dest_dir: str) -> tuple[bool, str]:
    """Move file to a different directory."""
    try:
        dest = shutil.move(path, dest_dir)
        return True, f"Moved to '{dest}'."
    except Exception as e:
        return False, str(e)
 
def copy_file(path: str, dest: str) -> tuple[bool, str]:
    """Copy file, preserving metadata."""
    try:
        shutil.copy2(path, dest)
        return True, f"Copied to '{dest}'."
    except Exception as e:
        return False, str(e)
    
# ── Timestamps ────────────────────────────────────────────────────────────

def set_timestamps(path: str, modified: Optional[float] = None, accessed: Optional[float] = None) -> tuple[bool, str]:
    """Set atime and/or mtime. Pass None to leave unchanged."""
    try:
        st = os.stat(path)
        atime = accessed if accessed is not None else st.st_atime
        mtime = modified if modified is not None else st.st_mtime
        os.utime(path, (atime, mtime))
        return True, "Timestamps updated."
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
    """Set permissions via octal string like '0755'."""
    if platform.system() == "Windows":
        return False, "Octal permissions are not supported on Windows."
    try:
        mode = int(octal_str, 8)
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
    if platform.system() == "Windows":
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
        "owner_read": stat.S_IRUSR, "owner_write": stat.S_IWUSR, "owner_exec": stat.S_IXUSR,
        "group_read": stat.S_IRGRP, "group_write": stat.S_IWGRP, "group_exec": stat.S_IXGRP,
        "other_read": stat.S_IROTH, "other_write": stat.S_IWOTH, "other_exec": stat.S_IXOTH,
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
    
def set_hidden(path: str, hidden: bool) -> tuple[bool, str]:
    """Toggle hidden attribute (Unix: prepend dot; Windows: attrib)."""
    p = Path(path)
    if platform.system() == "Windows":
        import ctypes
        FILE_ATTRIBUTES_HIDDEN = 0x02
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))
        if hidden:
            attrs |= FILE_ATTRIBUTES_HIDDEN
        else:
            attrs &= ~FILE_ATTRIBUTES_HIDDEN

        ok = ctypes.windll.kernel32.SetFileAttributesW(str(p), attrs)
        return (True, "Hidden attribute set.") if ok else (False, "Failed to set attribute.")
    else:
        # Unix: rename with/without leading dot
        if hidden and not p.name.startswith("."):
            dest = p.parent / f".{p.name}"
        elif not hidden and p.name.startswith("."):
            dest = p.parent / p.name.lstrip(".")
        else:
            return True, "No change needed."
        if dest.exists():
            return False, f"'{dest.name}' already exists."
        try:
            p.rename(dest)
            return True, f"Renamed to '{dest.name}'"
        except Exception as e:
            return False, str(e)
        
# ── Extension ─────────────────────────────────────────────────────────────

def change_extension(path: str, new_ext: str) -> tuple[bool, str]:
    """Change the file extension (new_ext may or may not include dot)."""
    p = Path(path)
    if not new_ext.startswith("."):
        new_ext = "." + new_ext
    dest = p.with_suffix(new_ext)
    if dest.exists():
        return False, f"'{dest.name}' already exists."
    try:
        p.rename(dest)
        return True, f"Extension changed to '{new_ext}'."
    except Exception as e:
        return False, str(e)
    
# ── Content truncation / zeroing ──────────────────────────────────────────

def truncate_file(path: str, size: int) -> tuple[bool, str]:
    """Truncate file to given byte size."""
    try: 
        with open(path, "ab") as f:
                f.truncate(size)
        return True, f"File truncated to {size} bytes"
    except Exception as e:
        return False, str(e)
    
def zero_file(path: str) -> tuple[bool, str]:
    """Empty file contents (zero bytes)."""
    try:
        open(path, "w").close()
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
        for k, v in tags.items():
            try:
                mf.tags[k] = [v]
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

def batch_rename_preview(paths: list[str], pattern: str, replacement: str) -> list[tuple[str, str]]:
    """
    Preview batch rename: find `pattern` in filename, replace with `replacement`.
    Returns list of (old_name, new_name).
    """
    import re
    results = []
    for path in paths:
        p = Path(path)
        try:
            new_name = re.sub(pattern, replacement, p.name)
        except re.error:
            new_name = p.name.replace(pattern, replacement)
        results.append((p.name, new_name))
    return results

def batch_rename_apply(paths: list[str], pattern: str, replacement: str) -> list[tuple[str, bool, str]]:
    """
    Apply batch rename. Returns list of (original_path, success, message).
    """
    import re
    results = []
    for path in paths:
        p = Path(path)
        try:
            new_name = re.sub(pattern, replacement, p.name)
        except re.error:
            new_name = p.name.replace(pattern, replacement)
        if new_name == p.name:
            results.append((path, True, "No change."))
            continue
        dest = p.parent / new_name
        if dest.exists():
            results.append((path, False, f"'{new_name}' already exists."))
            continue
        try:
            p.rename(dest)
            results.append((path, True, f"-> '{new_name}'"))
        except Exception as e:
            results.append((path, False, str(e)))
    return results