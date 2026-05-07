"""
strings_extractor.py — Extract printable strings from binary files.
"""

from __future__ import annotations
import os
import re
from typing import List, Tuple, Iterator


def extract_strings(file_path: str, min_length: int = 4, encoding: str = 'ascii') -> List[Tuple[int, str]]:
    """
    Extract printable strings from a binary file.

    Args:
        file_path: Path to the file to analyze
        min_length: Minimum string length to extract
        encoding: Text encoding to use ('ascii', 'utf-8', 'utf-16', 'latin-1')

    Returns:
        List of (offset, string) tuples
    """
    strings = []

    try:
        # Use streaming approach to avoid loading entire file into memory
        for offset, string in extract_strings_streaming(file_path, min_length, encoding):
            strings.append((offset, string))

    except (OSError, IOError):
        pass

    return strings


def extract_strings_streaming(file_path: str, min_length: int = 4, encoding: str = 'ascii',
                               chunk_size: int = 1_000_000) -> Iterator[Tuple[int, str]]:
    """
    Extract printable strings from a binary file using streaming approach.

    Args:
        file_path: Path to the file to analyze
        min_length: Minimum string length to extract
        encoding: Text encoding to use
        chunk_size: Size of chunks to read at a time

    Yields:
        (offset, string) tuples
    """
    # Define printable characters based on encoding
    if encoding == 'ascii':
        # ASCII printable characters (32-126)
        pattern = re.compile(b'[\x20-\x7E]{' + str(min_length).encode() + b',}')
    elif encoding == 'utf-8':
        # UTF-8 printable characters
        pattern = re.compile(b'[\x20-\x7E\xC2-\xF4][\x80-\xBF]*{' + str(max(0, min_length-1)).encode() + b',}')
    elif encoding == 'utf-16':
        # UTF-16 (little endian)
        pattern = re.compile(b'(?:[\x20-\x7E]\x00){' + str(min_length).encode() + b',}')
    elif encoding == 'latin-1':
        # Latin-1 printable characters
        pattern = re.compile(b'[\x20-\xFF]{' + str(min_length).encode() + b',}')
    else:
        # Default to ASCII
        pattern = re.compile(b'[\x20-\x7E]{' + str(min_length).encode() + b',}')

    buffer = bytearray(chunk_size + min_length)
    overlap = bytearray()
    file_pos = 0

    with open(file_path, 'rb') as f:
        while True:
            bytes_read = f.readinto(buffer)
            if not bytes_read:
                break

            # Process buffer with overlap from previous chunk
            process_data = overlap + buffer[:bytes_read]

            for match in pattern.finditer(process_data):
                try:
                    string_bytes = match.group()
                    if encoding == 'utf-16':
                        # Decode UTF-16 LE
                        decoded = string_bytes.decode('utf-16-le', errors='ignore')
                    else:
                        decoded = string_bytes.decode(encoding, errors='ignore')

                    if len(decoded) >= min_length:
                        offset = file_pos + match.start() - len(overlap)
                        yield (offset, decoded)
                except UnicodeDecodeError:
                    continue

            # Prepare overlap for next chunk
            overlap = process_data[-(min_length-1):] if len(process_data) >= min_length else bytearray()
            file_pos += bytes_read


def extract_strings_with_context(file_path: str, min_length: int = 4, encoding: str = 'ascii', context_bytes: int = 16) -> List[Tuple[int, str, bytes, bytes]]:
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

        with open(file_path, 'rb') as f:
            data = f.read()

        strings = extract_strings(file_path, min_length, encoding)

        for offset, string in strings:
            # Get context before
            before_start = max(0, offset - context_bytes)
            before_bytes = data[before_start:offset]

            # Get context after
            after_end = min(len(data), offset + len(string.encode(encoding, errors='ignore')) + context_bytes)
            after_bytes = data[offset + len(string.encode(encoding, errors='ignore')):after_end]

            strings_with_context.append((offset, string, before_bytes, after_bytes))

    except (OSError, IOError):
        pass

    return strings_with_context


def filter_strings(strings: List[Tuple[int, str]], search_term: str = "",
                  case_sensitive: bool = False) -> List[Tuple[int, str]]:
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