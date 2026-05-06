"""
main_window.py — Top-level QMainWindow: sidebar + tabbed editor area.
"""

from __future__ import annotations
import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
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
from modules.tab_folder_analysis import FolderAnalysisTab
from modules.tab_integrity    import IntegrityTab
from modules.tab_preview      import PreviewTab
from modules.settings_dialog  import SettingsDialog
from modules.file_watcher     import FileWatcher
from modules.tab_strings      import StringsTab
from modules.tab_signatures   import SignaturesTab
from modules.comparison_dialog import ComparisonDialog


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
        self.setAcceptDrops(True) # Enable drag and drop

        self._current_info: FileInfo | None = None
        self._loader_thread: QThread | None = None
        self._loader_worker: _Loader | None = None
        self._file_watcher = FileWatcher(self)
        self._file_watcher.file_changed.connect(self._on_file_changed_externally)

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

        self._tab_overview       = OverviewTab()
        self._tab_rename         = RenameTab()
        self._tab_timestamps     = TimestampsTab()
        self._tab_permissions    = PermissionsTab()
        self._tab_hashes         = HashesTab()
        self._tab_audio          = AudioTab()
        self._tab_batch          = BatchTab()
        self._tab_advanced       = AdvancedTab()
        self._tab_preview        = PreviewTab()
        self._tab_folder_analysis = FolderAnalysisTab()
        self._tab_integrity      = IntegrityTab()
        self._tab_strings        = StringsTab()
        self._tab_signatures     = SignaturesTab()

        # Metadata section with nested tabs
        self._metadata_tab = QWidget()
        metadata_layout = QVBoxLayout(self._metadata_tab)
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.setSpacing(0)
        self._metadata_tabs = QTabWidget()
        self._metadata_tabs.setTabPosition(QTabWidget.North)
        self._metadata_tabs.setMovable(False)
        self._metadata_tabs.setDocumentMode(True)
        self._metadata_tabs.tabBar().setElideMode(Qt.ElideNone)
        self._metadata_tabs.tabBar().setExpanding(True)
        self._metadata_tabs.tabBar().setUsesScrollButtons(False)
        self._metadata_tabs.addTab(self._tab_rename, "Rename / Move")
        self._metadata_tabs.addTab(self._tab_timestamps, "Timestamps")
        self._metadata_tabs.addTab(self._tab_permissions, "Permissions")
        metadata_layout.addWidget(self._metadata_tabs)

        # Analysis section with nested tabs
        self._analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(self._analysis_tab)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_layout.setSpacing(0)
        self._analysis_tabs = QTabWidget()
        self._analysis_tabs.setTabPosition(QTabWidget.North)
        self._analysis_tabs.setMovable(False)
        self._analysis_tabs.setDocumentMode(True)
        self._analysis_tabs.tabBar().setElideMode(Qt.ElideNone)
        self._analysis_tabs.tabBar().setExpanding(True)
        self._analysis_tabs.tabBar().setUsesScrollButtons(False)
        self._analysis_tabs.addTab(self._tab_hashes, "Hashes")
        self._analysis_tabs.addTab(self._tab_audio, "Audio Tags")
        self._analysis_tabs.addTab(self._tab_advanced, "Advanced")
        self._analysis_tabs.addTab(self._tab_strings, "Strings")
        self._analysis_tabs.addTab(self._tab_signatures, "Signatures")
        analysis_layout.addWidget(self._analysis_tabs)

        self._tabs.addTab(self._tab_overview, "Overview")
        self._tabs.addTab(self._metadata_tab, "Metadata")
        self._tabs.addTab(self._analysis_tab, "Analysis")
        self._tabs.addTab(self._tab_batch, "Batch")
        self._tabs.addTab(self._tab_preview, "Preview")
        self._tabs.addTab(self._tab_folder_analysis, "Folder")
        self._tabs.addTab(self._tab_integrity, "Integrity")

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

        open_folder_act = QAction("Open Folder…", self)
        open_folder_act.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_folder_act.triggered.connect(self._open_folder_dialog)
        file_menu.addAction(open_folder_act)

        reload_act = QAction("Reload", self)
        reload_act.setShortcut(QKeySequence("F5"))
        reload_act.triggered.connect(self._force_reload)
        file_menu.addAction(reload_act)

        close_act = QAction("Close File", self)
        close_act.setShortcut(QKeySequence("Ctrl+W"))
        close_act.triggered.connect(self._close_file)
        file_menu.addAction(close_act)

        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # View
        view_menu = mb.addMenu("View")
        for i, name in enumerate(["Overview", "Metadata", "Analysis", "Batch"]):
            act = QAction(name, self)
            act.setShortcut(QKeySequence(f"Ctrl+Shift+{i+1}"))
            act.triggered.connect(lambda checked, idx=i: self._tabs.setCurrentIndex(idx))
            view_menu.addAction(act)

        # Tools
        tools_menu = mb.addMenu("Tools")
        settings_act = QAction("Settings…", self)
        settings_act.setShortcut(QKeySequence("Ctrl+,"))
        settings_act.triggered.connect(self._show_settings)
        tools_menu.addAction(settings_act)

        compare_act = QAction("Compare Files…", self)
        compare_act.setShortcut(QKeySequence("Ctrl+Shift+C"))
        compare_act.triggered.connect(self._show_comparison)
        tools_menu.addAction(compare_act)

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

    def _open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self._sidebar.set_current_folder(folder)

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
        thread.finished.connect(self._cleanup_loader)

        self._loader_worker = worker
        self._loader_thread = thread
        thread.start()

    def _on_file_changed_externally(self, path: str):
        """Handle external file changes - auto-refresh if enabled."""
        settings = SettingsDialog()
        if settings.get_auto_refresh_enabled() and self._current_info and self._current_info.path == path:
            self.statusBar().showMessage("File changed externally - reloading…", 3000)
            self._reload_file(path)
        self._sidebar.add_recent(path)

    def _reload_file(self, path: str):
        """Reload after an in-place modification."""
        if path and os.path.exists(path):
            self._load_file(path)

    def _force_reload(self):
        if self._current_info:
            self._reload_file(self._current_info.path)

    def _close_file(self):
        self._current_info = None
        self._file_watcher.stop_watching()
        self._populate_tabs(None)
        self._update_status_for_closed()

    def _on_info_loaded(self, info: FileInfo):
        self._current_info = info
        self._file_watcher.watch_file(info.path)
        self._populate_tabs(info)
        self._update_status(info)

    def _cleanup_loader(self):
        if self._loader_worker is not None:
            self._loader_worker.deleteLater()
            self._loader_worker = None
        if self._loader_thread is not None:
            self._loader_thread.deleteLater()
            self._loader_thread = None

    def _populate_tabs(self, info: FileInfo):
        if info is None:
            self._tab_overview.clear()
            self._tab_rename.clear()
            self._tab_timestamps.clear()
            self._tab_permissions.clear()
            self._tab_hashes.clear()
            self._tab_audio.clear()
            self._tab_advanced.clear()
            self._tab_strings.clear()
            self._tab_signatures.clear()
            self._tab_preview.clear()
            self._tab_folder_analysis.clear()
            self._tab_integrity.clear()
            # BatchTab manages its own list; we don't force-clear it
        else:
            self._tab_overview.load(info)
            self._tab_rename.load(info)
            self._tab_timestamps.load(info)
            self._tab_permissions.load(info)
            self._tab_hashes.load(info)
            self._tab_audio.load(info)
            self._tab_advanced.load(info)
            self._tab_strings.load(info)
            self._tab_signatures.load(info)
            self._tab_preview.load(info)
            self._tab_folder_analysis.load(info)
            self._tab_integrity.load(info)
            # BatchTab manages its own list; we don't force-load it

    def _update_status(self, info: FileInfo):
        self._status_file.setText(info.path)
        self._status_kind.setText(info.kind.capitalize())
        self._status_size.setText(info.size_human)
        self.statusBar().showMessage("")
        self.setWindowTitle(f"FileForge — {info.name}")

    def _update_status_for_closed(self):
        self._status_file.setText("No file loaded")
        self._status_kind.setText("")
        self._status_size.setText("")
        self.statusBar().showMessage("")
        self.setWindowTitle("FileForge — File Properties Manager")

    # ── Helpers ────────────────────────────────────────────────────────

    def _show_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}", 5000)
        QMessageBox.critical(self, "FileForge Error", msg)

    def _show_about(self):
        QMessageBox.about(
            self, "About FileForge",
            "<b>FileForge v1.1</b><br>"
            "A comprehensive file properties and analysis manager.<br><br>"
            "<b>Core Features:</b><br>"
            "• Rich metadata inspection with entropy analysis<br>"
            "• File rename, move, copy operations<br>"
            "• Precise timestamp editing<br>"
            "• Visual permission editor<br>"
            "• Multiple hash algorithms (MD5, SHA-1, SHA-256, SHA-512, BLAKE2)<br>"
            "• Audio tag editing<br>"
            "• Batch rename with regex support<br><br>"
            "<b>Advanced Features:</b><br>"
            "• File entropy calculation and analysis<br>"
            "• String extraction from binary files<br>"
            "• Digital signature inspection (Authenticode, PGP/GPG)<br>"
            "• File comparison tool with diff modes<br>"
            "• Hex preview and binary analysis<br>"
            "• File watcher with auto-refresh<br>"
            "• Drag-and-drop file opening<br>"
            "• Customizable settings and keyboard shortcuts<br><br>"
            "<b>Supported Platforms:</b><br>"
            "Windows, macOS, Linux<br><br>"
            "<b>Credits:</b><br>"
            "Hana Eun-Seo, Florian van den Bersselaar,<br>"
            "Simon Roberge, Anna Zieleman"
        )

    def _show_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec_()

    def _show_comparison(self):
        dialog = ComparisonDialog(self)
        dialog.exec_()

    def closeEvent(self, event):
        # Clean up background threads
        if hasattr(self, '_load_thread') and self._load_thread.isRunning():
            self._load_thread.quit()
            self._load_thread.wait()
        event.accept()

    # ── Drag and Drop ───────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and len(urls) == 1:
                url = urls[0]
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if os.path.isfile(path):
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and len(urls) == 1:
            url = urls[0]
            if url.isLocalFile():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    self._load_file(path)
                    event.acceptProposedAction()
                    return
        event.ignore()