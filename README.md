# FileForge

[![Python CI](https://github.com/Yeongwonhan-Jeolmang/FileForge/actions/workflows/python-ci.yml/badge.svg)](https://github.com/Yeongwonhan-Jeolmang/FileForge/actions/workflows/python-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Issues](https://img.shields.io/github/issues/Yeongwonhan-Jeolmang/FileForge)](https://github.com/Yeongwonhan-Jeolmang/FileForge/issues)

FileForge is a cross-platform desktop application for exploring, editing, and validating file metadata, content metadata, and attributes.

Built with PyQt5, FileForge gives users fast access to file timestamps, permissions, hashes, audio tags, digital signatures, string extraction, and advanced file operations.

## Key Features

- Inspect file metadata, file type details, timestamps, permission bits, and extended attributes
- Rename, move, copy, and change extensions with file preview support
- Edit timestamps precisely and apply modified/accessed time updates
- Manage permissions visually, including octal mode and platform-specific handling
- Compute MD5, SHA-1, and SHA-256 hashes with easy verification and copy support
- Edit audio metadata tags for supported audio formats
- Batch rename using plain-text replacements or regular expressions
- Inspect binary data with a hex preview, string extraction, entropy analysis, and file comparison
- Display Authenticode/PGP signature details and certificate validity for signed files
- Support recent file history for quick reopen and workflow continuity

## User Interface Overview

FileForge organizes functionality into the following main tabs:

1. **Overview**
   - File identity, size, MIME type, kind, timestamps, permissions, flags, and metadata
   - Image EXIF metadata and audio tag previews when available
   - Extended attribute display on supported platforms

2. **Rename / Move**
   - Rename files within the same directory or move them to a new location
   - Change file extensions and toggle file hidden status
   - Copy files to a selected destination path

3. **Timestamps**
   - View and edit modified, accessed, and created timestamps
   - Apply timestamps independently or together
   - Use quick "touch" support to set timestamps to the current time

4. **Permissions**
   - Visual permission matrix for owner, group, and others
   - Toggle read/write/execute bits and apply octal permission values
   - Built-in presets such as `644`, `755`, `600`, `777`, and `400`
   - Windows support for read-only attribute handling

5. **Hashes**
   - Compute MD5, SHA-1, and SHA-256 hashes
   - Copy hash values to clipboard and verify pasted hashes

6. **Audio Tags**
   - Edit common ID3/Vorbis tags including title, artist, album, genre, year, composer, and comment
   - Save updated audio tags or remove tags from a supported file

7. **Batch Rename**
   - Create batch rename lists from selected files or entire folders
   - Preview rename results before applying changes
   - Use both literal replacements and regular expressions
   - Case conversion and whitespace normalization options

8. **Advanced**
   - Truncate file contents to a specified length or zero file contents
   - View a hex dump of the first 512 bytes
   - Inspect extended attributes and symlink targets
   - Browse EXIF/image metadata for supported files

9. **Signatures**
   - Display digital signature details for signed executable files
   - Verify Authenticode and PGP signature validity and view certificate information

10. **Strings**
    - Extract printable strings from binary files
    - Configure minimum string length and encoding
    - Filter and search extracted strings directly in the UI

## Installation

### Requirements

- Python 3.8 or later
- PyQt5

Optional packages for enhanced support:

- `Pillow` — image metadata and EXIF support
- `mutagen` — audio metadata reading and writing

### Install dependencies

```powershell
python -m pip install PyQt5
python -m pip install -r requirements.txt
```

### Launching FileForge

From the repository root:

```powershell
python main.py
```

## Supported Platforms

- Windows
- macOS
- Linux

> Note: Extended attributes are only available on Linux/macOS. On Windows, permission editing is limited to the read-only attribute.

## Repository Structure

- `main.py` — Application entry point
- `modules/main_window.py` — Main window, menu, sidebar, and tab coordination
- `modules/file_info.py` — File metadata extraction and classification
- `modules/file_ops.py` — File operations, timestamp editing, permissions, hashing, audio tag writing, and batch rename
- `modules/sidebar.py` — Recent file selector and sidebar navigation
- `modules/tab_overview.py` — Overview metadata display
- `modules/tab_rename.py` — Rename/move/copy/visibility controls
- `modules/tab_timestamps.py` — Timestamp editing UI
- `modules/tab_permissions.py` — Permissions editor UI
- `modules/tab_hashes.py` — Hash computation and verification UI
- `modules/tab_audio.py` — Audio tag editing UI
- `modules/tab_batch.py` — Batch rename UI
- `modules/tab_advanced.py` — Advanced file operations and metadata viewers
- `modules/tab_signatures.py` — Digital signature inspection UI
- `modules/tab_strings.py` — String extraction and display UI
- `modules/comparison_dialog.py` — File comparison dialog
- `modules/entropy_calculator.py` — File entropy calculation utilities
- `modules/file_watcher.py` — File change monitoring
- `modules/settings_dialog.py` — Application settings dialog
- `modules/signature_inspector.py` — Digital signature inspection utilities
- `modules/strings_extractor.py` — String extraction utilities
- `modules/theme.py` — UI styling constants
- `modules/widgets.py` — Reusable custom widgets and controls

## Notes

- FileForge degrades gracefully when optional dependencies are missing.
- Use `Pillow` for richer image metadata support.
- Use `mutagen` for audio metadata editing.

## Community

- Report bugs and feature requests using the GitHub issue templates.
- Review `CONTRIBUTING.md` before submitting pull requests.
- Follow `CODE_OF_CONDUCT.md` for community behavior and collaboration.

## License

This project is released under the MIT License. See the `LICENSE` file for details.
