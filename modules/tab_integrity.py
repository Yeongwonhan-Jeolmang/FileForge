"""
tab_integrity.py — File/folder integrity snapshot and verification UI.
"""

from __future__ import annotations
import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem,
)
from PyQt5.QtCore import Qt

from modules.integrity_tools import create_snapshot, save_snapshot, load_snapshot, verify_snapshot
from modules.widgets import SectionLabel, StatusBanner
from modules.theme import TEXT_SECONDARY, TEXT_MUTED, ACCENT


class IntegrityTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target: str | None = None
        self._target_is_folder = False
        self._loaded_snapshot: dict | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 20, 20, 10)
        hl.setSpacing(14)

        self._target_label = QLabel('No target selected')
        self._target_label.setStyleSheet(f'color: {TEXT_SECONDARY};')
        self._target_label.setWordWrap(True)

        self._select_file_btn = QPushButton('Select File…')
        self._select_file_btn.clicked.connect(self._select_file)
        self._select_folder_btn = QPushButton('Select Folder…')
        self._select_folder_btn.clicked.connect(self._select_folder)
        self._snapshot_btn = QPushButton('Create Snapshot')
        self._snapshot_btn.setObjectName('primary')
        self._snapshot_btn.clicked.connect(self._create_snapshot)
        self._verify_btn = QPushButton('Verify Snapshot…')
        self._verify_btn.clicked.connect(self._verify_snapshot)

        hl.addWidget(self._target_label, 1)
        hl.addWidget(self._select_file_btn)
        hl.addWidget(self._select_folder_btn)
        hl.addWidget(self._snapshot_btn)
        hl.addWidget(self._verify_btn)
        outer.addWidget(header)

        self._results_tree = QTreeWidget()
        self._results_tree.setColumnCount(2)
        self._results_tree.setHeaderLabels(['Path', 'Status'])
        self._results_tree.setAlternatingRowColors(True)
        outer.addWidget(self._results_tree)

        self._set_enabled(False)

    def load(self, info=None):
        if info:
            self._target = info.path
            self._target_is_folder = False
            self._target_label.setText(self._target)
            self._set_enabled(True)
        else:
            self.clear()

    def clear(self):
        self._target = None
        self._target_label.setText('No target selected')
        self._results_tree.clear()
        self._loaded_snapshot = None
        self._set_enabled(False)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select File')
        if path:
            self._target = path
            self._target_is_folder = False
            self._target_label.setText(path)
            self._set_enabled(True)

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder:
            self._target = folder
            self._target_is_folder = True
            self._target_label.setText(folder)
            self._set_enabled(True)

    def _create_snapshot(self):
        if not self._target:
            self._banner.show_message('Select a file or folder first.', 'warning')
            return
        default = 'snapshot.json'
        path, _ = QFileDialog.getSaveFileName(self, 'Save Snapshot', default, filter='JSON Files (*.json)')
        if not path:
            return
        snapshot = create_snapshot(self._target)
        ok, msg = save_snapshot(snapshot, path)
        self._banner.show_message(msg, 'success' if ok else 'error')
        if ok:
            self._loaded_snapshot = snapshot
            self._display_verify_results(verify_snapshot(snapshot))

    def _verify_snapshot(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open Snapshot', filter='JSON Files (*.json)')
        if not path:
            return
        snapshot = load_snapshot(path)
        if snapshot is None:
            self._banner.show_message('Unable to load snapshot file.', 'error')
            return
        self._loaded_snapshot = snapshot
        results = verify_snapshot(snapshot)
        self._display_verify_results(results)
        self._banner.show_message('Snapshot verification completed.', 'success')

    def _display_verify_results(self, results: dict) -> None:
        self._results_tree.clear()
        for status in ['missing', 'changed', 'extra', 'unchanged']:
            items = results.get(status, [])
            if not items:
                continue
            parent = QTreeWidgetItem([status.title(), str(len(items))])
            self._results_tree.addTopLevelItem(parent)
            for item in items:
                if isinstance(item, dict):
                    path = item.get('path', 'Unknown')
                    reason = item.get('reason', '')
                    child = QTreeWidgetItem([path, reason])
                else:
                    child = QTreeWidgetItem([item, status])
                parent.addChild(child)
            parent.setExpanded(True)

    def _set_enabled(self, enabled: bool) -> None:
        self._snapshot_btn.setEnabled(enabled)
        self._verify_btn.setEnabled(True)
