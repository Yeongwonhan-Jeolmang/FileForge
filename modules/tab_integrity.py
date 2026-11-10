"""
tab_integrity.py — File/folder integrity snapshot and verification UI.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.integrity_tools import (
    create_snapshot,
    load_snapshot,
    save_snapshot,
    verify_snapshot,
)
from modules.theme import (
    ACCENT,
    ERROR,
    INFO,
    SUCCESS,
    TEXT_MUTED,
    TEXT_SECONDARY,
    WARNING,
)
from modules.widgets import Card, SectionLabel, StatusBanner

_STATUS_STYLE = {
    "missing": ("Missing", ERROR, "✕"),
    "changed": ("Changed", WARNING, "≠"),
    "extra": ("New files", INFO, "+"),
    "unchanged": ("Unchanged", SUCCESS, "✓"),
}


class _IntegrityWorker(QObject):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str, object)  # mode, result
    error = pyqtSignal(str)

    def __init__(self, mode: str, target=None, snapshot=None, deep=False):
        super().__init__()
        self._mode = mode
        self._target = target
        self._snapshot = snapshot
        self._deep = deep
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            cb = lambda d, t, p: self.progress.emit(d, t, p)
            if self._mode == "create":
                if not self._target:
                    raise ValueError("No folder selected.")
                result = create_snapshot(
                    self._target, progress_cb=cb, cancel_cb=self._stop.is_set
                )
            else:
                if self._snapshot is None:
                    raise ValueError("No snapshot loaded.")
                result = verify_snapshot(
                    self._snapshot,
                    progress_cb=cb,
                    cancel_cb=self._stop.is_set,
                    deep=self._deep,
                )
            self.finished.emit(self._mode, result)
        except Exception as e:
            self.error.emit(str(e))


class IntegrityTab(QWidget):
    file_open_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target: str | None = None
        self._target_is_folder = False
        self._loaded_snapshot: dict | None = None
        self._pending_save_path: str | None = None
        self._thread: QThread | None = None
        self._worker: _IntegrityWorker | None = None
        self._explicit_target = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 20)
        bl.setSpacing(12)
        outer.addWidget(body, 1)

        bl.addWidget(SectionLabel("Integrity Snapshots"))
        intro = QLabel(
            "Record SHA-256 fingerprints of a file or a whole folder, then verify later "
            "to see exactly what was added, removed or modified."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TEXT_SECONDARY};")
        bl.addWidget(intro)

        header = Card()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(8)

        self._target_label = QLabel("No target selected")
        self._target_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._target_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._target_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self._select_file_btn = QPushButton("Select File…")
        self._select_file_btn.clicked.connect(self._select_file)
        self._select_folder_btn = QPushButton("Select Folder…")
        self._select_folder_btn.clicked.connect(self._select_folder)
        self._snapshot_btn = QPushButton("Create Snapshot")
        self._snapshot_btn.setObjectName("primary")
        self._snapshot_btn.clicked.connect(self._create_snapshot)
        self._verify_btn = QPushButton("Verify Snapshot…")
        self._verify_btn.clicked.connect(self._verify_snapshot)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel)
        self._cancel_btn.hide()

        hl.addWidget(self._target_label, 1)
        hl.addWidget(self._select_file_btn)
        hl.addWidget(self._select_folder_btn)
        hl.addWidget(self._cancel_btn)
        hl.addWidget(self._snapshot_btn)
        hl.addWidget(self._verify_btn)
        bl.addWidget(header)

        opts = QHBoxLayout()
        self._deep_chk = QCheckBox(
            "Deep verify (re-hash every file, even if size and date are unchanged)"
        )
        self._deep_chk.setToolTip(
            "Slower, but catches modifications that restored the original timestamp"
        )
        opts.addWidget(self._deep_chk)
        opts.addStretch()
        self._summary_lbl = QLabel("")
        opts.addWidget(self._summary_lbl)
        bl.addLayout(opts)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.hide()
        self._progress_lbl = QLabel("")
        self._progress_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._progress_lbl.hide()
        bl.addWidget(self._progress)
        bl.addWidget(self._progress_lbl)

        self._results_tree = QTreeWidget()
        self._results_tree.setColumnCount(2)
        self._results_tree.setHeaderLabels(["Path", "Status"])
        self._results_tree.setAlternatingRowColors(True)
        self._results_tree.setUniformRowHeights(True)
        self._results_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._results_tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self._results_tree.itemDoubleClicked.connect(self._on_double_click)
        bl.addWidget(self._results_tree, 1)

        self._set_enabled(False)

    def load(self, info=None):
        if info:
            if not self._explicit_target and self._thread is None:
                self._target = info.path
                self._target_is_folder = False
                self._target_label.setText(self._target)
                self._set_enabled(True)
        else:
            self.clear()

    def clear(self):
        if self._explicit_target:
            return
        self._target = None
        self._target_label.setText("No target selected")
        self._results_tree.clear()
        self._summary_lbl.setText("")
        self._loaded_snapshot = None
        self._set_enabled(False)

    def shutdown(self):
        self._cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self._target = path
            self._target_is_folder = False
            self._explicit_target = True
            self._target_label.setText(path)
            self._set_enabled(True)

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._target = folder
            self._target_is_folder = True
            self._explicit_target = True
            self._target_label.setText(f"📁  {folder}")
            self._set_enabled(True)

    def _create_snapshot(self):
        if not self._target:
            self._banner.show_message("Select a file or folder first.", "warning")
            return
        base = Path(self._target)
        default = str(
            (base if base.is_dir() else base.parent) / f"{base.name}.snapshot.json"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Snapshot", default, filter="JSON Files (*.json)"
        )
        if not path:
            return
        self._pending_save_path = path
        self._start(_IntegrityWorker("create", target=self._target), "Hashing files…")

    def _verify_snapshot(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Snapshot", filter="JSON Files (*.json)"
        )
        if not path:
            return
        snapshot = load_snapshot(path)
        if snapshot is None or "entries" not in snapshot:
            self._banner.show_message("Unable to load snapshot file.", "error")
            return
        self._loaded_snapshot = snapshot
        self._start(
            _IntegrityWorker(
                "verify", snapshot=snapshot, deep=self._deep_chk.isChecked()
            ),
            "Verifying…",
        )

    def _start(self, worker: _IntegrityWorker, label: str):
        if self._thread is not None:
            return
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
        self._progress.setRange(0, 0)
        self._progress.show()
        self._progress_lbl.setText(label)
        self._progress_lbl.show()
        self._cancel_btn.show()
        self._set_enabled(bool(self._target))
        thread.start()

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def _on_progress(self, done: int, total: int, path: str):
        if total:
            self._progress.setRange(0, total)
            self._progress.setValue(done)
        name = path if len(path) < 90 else "…" + path[-89:]
        self._progress_lbl.setText(f"{done:,} / {total:,}  ·  {name}")

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
        self._set_enabled(bool(self._target))

    def _on_finished(self, mode: str, result: dict):
        if mode == "create":
            if result.get("cancelled"):
                self._banner.show_message(
                    "Snapshot cancelled — nothing was saved.", "warning"
                )
                return
            if not self._pending_save_path:
                self._banner.show_message(
                    "No save location chosen — nothing was saved.", "warning"
                )
                return
            ok, msg = save_snapshot(result, self._pending_save_path)
            errors = len(result.get("errors", []))
            if ok and errors:
                msg += f"  ({errors} unreadable file(s) skipped)"
            self._banner.show_message(msg, "success" if ok else "error")
            if ok:
                self._loaded_snapshot = result
                self._display_snapshot(result)
        else:
            self._display_verify_results(result)
            problems = (
                len(result["missing"]) + len(result["changed"]) + len(result["extra"])
            )
            if result.get("cancelled"):
                self._banner.show_message(
                    "Verification cancelled — partial results shown.", "warning"
                )
            elif problems:
                self._banner.show_message(
                    f"Verification found {problems} difference(s).", "warning"
                )
            else:
                self._banner.show_message(
                    "Everything matches the snapshot. ✓", "success"
                )

    def _display_snapshot(self, snapshot: dict):
        self._results_tree.clear()
        entries = snapshot.get("entries", [])
        parent = QTreeWidgetItem(
            [
                f"Snapshot of {snapshot.get('base')}",
                f"{len(entries):,} file(s) recorded",
            ]
        )
        parent.setForeground(0, QColor(ACCENT))
        self._results_tree.addTopLevelItem(parent)
        for e in entries[:2000]:
            child = QTreeWidgetItem([e["relative_path"], e["sha256"][:16] + "…"])
            child.setToolTip(1, e["sha256"])
            child.setData(0, Qt.UserRole, e.get("absolute_path"))
            parent.addChild(child)
        parent.setExpanded(len(entries) <= 200)
        self._summary_lbl.setText(f"{len(entries):,} file(s) fingerprinted")
        self._summary_lbl.setStyleSheet(f"color: {SUCCESS};")

    def _display_verify_results(self, results: dict) -> None:
        self._results_tree.clear()
        base = (
            Path(self._loaded_snapshot.get("base", ""))
            if self._loaded_snapshot
            else None
        )
        is_folder = bool(
            self._loaded_snapshot and self._loaded_snapshot.get("type") == "folder"
        )
        counts = []
        for status in ["missing", "changed", "extra", "unchanged"]:
            items = results.get(status, [])
            if not items:
                continue
            label, color, icon = _STATUS_STYLE[status]
            counts.append(f"{icon} {len(items):,} {label.lower()}")
            parent = QTreeWidgetItem([f"{icon}  {label}", str(len(items))])
            parent.setForeground(0, QColor(color))
            parent.setForeground(1, QColor(color))
            self._results_tree.addTopLevelItem(parent)
            for item in items[:5000]:
                if isinstance(item, dict):
                    path = item.get("path", "Unknown")
                    reason = item.get("reason", "")
                    child = QTreeWidgetItem([path, reason])
                else:
                    path = item
                    child = QTreeWidgetItem([item, status])
                if base is not None and status != "missing":
                    full = str(base / path) if is_folder else str(base)
                    child.setData(0, Qt.UserRole, full)
                    child.setToolTip(0, full)
                parent.addChild(child)
            parent.setExpanded(status != "unchanged")
        self._summary_lbl.setText("   ".join(counts))
        problems = any(results.get(k) for k in ("missing", "changed", "extra"))
        self._summary_lbl.setStyleSheet(f"color: {WARNING if problems else SUCCESS};")

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            self.file_open_requested.emit(path)

    def _set_enabled(self, enabled: bool) -> None:
        busy = self._thread is not None
        self._snapshot_btn.setEnabled(enabled and not busy)
        self._verify_btn.setEnabled(not busy)
        self._select_file_btn.setEnabled(not busy)
        self._select_folder_btn.setEnabled(not busy)
