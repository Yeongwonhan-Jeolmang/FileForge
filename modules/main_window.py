"""
main_window.py — Top-level QMainWindow: sidebar + tabbed editor area.
"""

from __future__ import annotations
import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QTabWidget, QStatusBar, QAction, QMenuBar,
    QLabel, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont, QKeySequence

from modules.theme import STYLESHEET, ACCENT, BG_DARKEST, TEXT_SECONDARY, BORDER
from modules.file_info import read_file_info, FileInfo
from modules.sidebar import Sidebar
from modules.tab_overview     import OverviewTab
from modules.tab_rename       import RenameTab
from modules.tab_timestamps   import TimestampsTab
from modules.tab_permissions  import PermissionsTab
from modules.tab_hashes       import HashesTab
from modules.tab_audio        import AudioTab
from modules.tab_batch        import BatchTab
from modules.tab_advanced     import AdvancedTab


# ── Background loader ──────────────────────────────────────────────────────

class _Loader(QObject):
    done  = pyqtSignal(object)   # FileInfo
    error = pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self):
        try:
            info = read_file_info(self._path)
            self.done.emit(info)
        except Exception as e:
            self.error.emit(str(e))


# ── Main window ────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileForge — File Properties Manager")
        self.resize(1280, 820)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLESHEET)

        self._current_info: FileInfo | None = None
        self._loader_thread: QThread | None = None

        self._build_ui()
        self._build_menu()
        self._build_status_bar()

    # ── Build UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.file_selected.connect(self._load_file)

        # Content area
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.North)
        self._tabs.setMovable(False)
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setElideMode(Qt.ElideNone)
        self._tabs.tabBar().setExpanding(True)
        self._tabs.tabBar().setUsesScrollButtons(False)

        self._tab_overview    = OverviewTab()
        self._tab_rename      = RenameTab()
        self._tab_timestamps  = TimestampsTab()
        self._tab_permissions = PermissionsTab()
        self._tab_hashes      = HashesTab()
        self._tab_audio       = AudioTab()
        self._tab_batch       = BatchTab()
        self._tab_advanced    = AdvancedTab()

        self._tabs.addTab(self._tab_overview,    "Overview")
        self._tabs.addTab(self._tab_rename,      "Rename / Move")
        self._tabs.addTab(self._tab_timestamps,  "Timestamps")
        self._tabs.addTab(self._tab_permissions, "Permissions")
        self._tabs.addTab(self._tab_hashes,      "Hashes")
        self._tabs.addTab(self._tab_audio,       "Audio Tags")
        self._tabs.addTab(self._tab_batch,       "Batch Rename")
        self._tabs.addTab(self._tab_advanced,    "Advanced")

        # Wire file_changed signals → reload
        for tab in [self._tab_rename, self._tab_timestamps,
                    self._tab_permissions, self._tab_audio, self._tab_advanced]:
            tab.file_changed.connect(self._reload_file)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1020])
        splitter.setHandleWidth(2)

        root_layout.addWidget(splitter)

    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("File")
        open_act = QAction("Open File…", self)
        open_act.setShortcut(QKeySequence("Ctrl+O"))
        open_act.triggered.connect(self._open_dialog)
        file_menu.addAction(open_act)

        reload_act = QAction("Reload", self)
        reload_act.setShortcut(QKeySequence("F5"))
        reload_act.triggered.connect(self._force_reload)
        file_menu.addAction(reload_act)

        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # View
        view_menu = mb.addMenu("View")
        for i, name in enumerate(["Overview", "Rename/Move", "Timestamps",
                                   "Permissions", "Hashes", "Audio Tags",
                                   "Batch Rename", "Advanced"]):
            act = QAction(name, self)
            act.setShortcut(QKeySequence(f"Ctrl+{i+1}"))
            act.triggered.connect(lambda checked, idx=i: self._tabs.setCurrentIndex(idx))
            view_menu.addAction(act)

        # Help
        help_menu = mb.addMenu("Help")
        about_act = QAction("About FileForge", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_status_bar(self):
        sb = self.statusBar()
        self._status_file  = QLabel("No file loaded")
        self._status_file.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._status_size  = QLabel("")
        self._status_kind  = QLabel("")
        self._status_sep1  = QLabel("·")
        self._status_sep2  = QLabel("·")
        for w in [self._status_sep1, self._status_sep2]:
            w.setStyleSheet(f"color: {BORDER};")

        sb.addWidget(self._status_file)
        sb.addWidget(self._status_sep1)
        sb.addWidget(self._status_kind)
        sb.addWidget(self._status_sep2)
        sb.addWidget(self._status_size)
        sb.addPermanentWidget(QLabel("FileForge v1.0"))

    # ── File loading ───────────────────────────────────────────────────

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        if not os.path.isfile(path):
            self._show_error(f"Not a file or not found:\n{path}")
            return

        self.statusBar().showMessage(f"Loading  {path}…")
        self._current_info = None

        worker = _Loader(path)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_info_loaded)
        worker.done.connect(thread.quit)
        worker.error.connect(lambda e: self._show_error(e))
        worker.error.connect(thread.quit)
        self._loader_thread = thread
        thread.start()

        self._sidebar.add_recent(path)

    def _reload_file(self, path: str):
        """Reload after an in-place modification."""
        if path and os.path.exists(path):
            self._load_file(path)

    def _force_reload(self):
        if self._current_info:
            self._reload_file(self._current_info.path)

    def _on_info_loaded(self, info: FileInfo):
        self._current_info = info
        self._populate_tabs(info)
        self._update_status(info)

    def _populate_tabs(self, info: FileInfo):
        self._tab_overview.load(info)
        self._tab_rename.load(info)
        self._tab_timestamps.load(info)
        self._tab_permissions.load(info)
        self._tab_hashes.load(info)
        self._tab_audio.load(info)
        self._tab_advanced.load(info)
        # BatchTab manages its own list; we don't force-load it

    def _update_status(self, info: FileInfo):
        self._status_file.setText(info.path)
        self._status_kind.setText(info.kind.capitalize())
        self._status_size.setText(info.size_human)
        self.statusBar().showMessage("")
        self.setWindowTitle(f"FileForge — {info.name}")

    # ── Helpers ────────────────────────────────────────────────────────

    def _show_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}", 5000)
        QMessageBox.critical(self, "FileForge Error", msg)

    def _show_about(self):
        QMessageBox.about(
            self, "About FileForge",
            "<b>FileForge v1.0</b><br>"
            "A fully-featured file properties manager.<br><br>"
            "Features:<br>"
            "• Overview with rich metadata<br>"
            "• Rename, move, copy, change extension<br>"
            "• Precise timestamp editing<br>"
            "• Visual permission editor with presets<br>"
            "• MD5 / SHA-1 / SHA-256 hashing with verification<br>"
            "• Audio tag editing (mutagen)<br>"
            "• Batch rename with regex<br>"
            "• Hex preview, EXIF viewer, extended attributes<br>"
        )