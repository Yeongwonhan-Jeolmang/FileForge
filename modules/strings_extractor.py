"""
strings_extractor.py — Extract printable strings from binary files.
"""

from __future__ import annotations
import os
import re
from typing import List, Tuple, Iterator, Optional, Callable


def extract_strings(
    file_path: str,
    min_length: int = 4,
    encoding: str = "ascii",
    max_results: Optional[int] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> List[Tuple[int, str]]:
    """
    Extract printable strings from a binary file.

    Args:
        file_path: Path to the file to analyze
        min_length: Minimum string length to extract
        encoding: Text encoding to use ('ascii', 'utf-8', 'utf-16', 'latin-1')
        max_results: Stop after this many strings (None = unlimited)
        cancel_cb: Polled periodically; returning True stops extraction early

    Returns:
        List of (offset, string) tuples
    """
    strings = []

    try:
        # Use streaming approach to avoid loading entire file into memory
        for offset, string in extract_strings_streaming(
            file_path, min_length, encoding
        ):
            strings.append((offset, string))
            if max_results is not None and len(strings) >= max_results:
                break
            if cancel_cb is not None and not (len(strings) & 0x3FF) and cancel_cb():
                break

    except (OSError, IOError):
        pass

    return strings


def _build_pattern(encoding: str, min_length: int) -> "re.Pattern[bytes]":
    """Compile the byte-level regex that matches a printable run for `encoding`."""
    n = str(max(1, min_length)).encode()
    if encoding == "utf-8":
        # A printable ASCII byte or a complete, well-formed multi-byte UTF-8 sequence
        char = (
            b"(?:[\x20-\x7e\t]"
            b"|[\xc2-\xdf][\x80-\xbf]"
            b"|[\xe0-\xef][\x80-\xbf]{2}"
            b"|[\xf0-\xf4][\x80-\xbf]{3})"
        )
        return re.compile(char + b"{" + n + b",}")
    if encoding == "utf-16":
        # UTF-16 LE: printable ASCII followed by a NUL high byte
        return re.compile(b"(?:[\x20-\x7e]\x00){" + n + b",}")
    if encoding == "latin-1":
        # Printable Latin-1, excluding the C1 control range 0x7F-0x9F
        return re.compile(b"[\x20-\x7e\xa0-\xff]{" + n + b",}")
    # ASCII (default)
    return re.compile(b"[\x20-\x7e]{" + n + b",}")


def extract_strings_streaming(
    file_path: str,
    min_length: int = 4,
    encoding: str = "ascii",
    chunk_size: int = 1_000_000,
    max_string_length: int = 65_536,
) -> Iterator[Tuple[int, str]]:
    """
    Extract printable strings from a binary file using streaming approach.

    Strings that straddle a chunk boundary are carried over to the next chunk
    and reported exactly once, with their true file offset.

    Args:
        file_path: Path to the file to analyze
        min_length: Minimum string length to extract
        encoding: Text encoding to use
        chunk_size: Size of chunks to read at a time
        max_string_length: Runs longer than this (bytes) are flushed in pieces
                           so a huge text region can't grow the buffer forever

    Yields:
        (offset, string) tuples
    """
    pattern = _build_pattern(encoding, min_length)
    codec = (
        "utf-16-le"
        if encoding == "utf-16"
        else ("ascii" if encoding not in ("utf-8", "latin-1") else encoding)
    )
    char_width = 2 if encoding == "utf-16" else (4 if encoding == "utf-8" else 1)
    # Any match starting in the last `tail` bytes might still be growing / not yet long enough
    tail = min_length * char_width

    carry = b""
    carry_offset = 0  # file offset of carry[0]

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            eof = not chunk
            data = carry + chunk
            base = carry_offset
            if not data:
                break

            cut = len(data) if eof else max(0, len(data) - tail)
            last_end = 0
            for match in pattern.finditer(data):
                if (
                    not eof
                    and match.end() == len(data)
                    and match.end() - match.start() < max_string_length
                ):
                    # Run touches the end of the buffer: it may continue in the next chunk
                    cut = min(cut, match.start())
                    break
                if match.start() >= cut:
                    break
                last_end = match.end()
                decoded = match.group().decode(codec, errors="ignore")
                if len(decoded) >= min_length:
                    yield (base + match.start(), decoded)

            if eof:
                break
            # Never re-scan bytes that belong to a string we already reported
            cut = max(cut, last_end)
            # UTF-16 strings must stay 2-byte aligned relative to the carry start
            if char_width == 2 and (cut % 2):
                cut -= 1
            carry = data[cut:]
            carry_offset = base + cut


def extract_strings_with_context(
    file_path: str,
    min_length: int = 4,
    encoding: str = "ascii",
    context_bytes: int = 16,
) -> List[Tuple[int, str, bytes, bytes]]:
    """
    Extract strings with surrounding context bytes.

    Returns:
        List of (offset, string, before_bytes, after_bytes) tuples
    """
    strings_with_context = []

    try:
        # Read entire file for context extraction (this is necessary for context)
        # but limit to reasonable size to avoid memory issues
        file_size = os.path.getsize(file_path)
        if file_size > 100_000_000:  # 100MB limit
            return []  # Skip context extraction for very large files

        with open(file_path, "rb") as f:
            data = f.read()

        strings = extract_strings(file_path, min_length, encoding)
        # Same codec the extractor decoded with. Plain 'utf-16' would prepend a
        # 2-byte BOM and shift every "after" window.
        codec = "utf-16-le" if encoding == "utf-16" else encoding

        for offset, string in strings:
            # Get context before
            before_start = max(0, offset - context_bytes)
            before_bytes = data[before_start:offset]

            # Get context after
            end = offset + len(string.encode(codec, errors="ignore"))
            after_end = min(len(data), end + context_bytes)
            after_bytes = data[end:after_end]

            strings_with_context.append((offset, string, before_bytes, after_bytes))

    except (OSError, IOError):
        pass

    return strings_with_context


def filter_strings(
    strings: List[Tuple[int, str]], search_term: str = "", case_sensitive: bool = False
) -> List[Tuple[int, str]]:
    """
    Filter strings based on search criteria.

    Args:
        strings: List of (offset, string) tuples
        search_term: Term to search for (empty string = no filtering)
        case_sensitive: Whether search should be case sensitive

    Returns:
        Filtered list of strings
    """
    if not search_term:
        return strings

    filtered = []
    flags = 0 if case_sensitive else re.IGNORECASE

    try:
        pattern = re.compile(search_term, flags)
        for offset, string in strings:
            if pattern.search(string):
                filtered.append((offset, string))
    except re.error:
        # Invalid regex, fall back to simple string search
        for offset, string in strings:
            search_str = string if case_sensitive else string.lower()
            search_term_cmp = search_term if case_sensitive else search_term.lower()
            if search_term_cmp in search_str:
                filtered.append((offset, string))

    return filtered
