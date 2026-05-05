"""
entropy_calculator.py — Calculate Shannon entropy for files.
"""

from __future__ import annotations
import math
import os
from collections import Counter

def calculate_entropy(file_path: str, sample_size: int = None) -> float:
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
        with open(file_path, 'rb') as f:
            if sample_size and file_size > sample_size:
                # Sample evenly distributed chunks
                chunk_size = min(8192, sample_size // 10)
                data = b''
                step = file_size // 10
                for i in range(0, file_size, step):
                    f.seek(i)
                    data += f.read(chunk_size)
                    if len(data) >= sample_size:
                        data = data[:sample_size]
                        break
            else:
                data = f.read()
        
        if not data:
            return 0.0

        # Count byte frequencies
        byte_counts = Counter(data)
        total_bytes = len(data)

        # Calculate entropy
        entropy = 0.0
        for count in byte_counts.values():
            probability = count / total_bytes
            entropy -= probability * math.log2(probability)

        return entropy

    except (OSError, IOError):
        return 0.0

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