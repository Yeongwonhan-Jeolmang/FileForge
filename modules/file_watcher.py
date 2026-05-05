"""
file_watcher.py — Watch files for changes and auto-refresh.
"""

from __future__ import annotations
from PyQt5.QtCore import QFileSystemWatcher, QObject, pyqtSignal

class FileWatcher(QObject):
    file_changed = pyqtSignal(str) # Emitted with file path when file changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._current_file: str | None = None

    def watch_file(self, file_path: str):
        """Start watching a specific file. Stops watching previous file if any."""
        if self._current_file:
            self._watcher.removePath(self._current_file)

        self._current_file = file_path
        if file_path:
            self._watcher.addPath(file_path)

    def stop_watching(self):
        """Stop watching the current file."""
        if self._current_file:
            self._watcher.removePath(self._current_file)
            self._current_file = None

    def _on_file_changed(self, path: str):
        """Handle file change notif"""
        # QFileSystemWatcher may emit multiple signals for one change
        # We emit our signal and let the main window handle it
        if path == self._current_file:
            self.file_changed.emit(path)

    def get_current_file(self) -> str | None:
        """Get the currently watched file path."""
        return self._current_file