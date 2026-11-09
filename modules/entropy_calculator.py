"""
entropy_calculator.py — Calculate Shannon entropy for files.
"""

from __future__ import annotations
import math
import os
from collections import Counter
from modules.metadata_cache import cached_entropy


@cached_entropy
def calculate_entropy(file_path: str, sample_size: int | None = None) -> float:
    """
    Calculate Shannon entropy of a file.

    Args:
        file_path: Path to the file
        sample_size: If provided, only sample this many bytes from the file

    Returns:
        Entropy value between 0.0 (no randomness) and 8.0 (maximum randomness for bytes)
    """
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return 0.0

        # Read the file or a sample
        with open(file_path, "rb") as f:
            if sample_size and file_size > sample_size:
                # Sample from start, middle, and end for better distribution
                data = b""
                sample_chunk = sample_size // 3

                # Start
                data += f.read(sample_chunk)

                # Middle
                f.seek(file_size // 2)
                data += f.read(sample_chunk)

                # End
                f.seek(max(0, file_size - sample_chunk))
                data += f.read(sample_chunk)

                # Trim to exact sample size
                data = data[:sample_size]
            else:
                data = f.read()

        if not data:
            return 0.0

        return entropy_of_bytes(data)

    except (OSError, IOError):
        return 0.0


def entropy_of_bytes(data: bytes) -> float:
    """Shannon entropy (bits/byte) of an in-memory buffer."""
    if not data:
        return 0.0
    # Counter's C fast-path is the quickest pure-stdlib way to histogram bytes
    byte_counts = Counter(data)
    total_bytes = len(data)
    entropy = 0.0
    for count in byte_counts.values():
        probability = count / total_bytes
        entropy -= probability * math.log2(probability)
    return entropy


def entropy_profile(
    file_path: str, blocks: int = 64, block_size: int = 32_768
) -> list[float]:
    """
    Entropy of `blocks` evenly spaced regions across the file.

    Useful to spot packed / encrypted / compressed sections inside an otherwise
    structured file (e.g. a payload appended to an executable). Reads at most
    blocks * block_size bytes (2 MiB by default) regardless of file size.
    """
    try:
        size = os.path.getsize(file_path)
    except OSError:
        return []
    if size == 0:
        return []

    if size <= blocks * block_size:
        # Small file: split it into contiguous slices
        with open(file_path, "rb") as f:
            data = f.read()
        n = min(blocks, max(1, size // 256))
        step = max(1, size // n)
        return [
            entropy_of_bytes(data[i * step : (i + 1) * step if i < n - 1 else size])
            for i in range(n)
        ]

    result = []
    stride = size / blocks
    with open(file_path, "rb") as f:
        for i in range(blocks):
            f.seek(int(i * stride))
            result.append(entropy_of_bytes(f.read(block_size)))
    return result


def entropy_percentage(entropy: float) -> float:
    """Convert entropy to a percentage (0-100)."""
    return min(100.0, (entropy / 8.0) * 100.0)


def entropy_description(entropy: float) -> str:
    """Get a human-readable description of entropy level."""
    if entropy < 1.0:
        return "Very low (highly structured)"
    elif entropy < 3.0:
        return "Low (structured data)"
    elif entropy < 5.0:
        return "Medium (mixed content)"
    elif entropy < 7.0:
        return "High (random-like)"
    else:
        return "Very high (highly random)"
