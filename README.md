# FileForge

[![Python CI](https://github.com/Yeongwonhan-Jeolmang/FileForge/actions/workflows/python-ci.yml/badge.svg?branch=main)](https://github.com/Yeongwonhan-Jeolmang/FileForge/actions/workflows/python-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Issues](https://img.shields.io/github/issues/Yeongwonhan-Jeolmang/FileForge)](https://github.com/Yeongwonhan-Jeolmang/FileForge/issues)

FileForge is a cross-platform desktop application for inspecting, editing, and validating file metadata, attributes, and content information.

Built on PyQt5, FileForge offers fast access to file timestamps, permissions, hashes, audio tags, digital signatures, string extraction, and advanced file utilities.

## Features

- Inspect file metadata, file type details, timestamps, permissions, flags, and extended attributes
- **Content-based type detection** (magic bytes) with a warning when the extension doesn't match the content
- Rename, move, copy, and change extensions with validation and overwrite protection
- Edit modified and accessed timestamps (and creation time on Windows)
- Manage permissions with visual controls and octal mode values
- Compute MD5, SHA-1, SHA-256, SHA-512 and BLAKE2 hashes in parallel, with progress, cancel, copy and auto-detecting verify
- Read and write audio metadata tags for supported audio files
- Batch rename with literal or regex find/replace, `{n}` numbering and other tokens, case styles, live preview, conflict detection and undo
- Paged hex viewer, string extraction (ASCII / UTF-8 / UTF-16 / Latin-1), Shannon entropy with a per-region entropy graph, and file/folder comparison with coloured diffs
- Folder statistics and a fast duplicate finder (size → partial hash → full hash)
- Integrity snapshots to detect added, removed or modified files
- View Authenticode (Windows), Apple codesign (macOS) and PGP/GPG signature details
- Recent files remembered between sessions, drag & drop (multiple files go straight to Batch)
- Dark and light themes with adjustable font size

## Installation

### Requirements

- Python 3.8 or later
- PyQt5

### Optional dependencies

The repository includes optional packages for richer metadata support:

- `Pillow` — image metadata and EXIF support
- `mutagen` — audio metadata editing
- `pypdf` — PDF metadata support (the older `PyPDF2` is still used if that's what is installed)
- `python-docx` — Word document metadata support
- `python-pptx` — PowerPoint metadata support
- `openpyxl` — Excel metadata support
- `py7zr` — 7z archive support
- `pymediainfo` — multimedia metadata support

### Install dependencies

For local development and full feature support:

```powershell
python -m pip install -r requirements.txt
```

To install the package from this repository:

```powershell
python -m pip install .
```

### Launch FileForge

From the repository root:

```powershell
python main.py
```

Or, after installing the package:

```powershell
fileforge
```

You can pass a file or folder to open it straight away:

```powershell
python main.py path/to/file.jpg
python main.py path/to/folder
```

### Run the tests

```powershell
python -m pip install pytest
python -m pytest -q
```

The GUI smoke test uses Qt's `offscreen` platform, so it also runs on machines without a display.

## Supported Platforms

- Windows
- macOS
- Linux

> Note: Extended attributes are only available on Linux/macOS. On Windows, permission editing is limited to the read-only attribute.

## Application Overview

FileForge organizes functionality into dedicated tabs for common file tasks:

- **Overview** — metadata, timestamps, permissions, MIME type, detected content type, entropy graph, and embedded EXIF/audio/video/document metadata
- **Rename / Move** — rename, move, copy, extension changes, and hidden file toggles
- **Timestamps** — inspect and edit modified, accessed, and created times
- **Permissions** — visual permission matrix, owner/group/other bits, and preset modes
- **Hashes** — compute and verify MD5, SHA-1, SHA-256, SHA-512 and BLAKE2
- **Audio Tags** — edit ID3/Vorbis audio tags and save changes
- **Batch Rename** — live preview, regex, numbering tokens, case conversion, conflict detection and undo
- **Advanced** — paged hex viewer, truncate file contents, EXIF inspection, and extended attributes
- **Signatures** — view digital signature and certificate details
- **Strings** — extract printable strings, filter with regex, export results
- **Preview** — image, text, document and archive previews; export a full JSON metadata report
- **Folder** — folder statistics by type/extension, largest and newest files, duplicate finder
- **Integrity** — create and verify SHA-256 snapshots of a file or folder

## Keyboard Shortcuts

| Action | Shortcut |
| --- | --- |
| Open file / folder | `Ctrl+O` / `Ctrl+Shift+O` |
| Reload / close file | `F5` / `Ctrl+W` |
| Switch main tabs | `Ctrl+1` … `Ctrl+7` |
| Copy path / reveal in file manager | `Ctrl+Shift+P` / `Ctrl+Shift+R` |
| Filter sidebar / toggle sidebar | `Ctrl+F` / `Ctrl+B` |
| Compare files | `Ctrl+Shift+C` |
| Settings | `Ctrl+,` |

## Settings

Settings are available under **Tools → Settings**: auto-refresh on external changes, default hash algorithms, automatic hashing on open, remembering recent files, showing hidden files, theme (Dark / Light — applied after restart) and font size.

Logs are written to the per-user application data folder (**Help → Open Log Folder**) instead of the current directory.

## Repository Structure

- `main.py` — application entry point
- `modules/main_window.py` — main window and tab coordination
- `modules/file_info.py` — file metadata extraction and classification
- `modules/file_ops.py` — file operations, timestamps, permissions, hashing, and tag editing
- `modules/sidebar.py` — recent file list and sidebar navigation
- `modules/tab_overview.py` — overview metadata display
- `modules/tab_rename.py` — rename/move/copy UI
- `modules/tab_timestamps.py` — timestamp editing UI
- `modules/tab_permissions.py` — permission editor UI
- `modules/tab_hashes.py` — hash computation UI
- `modules/tab_audio.py` — audio tag editor UI
- `modules/tab_batch.py` — batch rename UI
- `modules/tab_advanced.py` — advanced file utilities and viewers
- `modules/tab_signatures.py` — signature inspection UI
- `modules/tab_strings.py` — string extraction UI
- `modules/comparison_dialog.py` — file comparison dialog
- `modules/magic_sniffer.py` — content type detection from magic bytes
- `modules/metadata_cache.py` — bounded caches keyed on file size and modification time
- `modules/folder_tools.py` / `modules/tab_folder_analysis.py` — folder statistics and duplicate finder
- `modules/integrity_tools.py` / `modules/tab_integrity.py` — integrity snapshots
- `modules/archive_tools.py` / `modules/tab_preview.py` — archive listing and previews
- `modules/entropy_calculator.py` — entropy calculation utilities
- `modules/file_watcher.py` — file change monitoring
- `modules/settings_dialog.py` — settings dialog
- `modules/signature_inspector.py` — signature inspection utilities
- `modules/strings_extractor.py` — string extraction utilities
- `modules/theme.py` — dark/light palettes and the application stylesheet
- `modules/widgets.py` — reusable controls and widgets (cards, banners, entropy graph, empty states)
- `tests/` — pytest suite (core logic + headless GUI smoke test)

## Notes

- FileForge degrades gracefully when optional dependencies are unavailable.
- Optional packages unlock additional format and metadata capabilities.

## Contributing

- Report bugs and feature requests via GitHub issues.
- Review `CONTRIBUTING.md` before submitting pull requests.
- Follow `CODE_OF_CONDUCT.md` for community guidelines.

## License

This project is licensed under the MIT License. See `LICENSE` for details.