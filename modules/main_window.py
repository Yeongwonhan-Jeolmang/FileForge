"""
main_window.py — Top-level QMainWindow: sidebar + tabbed editor area.
"""

from __future__ import annotations
import os
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QTabWidget, QStatusBar, QAction, QMenuBar, QMenu,
    QLabel, QFileDialog, QMessageBox, QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QSettings, QByteArray
from PyQt5.QtGui import QFont, QKeySequence

from modules import __version__
from modules.theme import (
    STYLESHEET, ACCENT, BG_DARKEST, TEXT_SECONDARY, TEXT_MUTED, BORDER, WARNING,
    build_stylesheet,
)
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
from modules.settings_dialog  import SettingsDialog, AppSettings
from modules.file_watcher     import FileWatcher
from modules.tab_strings      import StringsTab
from modules.tab_signatures   import SignaturesTab
from modules.comparison_dialog import ComparisonDialog
from modules.widgets import copy_to_clipboard, reveal_in_file_manager, open_with_default_app

logger = logging.getLogger(__name__)


# ── Background loader ──────────────────────────────────────────────────────

class _Loader(QObject):
    done  = pyqtSignal(int, object)   # request id, FileInfo
    error = pyqtSignal(int, str)

    def __init__(self, path: str, request_id: int):
        super().__init__()
        self._path = path
        self._request_id = request_id

    def run(self):
        try:
            info = read_file_info(self._path)
            self.done.emit(self._request_id, info)
        except Exception as e:
            logger.exception("Failed to read %s", self._path)
            self.error.emit(self._request_id, str(e))


# ── Main window ────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileForge — File Properties Manager")
        self.resize(1280, 820)
        self.setMinimumSize(900, 600)
        self._app_settings = AppSettings()
        self.setStyleSheet(build_stylesheet(self._app_settings.font_px()))
        self.setAcceptDrops(True) # Enable drag and drop

        self._current_info: FileInfo | None = None
        self._loader_thread: QThread | None = None
        self._loader_worker: _Loader | None = None
        self._request_id = 0
        # Every thread we start — and its worker — is kept here until the thread has
        # finished. Without a Python reference the worker would be garbage-collected
        # (taking its signal connections with it) and the QThread could be destroyed
        # while still running, which crashes Qt.
        self._live_threads: dict[QThread, _Loader] = {}

        self._file_watcher = FileWatcher(self)
        self._file_watcher.file_changed.connect(self._on_file_changed_externally)

        # Coalesce bursts of reload requests (our own writes + watcher events)
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(250)
        self._reload_timer.timeout.connect(self._do_pending_reload)
        self._pending_reload_path: str | None = None

        self._build_ui()
        self._build_menu()
        self._build_status_bar()
        self._restore_window_state()
        self._overview_show_recent()

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
        self._sidebar.folder_selected.connect(self._analyse_folder)

        # Content area
        self._tabs = self._make_tab_widget()

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
        self._metadata_tabs = self._make_tab_widget()
        self._metadata_tabs.addTab(self._tab_rename, "Rename / Move")
        self._metadata_tabs.addTab(self._tab_timestamps, "Timestamps")
        self._metadata_tabs.addTab(self._tab_permissions, "Permissions")
        metadata_layout.addWidget(self._metadata_tabs)

        # Analysis section with nested tabs
        self._analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(self._analysis_tab)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_layout.setSpacing(0)
        self._analysis_tabs = self._make_tab_widget()
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
        self._tabs.setTabToolTip(0, "Summary of the current file (Ctrl+1)")
        self._tabs.setTabToolTip(1, "Rename, timestamps and permissions (Ctrl+2)")
        self._tabs.setTabToolTip(2, "Hashes, tags, hex, strings and signatures (Ctrl+3)")
        self._tabs.setTabToolTip(3, "Rename many files at once (Ctrl+4)")
        self._tabs.setTabToolTip(4, "Content preview (Ctrl+5)")
        self._tabs.setTabToolTip(5, "Folder statistics and duplicate finder (Ctrl+6)")
        self._tabs.setTabToolTip(6, "Integrity snapshots (Ctrl+7)")

        # Leaf tabs that receive load()/clear(). Loading is lazy: only the visible
        # tab is populated immediately, the others when they are first shown.
        self._leaf_tabs = [
            self._tab_overview, self._tab_rename, self._tab_timestamps,
            self._tab_permissions, self._tab_hashes, self._tab_audio,
            self._tab_advanced, self._tab_strings, self._tab_signatures,
            self._tab_preview, self._tab_folder_analysis, self._tab_integrity,
        ]
        self._stale_tabs: set = set()

        for tw in (self._tabs, self._metadata_tabs, self._analysis_tabs):
            tw.currentChanged.connect(lambda _=None: self._load_visible_tab())

        # Wire file_changed signals → reload
        for tab in [self._tab_rename, self._tab_timestamps,
                    self._tab_permissions, self._tab_audio, self._tab_advanced]:
            tab.file_changed.connect(self._reload_file)

        # Cross-tab navigation
        self._tab_overview.open_requested.connect(self._open_dialog)
        self._tab_overview.file_requested.connect(self._load_file)
        self._tab_overview.navigate_requested.connect(self._navigate_to)
        self._tab_folder_analysis.file_open_requested.connect(self._load_file)
        self._tab_integrity.file_open_requested.connect(self._load_file)
        self._tab_batch.file_open_requested.connect(self._load_file)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(self._tabs)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setCollapsible(1, False)
        self._splitter.setSizes([280, 1000])
        self._splitter.setHandleWidth(1)

        root_layout.addWidget(self._splitter)

    @staticmethod
    def _make_tab_widget() -> QTabWidget:
        tw = QTabWidget()
        tw.setTabPosition(QTabWidget.North)
        tw.setMovable(False)
        tw.setDocumentMode(True)
        tw.tabBar().setElideMode(Qt.ElideNone)
        tw.tabBar().setExpanding(False)
        tw.tabBar().setUsesScrollButtons(True)
        return tw

    def _build_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        open_act = QAction("Open File…", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self._open_dialog)
        file_menu.addAction(open_act)

        open_folder_act = QAction("Open Folder…", self)
        open_folder_act.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_folder_act.triggered.connect(self._open_folder_dialog)
        file_menu.addAction(open_folder_act)

        self._recent_menu = file_menu.addMenu("Open Recent")
        self._recent_menu.aboutToShow.connect(self._populate_recent_menu)

        file_menu.addSeparator()
        reload_act = QAction("Reload", self)
        reload_act.setShortcut(QKeySequence("F5"))
        reload_act.triggered.connect(self._force_reload)
        file_menu.addAction(reload_act)

        close_act = QAction("Close File", self)
        close_act.setShortcut(QKeySequence("Ctrl+W"))
        close_act.triggered.connect(self._close_file)
        file_menu.addAction(close_act)

        file_menu.addSeparator()
        self._copy_path_act = QAction("Copy File Path", self)
        self._copy_path_act.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self._copy_path_act.triggered.connect(self._copy_current_path)
        file_menu.addAction(self._copy_path_act)

        self._reveal_act = QAction("Reveal in File Manager", self)
        self._reveal_act.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self._reveal_act.triggered.connect(self._reveal_current)
        file_menu.addAction(self._reveal_act)

        self._open_default_act = QAction("Open with Default App", self)
        self._open_default_act.triggered.connect(self._open_current_externally)
        file_menu.addAction(self._open_default_act)

        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # View
        view_menu = mb.addMenu("&View")
        for i in range(self._tabs.count()):
            name = self._tabs.tabText(i)
            act = QAction(name, self)
            # Ctrl+N is the conventional tab shortcut; keep the old Ctrl+Shift+N working too
            act.setShortcuts([QKeySequence(f"Ctrl+{i + 1}"), QKeySequence(f"Ctrl+Shift+{i + 1}")])
            act.triggered.connect(lambda checked, idx=i: self._tabs.setCurrentIndex(idx))
            view_menu.addAction(act)
        view_menu.addSeparator()
        toggle_sidebar = QAction("Toggle Sidebar", self)
        toggle_sidebar.setShortcut(QKeySequence("Ctrl+B"))
        toggle_sidebar.triggered.connect(lambda: self._sidebar.setVisible(not self._sidebar.isVisible()))
        view_menu.addAction(toggle_sidebar)
        focus_filter = QAction("Filter Files", self)
        focus_filter.setShortcut(QKeySequence("Ctrl+F"))
        focus_filter.triggered.connect(self._focus_filter)
        view_menu.addAction(focus_filter)

        # Tools
        tools_menu = mb.addMenu("&Tools")
        compare_act = QAction("Compare Files…", self)
        compare_act.setShortcut(QKeySequence("Ctrl+Shift+C"))
        compare_act.triggered.connect(self._show_comparison)
        tools_menu.addAction(compare_act)

        analyse_act = QAction("Analyse Folder…", self)
        analyse_act.triggered.connect(self._analyse_folder_dialog)
        tools_menu.addAction(analyse_act)

        tools_menu.addSeparator()
        settings_act = QAction("Settings…", self)
        settings_act.setShortcut(QKeySequence("Ctrl+,"))
        settings_act.setMenuRole(QAction.PreferencesRole)
        settings_act.triggered.connect(self._show_settings)
        tools_menu.addAction(settings_act)

        # Help
        help_menu = mb.addMenu("&Help")
        log_act = QAction("Open Log Folder", self)
        log_act.triggered.connect(self._open_log_folder)
        help_menu.addAction(log_act)
        about_act = QAction("About FileForge", self)
        about_act.setMenuRole(QAction.AboutRole)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

        self._update_file_actions()

    def _build_status_bar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self._status_file  = QLabel("No file loaded")
        self._status_file.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._status_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._status_size  = QLabel("")
        self._status_kind  = QLabel("")
        self._status_warn  = QLabel("")
        self._status_warn.setStyleSheet(f"color: {WARNING};")
        self._status_sep1  = QLabel("·")
        self._status_sep2  = QLabel("·")
        for w in [self._status_sep1, self._status_sep2]:
            w.setStyleSheet(f"color: {TEXT_MUTED};")

        sb.addWidget(self._status_file, 1)
        sb.addWidget(self._status_kind)
        sb.addWidget(self._status_sep1)
        sb.addWidget(self._status_size)
        sb.addWidget(self._status_sep2)
        sb.addWidget(self._status_warn)
        version = QLabel(f"FileForge v{__version__}")
        version.setStyleSheet(f"color: {TEXT_MUTED};")
        sb.addPermanentWidget(version)
        self._update_status_for_closed()

    # ── Public API ─────────────────────────────────────────────────────

    def open_file(self, path: str):
        self._load_file(path)

    def open_folder(self, folder: str):
        self._sidebar.set_current_folder(folder)
        self._analyse_folder(folder)

    # ── File loading ───────────────────────────────────────────────────

    def _open_dialog(self):
        start = os.path.dirname(self._current_info.path) if self._current_info else ""
        path, _ = QFileDialog.getOpenFileName(self, "Open File", start)
        if path:
            self._load_file(path)

    def _open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self._sidebar.set_current_folder(folder)

    def _load_file(self, path: str):
        if not os.path.isfile(path):
            if not os.path.exists(path):
                self._sidebar.remove_recent(path)
            self._show_error(f"Not a file or not found:\n{path}")
            return

        self._request_id += 1
        request_id = self._request_id
        self.statusBar().showMessage(f"Loading  {path}…")
        QApplication.setOverrideCursor(Qt.BusyCursor)

        worker = _Loader(path, request_id)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_info_loaded)
        worker.done.connect(thread.quit)
        worker.error.connect(self._on_load_error)
        worker.error.connect(thread.quit)
        # Each thread cleans up only *itself* — the old shared cleanup could
        # delete a newer, still-running thread when two loads overlapped.
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._forget_thread(t))

        self._live_threads[thread] = worker
        self._loader_worker = worker
        self._loader_thread = thread
        thread.start()

    def _forget_thread(self, thread: QThread):
        self._live_threads.pop(thread, None)
        if thread is self._loader_thread:
            self._loader_thread = None
            self._loader_worker = None
        thread.deleteLater()

    def _on_load_error(self, request_id: int, msg: str):
        QApplication.restoreOverrideCursor()
        if request_id != self._request_id:
            return
        self._show_error(msg)

    def _on_file_changed_externally(self, path: str):
        """Handle external file changes - auto-refresh if enabled."""
        if not (self._current_info and os.path.normcase(self._current_info.path) == os.path.normcase(path)):
            return
        if not os.path.exists(path):
            self.statusBar().showMessage("The current file was deleted or moved by another program.", 6000)
            return
        if self._app_settings.auto_refresh():
            self.statusBar().showMessage("File changed externally — reloading…", 3000)
            self._reload_file(path)
        else:
            self.statusBar().showMessage("File changed on disk — press F5 to reload.", 6000)

    def _reload_file(self, path: str):
        """Reload after an in-place modification (debounced)."""
        if path:
            self._pending_reload_path = path
            self._reload_timer.start()

    def _do_pending_reload(self):
        path = self._pending_reload_path
        self._pending_reload_path = None
        if path and os.path.exists(path):
            self._load_file(path)
        elif self._current_info and not os.path.exists(self._current_info.path):
            self._close_file()

    def _force_reload(self):
        if self._current_info:
            self._load_file(self._current_info.path)

    def _close_file(self):
        self._request_id += 1      # ignore any load still in flight
        self._current_info = None
        self._file_watcher.stop_watching()
        self._populate_tabs(None)
        self._update_status_for_closed()
        self._update_file_actions()
        self._overview_show_recent()

    def _on_info_loaded(self, request_id: int, info: FileInfo):
        QApplication.restoreOverrideCursor()
        if request_id != self._request_id:
            return   # a newer file was requested meanwhile — drop this stale result
        self._current_info = info
        self._file_watcher.watch_file(info.path)
        self._sidebar.add_recent(info.path)
        self._populate_tabs(info)
        self._update_status(info)
        self._update_file_actions()

    def _cleanup_loader(self):
        # Kept for backwards compatibility; per-thread cleanup now lives in _forget_thread
        pass

    def _populate_tabs(self, info: FileInfo):
        if info is None:
            self._stale_tabs.clear()
            for tab in self._leaf_tabs:
                tab.clear()
            # BatchTab manages its own list; we don't force-clear it
            return

        self._stale_tabs = set(self._leaf_tabs)
        if self._app_settings.auto_hash_on_load():
            self._ensure_loaded(self._tab_hashes)
        self._load_visible_tab()
        # BatchTab manages its own list; we don't force-load it

    def _visible_leaf(self):
        page = self._tabs.currentWidget()
        if page is self._metadata_tab:
            return self._metadata_tabs.currentWidget()
        if page is self._analysis_tab:
            return self._analysis_tabs.currentWidget()
        return page

    def _load_visible_tab(self):
        leaf = self._visible_leaf()
        if leaf is not None:
            self._ensure_loaded(leaf)

    def _ensure_loaded(self, tab):
        if tab in self._stale_tabs and self._current_info is not None:
            self._stale_tabs.discard(tab)
            try:
                tab.load(self._current_info)
            except Exception:
                logger.exception("Tab %s failed to load", type(tab).__name__)
                self.statusBar().showMessage(f"{type(tab).__name__} could not display this file.", 5000)

    def _navigate_to(self, name: str):
        """Jump to a tab by name (used by Overview quick actions)."""
        targets = {
            "hashes": (2, self._analysis_tabs, self._tab_hashes),
            "strings": (2, self._analysis_tabs, self._tab_strings),
            "advanced": (2, self._analysis_tabs, self._tab_advanced),
            "rename": (1, self._metadata_tabs, self._tab_rename),
            "timestamps": (1, self._metadata_tabs, self._tab_timestamps),
            "permissions": (1, self._metadata_tabs, self._tab_permissions),
            "preview": (4, None, None),
        }
        if name in targets:
            top, sub, widget = targets[name]
            if sub is not None:
                sub.setCurrentWidget(widget)
            self._tabs.setCurrentIndex(top)

    def _update_status(self, info: FileInfo):
        self._status_file.setText(info.path)
        self._status_file.setToolTip(info.path)
        self._status_kind.setText(info.kind.capitalize())
        self._status_size.setText(info.size_human)
        for w in (self._status_sep1, self._status_kind, self._status_size):
            w.setVisible(True)
        mismatch = info.extension_mismatch
        self._status_warn.setText(f"⚠ Content looks like {info.detected_type}" if mismatch else "")
        self._status_warn.setVisible(mismatch)
        self._status_sep2.setVisible(mismatch)
        self.statusBar().clearMessage()
        self.setWindowTitle(f"{info.name} — FileForge")

    def _update_status_for_closed(self):
        self._status_file.setText("No file loaded — drop a file anywhere or press Ctrl+O")
        self._status_file.setToolTip("")
        for w in (self._status_sep1, self._status_sep2, self._status_kind, self._status_size, self._status_warn):
            w.setVisible(False)
        self._status_kind.setText("")
        self._status_size.setText("")
        self.statusBar().clearMessage()
        self.setWindowTitle("FileForge — File Properties Manager")

    def _update_file_actions(self):
        has = self._current_info is not None
        for act in (self._copy_path_act, self._reveal_act, self._open_default_act):
            act.setEnabled(has)

    def _overview_show_recent(self):
        self._tab_overview.set_recent_files(self._sidebar.recent_files())

    def _populate_recent_menu(self):
        self._recent_menu.clear()
        recent = self._sidebar.recent_files()
        if not recent:
            act = self._recent_menu.addAction("(no recent files)")
            act.setEnabled(False)
            return
        for i, path in enumerate(recent[:15]):
            label = f"{'&' + str(i + 1) if i < 9 else ' '}  {os.path.basename(path)}"
            act = self._recent_menu.addAction(label)
            act.setToolTip(path)
            act.setEnabled(os.path.isfile(path))
            act.triggered.connect(lambda checked, p=path: self._load_file(p))
        self._recent_menu.addSeparator()
        self._recent_menu.addAction("Clear Recent", self._sidebar._clear_recent)

    # ── Helpers ────────────────────────────────────────────────────────

    def _show_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}", 5000)
        QMessageBox.critical(self, "FileForge Error", msg)

    def _copy_current_path(self):
        if self._current_info:
            copy_to_clipboard(self._current_info.path)
            self.statusBar().showMessage("Path copied to clipboard.", 2500)

    def _reveal_current(self):
        if self._current_info:
            reveal_in_file_manager(self._current_info.path)

    def _open_current_externally(self):
        if self._current_info and not open_with_default_app(self._current_info.path):
            self.statusBar().showMessage("No application is associated with this file type.", 4000)

    def _focus_filter(self):
        self._sidebar.setVisible(True)
        self._sidebar.focus_filter()

    def _analyse_folder(self, folder: str):
        self._tab_folder_analysis.set_folder(folder)
        self._tabs.setCurrentWidget(self._tab_folder_analysis)

    def _analyse_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Analyse Folder")
        if folder:
            self._analyse_folder(folder)

    def _open_log_folder(self):
        try:
            from modules.integrity_tools import ensure_app_data_dir
            open_with_default_app(str(ensure_app_data_dir()))
        except Exception as e:
            self._show_error(str(e))

    def _show_about(self):
        QMessageBox.about(
            self, "About FileForge",
            f"<b>FileForge v{__version__}</b><br>"
            "A comprehensive file properties and analysis manager.<br><br>"
            "<b>Core Features:</b><br>"
            "• Rich metadata inspection with entropy analysis<br>"
            "• Content-based type detection (magic bytes) with extension-mismatch warnings<br>"
            "• File rename, move, copy operations<br>"
            "• Precise timestamp editing<br>"
            "• Visual permission editor<br>"
            "• Multiple hash algorithms (MD5, SHA-1, SHA-256, SHA-512, BLAKE2)<br>"
            "• Audio tag editing<br>"
            "• Batch rename with regex, numbering and case transforms<br><br>"
            "<b>Advanced Features:</b><br>"
            "• File entropy calculation and per-region entropy graph<br>"
            "• String extraction from binary files<br>"
            "• Digital signature inspection (Authenticode, Apple codesign, PGP/GPG)<br>"
            "• File comparison tool with diff modes<br>"
            "• Paged hex viewer and binary analysis<br>"
            "• Folder statistics and fast duplicate finder<br>"
            "• File watcher with auto-refresh<br>"
            "• Drag-and-drop file opening<br>"
            "• Dark and light themes, adjustable font size<br><br>"
            "<b>Supported Platforms:</b><br>"
            "Windows, macOS, Linux<br><br>"
            "<b>Credits:</b><br>"
            "Hana Eun-Seo, Florian van den Bersselaar,<br>"
            "Simon Roberge, Anna Zieleman"
        )

    def _show_settings(self):
        dialog = SettingsDialog(self)
        dialog.settings_applied.connect(self._apply_settings)
        dialog.exec_()

    def _apply_settings(self):
        self.setStyleSheet(build_stylesheet(self._app_settings.font_px()))
        self._sidebar.set_show_hidden(self._app_settings.show_hidden_files())
        self._tab_hashes.refresh_defaults()

    def _show_comparison(self):
        dialog = ComparisonDialog(self)
        if self._current_info:
            dialog.set_first_path(self._current_info.path)
        dialog.exec_()

    # ── Window state ───────────────────────────────────────────────────

    def _restore_window_state(self):
        s = QSettings("FileForge", "FileForge")
        geometry = s.value("window/geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
        splitter = s.value("window/splitter")
        if isinstance(splitter, QByteArray) and not splitter.isEmpty():
            self._splitter.restoreState(splitter)
        tab = s.value("window/tab", 0, type=int)
        if 0 <= tab < self._tabs.count():
            self._tabs.setCurrentIndex(tab)

    def _save_window_state(self):
        s = QSettings("FileForge", "FileForge")
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/splitter", self._splitter.saveState())
        s.setValue("window/tab", self._tabs.currentIndex())

    def closeEvent(self, event):
        self._save_window_state()
        self._request_id += 1
        # Ask tabs with background work to stop, then wait for every thread
        for tab in self._leaf_tabs + [self._tab_batch]:
            shutdown = getattr(tab, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception:
                    logger.exception("Error while shutting down %s", type(tab).__name__)
        for thread in list(self._live_threads):
            thread.quit()
            thread.wait(3000)
        event.accept()

    # ── Drag and Drop ───────────────────────────────────────────────────

    @staticmethod
    def _local_paths(event) -> list[str]:
        if not event.mimeData().hasUrls():
            return []
        return [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]

    def dragEnterEvent(self, event):
        paths = self._local_paths(event)
        if paths and all(os.path.exists(p) for p in paths):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        paths = self._local_paths(event)
        files = [p for p in paths if os.path.isfile(p)]
        folders = [p for p in paths if os.path.isdir(p)]
        if not paths:
            event.ignore()
            return
        if len(paths) == 1 and files:
            self._load_file(files[0])
        elif len(paths) == 1 and folders:
            self.open_folder(folders[0])
        else:
            # Several items: queue them for batch renaming
            added = self._tab_batch.add_paths(files, folders)
            self._tabs.setCurrentWidget(self._tab_batch)
            self.statusBar().showMessage(f"Added {added} file(s) to Batch.", 4000)
        event.acceptProposedAction()
