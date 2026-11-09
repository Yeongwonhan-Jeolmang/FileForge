"""
file_watcher.py — Watch files for changes and auto-refresh.
"""

from __future__ import annotations
import os
from PyQt5.QtCore import QFileSystemWatcher, QObject, pyqtSignal, QTimer


class FileWatcher(QObject):
    file_changed = pyqtSignal(str)  # Emitted with file path when file changes

    DEBOUNCE_MS = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._current_file: str | None = None

        # QFileSystemWatcher fires several times for a single save (truncate,
        # write, close…). Collapse a burst into one notification.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self.DEBOUNCE_MS)
        self._debounce.timeout.connect(self._emit_change)

    def watch_file(self, file_path: str):
        """Start watching a specific file. Stops watching previous file if any."""
        if self._current_file and self._current_file in self._watcher.files():
            self._watcher.removePath(self._current_file)

        self._current_file = file_path
        if file_path and os.path.exists(file_path):
            self._watcher.addPath(file_path)

    def stop_watching(self):
        """Stop watching the current file."""
        self._debounce.stop()
        if self._current_file:
            if self._current_file in self._watcher.files():
                self._watcher.removePath(self._current_file)
            self._current_file = None

    def _on_file_changed(self, path: str):
        """Handle file change notif"""
        if path != self._current_file:
            return
        # Editors that save atomically (write temp file + rename over the original)
        # make the watcher drop the path. Re-arm it if the file is back.
        if path not in self._watcher.files() and os.path.exists(path):
            self._watcher.addPath(path)
        self._debounce.start()

    def _emit_change(self):
        if self._current_file:
            if self._current_file not in self._watcher.files() and os.path.exists(
                self._current_file
            ):
                self._watcher.addPath(self._current_file)
            self.file_changed.emit(self._current_file)

    def get_current_file(self) -> str | None:
        """Get the currently watched file path."""
        return self._current_file
