# FileForge

[![Python CI](https://github.com/Yeongwonhan-Jeolmang/FileForge/actions/workflows/python-ci.yml/badge.svg?branch=main)](https://github.com/Yeongwonhan-Jeolmang/FileForge/actions/workflows/python-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Issues](https://img.shields.io/github/issues/Yeongwonhan-Jeolmang/FileForge)](https://github.com/Yeongwonhan-Jeolmang/FileForge/issues)

FileForge is a cross-platform desktop application for inspecting, editing, and validating file metadata, attributes, and content information.

Built on PyQt5, FileForge offers fast access to file timestamps, permissions, hashes, audio tags, digital signatures, string extraction, and advanced file utilities.

## Features

- Inspect file metadata, file type details, timestamps, permissions, flags, and extended attributes
- Rename, move, copy, and change extensions with path preview support
- Edit modified, accessed, and created timestamps independently
- Manage permissions with visual controls and octal mode values
- Compute MD5, SHA-1, and SHA-256 hashes with copy/verify support
- Read and write audio metadata tags for supported audio files
- Batch rename files using literal replacements or regular expressions
- Preview binary content with hex dumps, string extraction, entropy analysis, and comparison
- View Authenticode and PGP signature details for signed files
- Keep recent files available for quick reopening

## Installation

### Requirements

- Python 3.8 or later
- PyQt5

### Optional dependencies

The repository includes optional packages for richer metadata support:

- `Pillow` — image metadata and EXIF support
- `mutagen` — audio metadata editing
- `PyPDF2` — PDF metadata support
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

## Supported Platforms

- Windows
- macOS
- Linux

> Note: Extended attributes are only available on Linux/macOS. On Windows, permission editing is limited to the read-only attribute.

## Application Overview

FileForge organizes functionality into dedicated tabs for common file tasks:

- **Overview** — metadata, timestamps, permissions, MIME type, and embedded EXIF/audio metadata
- **Rename / Move** — rename, move, copy, extension changes, and hidden file toggles
- **Timestamps** — inspect and edit modified, accessed, and created times
- **Permissions** — visual permission matrix, owner/group/other bits, and preset modes
- **Hashes** — compute and verify MD5, SHA-1, and SHA-256
- **Audio Tags** — edit ID3/Vorbis audio tags and save changes
- **Batch Rename** — preview batch rename operations, including regex and case conversion
- **Advanced** — hex preview, truncate file contents, metadata inspection, and extended attributes
- **Signatures** — view digital signature and certificate details
- **Strings** — extract printable strings and filter results

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
- `modules/entropy_calculator.py` — entropy calculation utilities
- `modules/file_watcher.py` — file change monitoring
- `modules/settings_dialog.py` — settings dialog
- `modules/signature_inspector.py` — signature inspection utilities
- `modules/strings_extractor.py` — string extraction utilities
- `modules/theme.py` — UI styling constants
- `modules/widgets.py` — reusable controls and widgets

## Notes

- FileForge degrades gracefully when optional dependencies are unavailable.
- Optional packages unlock additional format and metadata capabilities.

## Contributing

- Report bugs and feature requests via GitHub issues.
- Review `CONTRIBUTING.md` before submitting pull requests.
- Follow `CODE_OF_CONDUCT.md` for community guidelines.

## License

This project is licensed under the MIT License. See `LICENSE` for details.