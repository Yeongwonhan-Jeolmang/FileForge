"""
Core (non-GUI) tests for FileForge.

Run with:  python -m pytest -q
"""

import hashlib
import os
import re
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.file_info import (
    human_size,
    compute_hashes,
    read_file_info,
    HashCancelled,
    classify_path,
)
from modules.magic_sniffer import sniff_bytes, extension_mismatch
from modules.strings_extractor import (
    extract_strings_streaming,
    extract_strings,
    _build_pattern,
)
from modules.entropy_calculator import calculate_entropy, entropy_profile
from modules import file_ops
from modules.folder_tools import find_duplicates, scan_folder
from modules.integrity_tools import create_snapshot, verify_snapshot
from modules.metadata_cache import MetadataCache
from modules.archive_tools import list_archive_contents


# ── file_info ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "n, expected",
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1536, "1.50 KB"),
        (5 * 1024**3, "5.00 GB"),
    ],
)
def test_human_size_includes_unit(n, expected):
    assert human_size(n) == expected


def test_compute_hashes_matches_hashlib(tmp_path):
    data = os.urandom(5 * 1024 * 1024 + 123)  # > 4 chunks → parallel path
    f = tmp_path / "blob.bin"
    f.write_bytes(data)
    result = compute_hashes(str(f), ["md5", "sha1", "sha256", "sha512", "blake2"])
    assert result["md5"] == hashlib.md5(data).hexdigest()
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["blake2"] == hashlib.blake2b(data).hexdigest()


def test_compute_hashes_cancel(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(os.urandom(3 * 1024 * 1024))
    with pytest.raises(HashCancelled):
        compute_hashes(str(f), ["sha256"], cancel_cb=lambda: True)


def test_progress_is_throttled(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(b"\0" * (20 * 1024 * 1024))
    calls = []
    compute_hashes(str(f), ["md5"], progress_cb=lambda d, t: calls.append(d))
    assert calls[-1] == 20 * 1024 * 1024
    assert len(calls) <= 102


def test_read_file_info_detects_renamed_png(tmp_path):
    f = tmp_path / "picture.txt"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 64)
    info = read_file_info(str(f))
    assert info.detected_type == "PNG image"
    assert info.extension_mismatch is True


def test_classify_path():
    assert classify_path("a.JPG") == "image"
    assert classify_path("a.docx") == "document"
    assert classify_path("a.tar.gz") == "archive"
    assert classify_path("a.exe") == "executable"


# ── magic sniffer ───────────────────────────────────────────────────────────


def test_sniff_known_signatures():
    assert sniff_bytes(b"%PDF-1.7 ...").description == "PDF document"
    assert sniff_bytes(b"RIFF\0\0\0\0WAVEfmt ").description == "WAV audio"
    assert sniff_bytes(b"\0\0\0\x18ftypisom").description == "MPEG-4 video"
    assert sniff_bytes(b"PK\x03\x04rest").kind == "archive"


def test_short_magic_does_not_misfire_on_text():
    # "BM" / "MZ" are BMP / PE magics but also ordinary text
    assert sniff_bytes(b"BMW service report, 2024").description == "Plain text"
    assert sniff_bytes(b"MZ is a text file").description == "Plain text"


def test_zip_based_office_is_not_a_mismatch():
    assert not extension_mismatch(sniff_bytes(b"PK\x03\x04"), ".docx")
    assert extension_mismatch(sniff_bytes(b"%PDF-1.4"), ".jpg")


# ── strings extractor ───────────────────────────────────────────────────────


@pytest.mark.parametrize("encoding", ["ascii", "utf-8", "latin-1", "utf-16"])
def test_streaming_matches_whole_file_scan(tmp_path, encoding):
    blob = (
        os.urandom(300_000)
        + "unicode ü 日本 text".encode("utf-8") * 20
        + "wide".encode("utf-16-le") * 30
    )
    f = tmp_path / "r.bin"
    f.write_bytes(blob)
    codec = {"utf-16": "utf-16-le"}.get(encoding, encoding)
    pattern = _build_pattern(encoding, 4)
    whole = [
        (m.start(), m.group().decode(codec, errors="ignore"))
        for m in pattern.finditer(blob)
    ]
    whole = [w for w in whole if len(w[1]) >= 4]
    for chunk in (513, 4096, 1_000_000):
        assert (
            list(extract_strings_streaming(str(f), 4, encoding, chunk_size=chunk))
            == whole
        )


def test_utf8_pattern_compiles_and_finds_text(tmp_path):
    f = tmp_path / "u.bin"
    f.write_bytes(b"\0\0" + "héllo wörld".encode("utf-8") + b"\0")
    assert extract_strings(str(f), 4, "utf-8") == [(2, "héllo wörld")]


def test_extract_strings_max_results(tmp_path):
    f = tmp_path / "m.bin"
    f.write_bytes(b"abcdef\0" * 1000)
    assert len(extract_strings(str(f), 4, "ascii", max_results=10)) == 10


# ── entropy ─────────────────────────────────────────────────────────────────


def test_entropy_bounds_and_profile(tmp_path):
    f = tmp_path / "e.bin"
    f.write_bytes(b"A" * 400_000 + os.urandom(400_000))
    assert 3.5 < calculate_entropy(str(f)) < 5.0
    prof = entropy_profile(str(f), blocks=16)
    assert len(prof) == 16
    assert prof[0] < 0.1 and prof[-1] > 7.5


def test_entropy_cache_invalidates_on_change(tmp_path):
    f = tmp_path / "c.bin"
    f.write_bytes(b"A" * 10_000)
    assert calculate_entropy(str(f)) == 0.0
    f.write_bytes(os.urandom(10_000) + b"x")  # size change → new signature
    assert calculate_entropy(str(f)) > 7.0


def test_metadata_cache_is_bounded():
    cache = MetadataCache(ttl_seconds=60, max_entries=3)
    for i in range(10):
        cache.set(str(i), i)
    assert len(cache) == 3 and cache.get("9") == 9 and cache.get("0") is None


# ── file_ops ────────────────────────────────────────────────────────────────


def test_batch_empty_pattern_is_noop():
    assert file_ops.batch_rename_preview(["/x/a.txt"], "", "Z") == [("a.txt", "a.txt")]


def test_batch_swap_and_conflicts(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("A")
    b.write_text("B")
    results = file_ops.batch_rename_to([str(a), str(b)], ["b.txt", "a.txt"])
    assert all(ok for _, ok, _, _ in results)
    assert a.read_text() == "B" and b.read_text() == "A"

    problems = file_ops.batch_rename_conflicts([str(a), str(b)], ["z.txt", "z.txt"])
    assert set(problems) == {0, 1}


def test_validate_filename():
    assert file_ops.validate_filename("ok.txt") is None
    assert file_ops.validate_filename("a/b") is not None
    assert file_ops.validate_filename("") is not None


def test_copy_and_move_refuse_overwrite(tmp_path):
    src, dst = tmp_path / "s.txt", tmp_path / "d.txt"
    src.write_text("s")
    dst.write_text("d")
    assert file_ops.copy_file(str(src), str(dst))[0] is False
    assert file_ops.copy_file(str(src), str(dst), overwrite=True)[0] is True
    assert dst.read_text() == "s"


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permissions")
def test_octal_permissions_accept_all_forms(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text("x")
    for value, mode in (("0644", 0o644), ("755", 0o755), ("0o600", 0o600)):
        ok, _ = file_ops.set_permissions_octal(str(f), value)
        assert ok and (os.stat(f).st_mode & 0o777) == mode


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="dot-file hiding is POSIX only"
)
def test_hidden_target_path(tmp_path):
    f = tmp_path / "h.txt"
    f.write_text("x")
    target = file_ops.hidden_target_path(str(f), True)
    assert file_ops.set_hidden(str(f), True)[0]
    assert os.path.exists(target) and Path(target).name == ".h.txt"


# ── folder / integrity / archives ───────────────────────────────────────────


def test_find_duplicates_prefilter_and_hardlinks(tmp_path):
    data = os.urandom(200_000)
    (tmp_path / "a.bin").write_bytes(data)
    (tmp_path / "b.bin").write_bytes(data)
    (tmp_path / "c.bin").write_bytes(
        data[:-1] + b"!"
    )  # same size + prefix, different tail
    if hasattr(os, "link"):
        os.link(tmp_path / "a.bin", tmp_path / "hard.bin")
    groups = find_duplicates(str(tmp_path))
    assert len(groups) == 1
    assert {Path(p).name for p in groups[0]["files"]} <= {"a.bin", "b.bin", "hard.bin"}
    assert "c.bin" not in {Path(p).name for p in groups[0]["files"]}


def test_scan_folder_summary(tmp_path):
    (tmp_path / "x.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "y.jpg").write_bytes(b"\xff\xd8\xff" + b"0" * 100)
    s = scan_folder(str(tmp_path))
    assert s["total_files"] == 2
    assert s["type_counts"] == {"text": 1, "image": 1}
    assert re.match(r"\d{4}-\d{2}-\d{2}", s["recent_files"][0]["modified_str"])


def test_snapshot_roundtrip(tmp_path):
    (tmp_path / "keep.txt").write_text("same")
    (tmp_path / "edit.txt").write_text("before")
    snap = create_snapshot(str(tmp_path))
    (tmp_path / "edit.txt").write_text("after!!")
    (tmp_path / "new.txt").write_text("n")
    r = verify_snapshot(snap)
    assert r["unchanged"] == ["keep.txt"]
    assert [c["path"] for c in r["changed"]] == ["edit.txt"]
    assert r["extra"] == ["new.txt"]


def test_archive_listing_limit(tmp_path):
    z = tmp_path / "t.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for i in range(50):
            zf.writestr(f"f{i}.txt", "x" * i)
    rows = list_archive_contents(str(z), limit=10)
    assert len(rows) == 10 and rows[0]["name"] == "f0.txt"
