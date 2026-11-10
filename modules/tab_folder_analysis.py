"""
tab_folder_analysis.py — Folder scan, duplicate finder, and export/reporting UI.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.file_info import human_size
from modules.folder_tools import (
    export_report_csv,
    export_report_json,
    find_duplicates,
    scan_folder,
)
from modules.theme import (
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)
from modules.widgets import (
    Card,
    SectionLabel,
    StatusBanner,
    copy_to_clipboard,
    kind_color,
    kind_icon,
    reveal_in_file_manager,
)

# ── Worker ────────────────────────────────────────────────────────────────


class _FolderWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, object)  # mode, result
    error = pyqtSignal(str)

    def __init__(self, folder: str, mode: str):
        super().__init__()
        self._folder = folder
        self._mode = mode
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            cb = lambda n, p: self.progress.emit(n, p)
            if self._mode == "scan":
                result = scan_folder(
                    self._folder, progress_cb=cb, cancel_cb=self._stop.is_set
                )
            else:
                result = find_duplicates(
                    self._folder,
                    progress_cb=cb,
                    cancel_cb=self._stop.is_set,
                    max_workers=min(8, (os.cpu_count() or 2) * 2),
                )
            self.finished.emit(self._mode, result)
        except Exception as e:
            self.error.emit(str(e))


class _StatTile(Card):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        self._value = QLabel("—")
        self._value.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {TEXT_PRIMARY};"
        )
        self._title = QLabel(title.upper())
        self._title.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; letter-spacing: 1px;"
        )
        self._sub = QLabel("")
        self._sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        lay.addWidget(self._title)
        lay.addWidget(self._value)
        lay.addWidget(self._sub)

    def set(self, value: str, sub: str = "", color: str | None = None):
        self._value.setText(value)
        self._sub.setText(sub)
        self._value.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {color or TEXT_PRIMARY};"
        )


# ── Tab ───────────────────────────────────────────────────────────────────


class FolderAnalysisTab(QWidget):
    file_open_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder = ""
        self._summary: dict = {}
        self._duplicates: list = []
        self._thread: QThread | None = None
        self._worker: _FolderWorker | None = None
        self._explicit_folder = (
            False  # chosen by the user → don't override on file load
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 20)
        bl.setSpacing(12)
        outer.addWidget(body, 1)

        bl.addWidget(SectionLabel("Folder Analysis"))

        controls = Card()
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(8)
        self._folder_label = QLabel("No folder selected")
        self._folder_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._folder_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        cl.addWidget(self._folder_label, 1)
        self._browse_btn = QPushButton("Select Folder…")
        self._browse_btn.clicked.connect(self._choose_folder)
        self._scan_btn = QPushButton("Scan Folder")
        self._scan_btn.setObjectName("primary")
        self._scan_btn.clicked.connect(self._scan)
        self._dup_btn = QPushButton("Find Duplicates")
        self._dup_btn.clicked.connect(self._find_duplicates)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel)
        self._cancel_btn.hide()
        self._export_json_btn = QPushButton("Export JSON")
        self._export_json_btn.clicked.connect(self._export_json)
        self._export_csv_btn = QPushButton("Export CSV")
        self._export_csv_btn.clicked.connect(self._export_csv)
        for b in (
            self._browse_btn,
            self._scan_btn,
            self._dup_btn,
            self._cancel_btn,
            self._export_json_btn,
            self._export_csv_btn,
        ):
            cl.addWidget(b)
        bl.addWidget(controls)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.hide()
        self._progress_lbl = QLabel("")
        self._progress_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._progress_lbl.hide()
        bl.addWidget(self._progress)
        bl.addWidget(self._progress_lbl)

        # ── Stat tiles ────────────────────────────────────────────────
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self._tile_files = _StatTile("Files")
        self._tile_size = _StatTile("Total size")
        self._tile_types = _StatTile("Top type")
        self._tile_dups = _StatTile("Duplicates")
        for t in (self._tile_files, self._tile_size, self._tile_types, self._tile_dups):
            tiles.addWidget(t, 1)
        bl.addLayout(tiles)

        # ── Results ───────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        bl.addWidget(splitter, 1)

        left_tabs = QTabWidget()
        left_tabs.setDocumentMode(True)

        self._types_tree = QTreeWidget()
        self._types_tree.setHeaderLabels(["Type", "Files", "Size", "Share"])
        self._types_tree.setRootIsDecorated(False)
        self._types_tree.setAlternatingRowColors(True)
        self._types_tree.header().setStretchLastSection(False)
        self._types_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            self._types_tree.header().setSectionResizeMode(
                c, QHeaderView.ResizeToContents
            )
        left_tabs.addTab(self._types_tree, "Types")

        self._ext_tree = QTreeWidget()
        self._ext_tree.setHeaderLabels(["Extension", "Files"])
        self._ext_tree.setRootIsDecorated(False)
        self._ext_tree.setAlternatingRowColors(True)
        self._ext_tree.header().setStretchLastSection(False)
        self._ext_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._ext_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        left_tabs.addTab(self._ext_tree, "Extensions")

        self._largest_tree = self._file_tree(["File", "Size"])
        left_tabs.addTab(self._largest_tree, "Largest")
        self._recent_tree = self._file_tree(["File", "Modified"])
        left_tabs.addTab(self._recent_tree, "Recently Modified")
        splitter.addWidget(left_tabs)

        dup_box = QWidget()
        dl = QVBoxLayout(dup_box)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(6)
        dup_title = QLabel("DUPLICATE GROUPS")
        dup_title.setObjectName("sectionLabel")
        dl.addWidget(dup_title)
        self._duplicate_tree = QTreeWidget()
        self._duplicate_tree.setHeaderLabels(
            ["Duplicate Group", "Files", "Size", "Wasted"]
        )
        self._duplicate_tree.setAlternatingRowColors(True)
        self._duplicate_tree.setUniformRowHeights(True)
        self._duplicate_tree.header().setStretchLastSection(False)
        self._duplicate_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            self._duplicate_tree.header().setSectionResizeMode(
                c, QHeaderView.ResizeToContents
            )
        self._duplicate_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._duplicate_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._duplicate_tree.customContextMenuRequested.connect(
            lambda pos: self._context_menu(self._duplicate_tree, pos)
        )
        dl.addWidget(self._duplicate_tree, 1)
        splitter.addWidget(dup_box)
        splitter.setSizes([480, 520])

        # Kept for compatibility: older code wrote the textual summary here
        self._summary_view = QTextEdit()
        self._summary_view.hide()

        self._set_enabled(False)

    def _file_tree(self, headers: list[str]) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.header().setStretchLastSection(False)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(
            lambda pos, t=tree: self._context_menu(t, pos)
        )
        return tree

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info=None):
        if info:
            if not self._explicit_folder:
                folder = str(Path(info.path).parent)
                if folder != self._folder:
                    self._set_folder(folder, explicit=False)
        else:
            self.clear()

    def set_folder(self, folder: str):
        """Point the tab at a folder (from the sidebar / Tools menu)."""
        self._set_folder(folder, explicit=True)

    def clear(self):
        if self._explicit_folder:
            return  # keep a folder the user picked on purpose
        self._cancel()
        self._folder = ""
        self._summary = {}
        self._duplicates = []
        self._folder_label.setText("No folder selected")
        self._reset_results()
        self._set_enabled(False)

    def shutdown(self):
        self._cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)

    # ── Slots ─────────────────────────────────────────────────────────

    def _set_folder(self, folder: str, explicit: bool):
        self._cancel()
        self._folder = folder
        self._explicit_folder = explicit
        self._summary = {}
        self._duplicates = []
        self._folder_label.setText(folder)
        self._folder_label.setToolTip(folder)
        self._reset_results()
        self._set_enabled(True)

    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder", self._folder)
        if d:
            self._set_folder(d, explicit=True)

    def _start(self, mode: str):
        if not self._folder:
            self._banner.show_message("Choose a folder first.", "warning")
            return
        if self._thread is not None:
            return
        worker = _FolderWorker(self._folder, mode)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.finished.connect(thread.quit)
        worker.error.connect(lambda e: self._banner.show_message(e, "error"))
        worker.error.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        self._worker, self._thread = worker, thread
        self._progress.show()
        self._progress_lbl.setText(
            "Scanning…" if mode == "scan" else "Looking for duplicates…"
        )
        self._progress_lbl.show()
        self._cancel_btn.show()
        self._set_enabled(True)
        thread.start()

    def _scan(self):
        self._start("scan")

    def _find_duplicates(self):
        self._start("dups")

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def _on_progress(self, n: int, path: str):
        self._progress_lbl.setText(f"{n:,} files…  {_elide(path, 90)}")

    def _on_thread_finished(self):
        self._progress.hide()
        self._progress_lbl.hide()
        self._cancel_btn.hide()
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self._set_enabled(bool(self._folder))

    def _on_finished(self, mode: str, result):
        if mode == "scan":
            self._summary = result
            if self._duplicates:
                self._summary["duplicates"] = self._duplicates
            self._show_summary(result)
            msg = (
                "Scan cancelled — partial results shown."
                if result.get("cancelled")
                else f"Scanned {result['total_files']:,} files in {result['scan_seconds']:.2f}s."
            )
            self._banner.show_message(
                msg, "warning" if result.get("cancelled") else "success"
            )
        else:
            self._duplicates = result
            if self._summary:
                self._summary["duplicates"] = result
            self._show_duplicates(result)

    def _reset_results(self):
        for tree in (
            self._types_tree,
            self._ext_tree,
            self._largest_tree,
            self._recent_tree,
            self._duplicate_tree,
        ):
            tree.clear()
        self._tile_files.set("—")
        self._tile_size.set("—")
        self._tile_types.set("—")
        self._tile_dups.set("—", "click Find Duplicates")

    def _show_summary(self, s: dict):
        total = s["total_files"]
        self._tile_files.set(f"{total:,}", f"{s.get('empty_files', 0):,} empty")
        self._tile_size.set(
            s.get("total_size_human", human_size(s["total_size"])),
            f"oldest change {s.get('oldest_modified_str', '').split('  ')[0]}",
        )
        types = sorted(s["type_counts"].items(), key=lambda kv: -kv[1])
        if types:
            kind, count = types[0]
            self._tile_types.set(
                f"{kind_icon(kind)} {kind.capitalize()}",
                f"{count:,} files ({count / max(total, 1):.0%})",
                kind_color(kind),
            )

        self._types_tree.clear()
        sizes = s.get("type_sizes", {})
        for kind, count in types:
            size = sizes.get(kind, 0)
            share = size / s["total_size"] if s["total_size"] else 0
            item = QTreeWidgetItem(
                [
                    f"{kind_icon(kind)}  {kind.capitalize()}",
                    f"{count:,}",
                    human_size(size),
                    f"{share:.1%}",
                ]
            )
            item.setForeground(0, QColor(kind_color(kind)))
            for c in (1, 2, 3):
                item.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
            self._types_tree.addTopLevelItem(item)

        self._ext_tree.clear()
        for ext, count in list(s.get("extensions", {}).items())[:200]:
            item = QTreeWidgetItem([ext, f"{count:,}"])
            item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            self._ext_tree.addTopLevelItem(item)

        self._largest_tree.clear()
        for entry in s["top_largest"]:
            item = QTreeWidgetItem([self._rel(entry["path"]), entry["size_human"]])
            item.setData(0, Qt.UserRole, entry["path"])
            item.setToolTip(0, entry["path"])
            item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            self._largest_tree.addTopLevelItem(item)

        self._recent_tree.clear()
        for entry in s.get("recent_files", []):
            item = QTreeWidgetItem([self._rel(entry["path"]), entry["modified_str"]])
            item.setData(0, Qt.UserRole, entry["path"])
            item.setToolTip(0, entry["path"])
            self._recent_tree.addTopLevelItem(item)

        # Keep a plain-text version too (e.g. for copy/paste)
        lines = [
            f"Root: {s['root']}",
            f"Total files: {total:,}",
            f"Total size: {s.get('total_size_human', '')} ({s['total_size']:,} bytes)",
        ]
        self._summary_view.setPlainText("\n".join(lines))

    def _show_duplicates(self, groups: list):
        self._duplicate_tree.clear()
        if not groups:
            item = QTreeWidgetItem(["No duplicates found", "", "", ""])
            item.setForeground(0, QColor(TEXT_MUTED))
            self._duplicate_tree.addTopLevelItem(item)
            self._tile_dups.set("0", "no duplicate files")
            self._banner.show_message("No duplicate files were detected.", "info")
            return
        wasted = sum(g["wasted"] for g in groups)
        extra_files = sum(len(g["files"]) - 1 for g in groups)
        self._tile_dups.set(
            human_size(wasted),
            f"{len(groups):,} groups · {extra_files:,} redundant copies",
            WARNING,
        )
        items = []
        for idx, group in enumerate(groups, start=1):
            title = f"Group {idx}  ·  {os.path.basename(group['files'][0])}"
            item = QTreeWidgetItem(
                [
                    title,
                    str(len(group["files"])),
                    group["size_human"],
                    group["wasted_human"],
                ]
            )
            item.setToolTip(0, f"SHA-256 {group['hash']}")
            for c in (1, 2, 3):
                item.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
            for file_path in group["files"]:
                child = QTreeWidgetItem([self._rel(file_path), "", "", ""])
                child.setData(0, Qt.UserRole, file_path)
                child.setToolTip(0, file_path)
                item.addChild(child)
            items.append(item)
        self._duplicate_tree.addTopLevelItems(items)
        if len(groups) <= 50:
            self._duplicate_tree.expandAll()
        self._banner.show_message(
            f"Found {len(groups)} duplicate group(s) wasting {human_size(wasted)}.",
            "success",
        )

    def _rel(self, path: str) -> str:
        try:
            return os.path.relpath(path, self._folder)
        except ValueError:
            return path

    def _on_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            self.file_open_requested.emit(path)

    def _context_menu(self, tree: QTreeWidget, pos):
        item = tree.itemAt(pos)
        path = item.data(0, Qt.UserRole) if item else None
        if not path:
            return
        menu = QMenu(self)
        act_open = menu.addAction("Open in FileForge")
        act_reveal = menu.addAction("Reveal in File Manager")
        act_copy = menu.addAction("Copy Path")
        chosen = menu.exec_(tree.viewport().mapToGlobal(pos))
        if chosen is act_open:
            self.file_open_requested.emit(path)
        elif chosen is act_reveal:
            reveal_in_file_manager(path)
        elif chosen is act_copy:
            copy_to_clipboard(path)

    def _export_json(self):
        if not self._summary:
            self._banner.show_message("Scan first before exporting.", "warning")
            return
        default = os.path.join(self._folder, "folder-report.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON Report", default, filter="JSON Files (*.json)"
        )
        if not path:
            return
        ok, msg = export_report_json(self._summary, path)
        self._banner.show_message(msg, "success" if ok else "error")

    def _export_csv(self):
        if not self._summary:
            self._banner.show_message("Scan first before exporting.", "warning")
            return
        default = os.path.join(self._folder, "folder-report.csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV Report", default, filter="CSV Files (*.csv)"
        )
        if not path:
            return
        ok, msg = export_report_csv(self._summary, path)
        self._banner.show_message(msg, "success" if ok else "error")

    def _set_enabled(self, enabled: bool):
        busy = self._thread is not None
        self._scan_btn.setEnabled(enabled and not busy)
        self._dup_btn.setEnabled(enabled and not busy)
        self._browse_btn.setEnabled(not busy)
        self._export_json_btn.setEnabled(enabled and bool(self._summary) and not busy)
        self._export_csv_btn.setEnabled(enabled and bool(self._summary) and not busy)


def _elide(text: str, n: int) -> str:
    return text if len(text) <= n else "…" + text[-(n - 1) :]
