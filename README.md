# FileForge

FileForge is an advanced desktop application for inspecting and editing file metadata, attributes, and content metadata on Windows, macOS, and Linux.

## Features

- Open any file and inspect rich metadata at a glance
- Rename, move, copy, change extension, and toggle hidden status
- Edit file timestamps precisely with calendar controls
- Manage file permissions visually with bit toggles and octal mode
- Compute MD5, SHA-1, and SHA-256 hashes with progress feedback
- Verify hashes against pasted values
- Edit audio metadata tags for supported audio formats
- Batch rename files using plain-text or regular expressions
- Inspect file content with a hex preview of the first 512 bytes
- View symlink targets, EXIF/image metadata, and extended attributes
- Recent files sidebar for quick reopen

## User Interface

FileForge is built with PyQt5 and organizes functionality into the following tabs:

1. **Overview**
   - File identity, size, MIME type, kind, timestamps, permissions, and flags
   - Displays image metadata and EXIF data when available
   - Displays audio metadata and embedded tags when available
   - Shows extended attributes (xattr) on supported platforms

2. **Rename / Move**
   - Rename files within the same directory
   - Change file extension
   - Toggle hidden visibility
   - Move files to a destination directory
   - Copy files to a chosen destination path

3. **Timestamps**
   - Read current modified, accessed, and created timestamps
   - Set modified or accessed timestamps independently
   - Apply both timestamps together
   - Touch file to set both timestamps to the current time

4. **Permissions**
   - Visual permission matrix for owner/group/others
   - Edit read/write/execute bits via toggles
   - Apply permissions by octal string
   - Use built-in presets like `644`, `755`, `600`, `777`, and `400`
   - Windows support is limited to the read-only attribute

5. **Hashes**
   - Compute MD5, SHA-1, and SHA-256 hashes
   - Copy hash values to clipboard
   - Verify pasted hash values against computed values

6. **Audio Tags**
   - Edit common ID3/Vorbis tags such as title, artist, album, genre, year, composer, and comment
   - Save new audio tags or delete all tags from the file
   - Only enabled for recognized audio files

7. **Batch Rename**
   - Create a file list from selected files or an entire folder
   - Preview filename changes before applying them
   - Use regular expressions or literal find-and-replace
   - Optionally uppercase, lowercase, or strip whitespace from results

8. **Advanced**
   - Truncate file contents to a specific byte length
   - Zero file contents to 0 bytes
   - View a hex dump of the first 512 bytes
   - Inspect extended attributes
   - Display symlink target information
   - Browse EXIF/image metadata for image files

## Installation

### Requirements

- Python 3.8+
- PyQt5

Optional features:

- `Pillow` for image metadata and EXIF support
- `mutagen` for audio metadata reading and writing

### Install dependencies

Install the core dependency:

```powershell
python -m pip install PyQt5
```

Install all recommended dependencies from `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

If you only need the core file property manager, `PyQt5` is the only hard requirement.

## Running FileForge

From the repository root:

```powershell
python main.py
```

## Supported Platforms

- Windows
- macOS
- Linux

> NOTE: Extended attributes are only available on Linux/macOS. Windows permission editing is limited to read-only flag behavior.

## Project Structure

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
- `modules/theme.py` — UI styling constants
- `modules/widgets.py` — Reusable custom widgets and controls

## Notes

- FileForge attempts to degrade gracefully when optional dependencies are missing.
- Image metadata and EXIF support require `Pillow`.
- Audio metadata support requires `mutagen`.

## License

FileForge is released under the MIT License. See the `LICENSE` file for details.

## Credits

- Hana Eun-Seo: UI and Programming
- Florian van den Bersselaar: UI
- Simon Roberge: UI and Programming
- Anna Zieleman: Programming
