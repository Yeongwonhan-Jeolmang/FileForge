"""
tab_folder_analysis.py — Folder scan, duplicate finder, and export/reporting UI.
"""

from __future__ import annotations
import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QFileDialog, QTreeWidget,
    QTreeWidgetItem, QSplitter, QTextEdit, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from modules.folder_tools import scan_folder, find_duplicates, export_report_json, export_report_csv
from modules.widgets import SectionLabel, StatusBanner
from modules.theme import BG_CARD, BORDER, TEXT_SECONDARY, TEXT_MUTED, ACCENT, BG_PANEL


class FolderAnalysisTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder = ''
        self._summary: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        splitter = QSplitter(Qt.Vertical)
        outer.addWidget(splitter)

        controls = QWidget()
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(20, 20, 20, 10)
        cl.setSpacing(14)

        cl.addWidget(SectionLabel('Folder Analysis'))

        row = QHBoxLayout()
        self._folder_label = QLabel('No folder selected')
        self._folder_label.setStyleSheet(f'color: {TEXT_SECONDARY};')
        self._folder_label.setWordWrap(True)
        row.addWidget(self._folder_label)
        self._browse_btn = QPushButton('Select Folder…')
        self._browse_btn.clicked.connect(self._choose_folder)
        self._scan_btn = QPushButton('Scan Folder')
        self._scan_btn.setObjectName('primary')
        self._scan_btn.clicked.connect(self._scan)
        row.addWidget(self._browse_btn)
        row.addWidget(self._scan_btn)
        cl.addLayout(row)

        action_row = QHBoxLayout()
        self._dup_btn = QPushButton('Find Duplicates')
        self._dup_btn.clicked.connect(self._find_duplicates)
        self._export_json_btn = QPushButton('Export JSON Report')
        self._export_json_btn.clicked.connect(self._export_json)
        self._export_csv_btn = QPushButton('Export CSV Report')
        self._export_csv_btn.clicked.connect(self._export_csv)
        action_row.addWidget(self._dup_btn)
        action_row.addWidget(self._export_json_btn)
        action_row.addWidget(self._export_csv_btn)
        action_row.addStretch()
        cl.addLayout(action_row)

        controls.setMinimumHeight(160)
        splitter.addWidget(controls)

        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(20, 10, 20, 20)
        bl.setSpacing(12)

        self._summary_view = QTextEdit()
        self._summary_view.setReadOnly(True)
        self._summary_view.setStyleSheet(f'background: {BG_PANEL}; color: {TEXT_SECONDARY};')
        self._summary_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._duplicate_tree = QTreeWidget()
        self._duplicate_tree.setHeaderLabels(['Duplicate Group', 'File Count', 'Size'])
        self._duplicate_tree.setAlternatingRowColors(True)
        self._duplicate_tree.setStyleSheet(f'background: {BG_CARD};')
        self._duplicate_tree.setFixedWidth(420)

        bl.addWidget(self._summary_view)
        bl.addWidget(self._duplicate_tree)
        splitter.addWidget(bottom)

        splitter.setSizes([180, 460])

        self._set_enabled(False)

    def load(self, info=None):
        if info:
            self._folder = str(Path(info.path).parent)
            self._folder_label.setText(self._folder)
            self._set_enabled(True)
        else:
            self.clear()

    def clear(self):
        self._folder = ''
        self._summary = {}
        self._folder_label.setText('No folder selected')
        self._summary_view.clear()
        self._duplicate_tree.clear()
        self._set_enabled(False)

    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if d:
            self._folder = d
            self._folder_label.setText(d)
            self._set_enabled(True)

    def _scan(self):
        if not self._folder:
            self._banner.show_message('Choose a folder first.', 'warning')
            return
        self._summary = scan_folder(self._folder)
        summary_text = [
            f"Root: {self._summary['root']}",
            f"Total files: {self._summary['total_files']}",
            f"Total size: {self._summary['total_size']} bytes",
            '',
            'File type counts:',
        ]
        for kind, count in sorted(self._summary['type_counts'].items()):
            summary_text.append(f"  • {kind.capitalize()}: {count}")
        summary_text.append('')
        summary_text.append('Top largest files:')
        for item in self._summary['top_largest']:
            summary_text.append(f"  • {item['size_human']} — {item['path']}")
        self._summary_view.setPlainText('\n'.join(summary_text))
        self._duplicate_tree.clear()
        self._banner.show_message('Folder scan completed.', 'success')

    def _find_duplicates(self):
        if not self._folder:
            self._banner.show_message('Choose a folder first.', 'warning')
            return
        groups = find_duplicates(self._folder)
        self._duplicate_tree.clear()
        if not groups:
            item = QTreeWidgetItem(['No duplicates found', '', ''])
            item.setForeground(0, QColor(TEXT_MUTED))
            self._duplicate_tree.addTopLevelItem(item)
            self._banner.show_message('No duplicate files were detected.', 'info')
            return
        for idx, group in enumerate(groups, start=1):
            title = f"Group {idx}"
            item = QTreeWidgetItem([title, str(len(group['files'])), group['size_human']])
            self._duplicate_tree.addTopLevelItem(item)
            for file_path in group['files']:
                child = QTreeWidgetItem([file_path, '', ''])
                item.addChild(child)
        self._duplicate_tree.expandAll()
        self._banner.show_message(f'Found {len(groups)} duplicate group(s).', 'success')

    def _export_json(self):
        if not self._summary:
            self._banner.show_message('Scan first before exporting.', 'warning')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export JSON Report', filter='JSON Files (*.json)')
        if not path:
            return
        ok, msg = export_report_json(self._summary, path)
        self._banner.show_message(msg, 'success' if ok else 'error')

    def _export_csv(self):
        if not self._summary:
            self._banner.show_message('Scan first before exporting.', 'warning')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export CSV Report', filter='CSV Files (*.csv)')
        if not path:
            return
        ok, msg = export_report_csv(self._summary, path)
        self._banner.show_message(msg, 'success' if ok else 'error')

    def _set_enabled(self, enabled: bool):
        self._scan_btn.setEnabled(enabled)
        self._dup_btn.setEnabled(enabled)
        self._export_json_btn.setEnabled(enabled and bool(self._summary))
        self._export_csv_btn.setEnabled(enabled and bool(self._summary))
