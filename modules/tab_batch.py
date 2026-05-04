"""
tab_batch.py — Batch rename multiple files with regex/plain-text find-replace.
"""

from __future__ import annotations
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QCheckBox,
    QScrollArea, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QAbstractItemView, QSplitter,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from modules.file_ops import batch_rename_preview, batch_rename_apply
from modules.widgets import SectionLabel, StatusBanner
from modules.theme import (
    BG_CARD, BORDER, SUCCESS, ERROR, ACCENT,
    TEXT_SECONDARY, BG_PANEL, TEXT_MUTED,
)


class BatchTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        splitter = QSplitter(Qt.Vertical)
        outer.addWidget(splitter)

        # ── Top: controls ──────────────────────────────────────────────
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(20, 20, 20, 10)
        tl.setSpacing(16)

        tl.addWidget(SectionLabel("Add Files"))
        add_card = self._card()
        al = QHBoxLayout(add_card)
        al.setContentsMargins(12, 8, 12, 8)
        self._add_btn = QPushButton("Add Files…")
        self._add_btn.clicked.connect(self._add_files)
        self._add_dir_btn = QPushButton("Add Folder…")
        self._add_dir_btn.clicked.connect(self._add_folder)
        self._clear_list_btn = QPushButton("Clear List")
        self._clear_list_btn.clicked.connect(self._clear_list)
        self._file_count_lbl = QLabel("0 files")
        self._file_count_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        al.addWidget(self._add_btn)
        al.addWidget(self._add_dir_btn)
        al.addWidget(self._clear_list_btn)
        al.addStretch()
        al.addWidget(self._file_count_lbl)
        tl.addWidget(add_card)

        tl.addWidget(SectionLabel("Find & Replace"))
        pattern_card = self._card()
        pl = QVBoxLayout(pattern_card)
        pl.setContentsMargins(16, 12, 16, 12)
        pl.setSpacing(10)

        row1 = QHBoxLayout()
        lbl_find = QLabel("Find:")
        lbl_find.setFixedWidth(70)
        lbl_find.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._find_edit = QLineEdit()
        self._find_edit.setPlaceholderText("Text or regex pattern…")
        self._regex_chk = QCheckBox("Regex")
        row1.addWidget(lbl_find)
        row1.addWidget(self._find_edit, 1)
        row1.addWidget(self._regex_chk)
        pl.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_rep = QLabel("Replace:")
        lbl_rep.setFixedWidth(70)
        lbl_rep.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("Replacement text (leave blank to delete)…")
        row2.addWidget(lbl_rep)
        row2.addWidget(self._replace_edit, 1)
        pl.addLayout(row2)

        # Extra transforms
        xrow = QHBoxLayout()
        self._upper_chk = QCheckBox("UPPERCASE result")
        self._lower_chk = QCheckBox("lowercase result")
        self._strip_chk = QCheckBox("Strip whitespace")
        xrow.addWidget(self._upper_chk)
        xrow.addWidget(self._lower_chk)
        xrow.addWidget(self._strip_chk)
        xrow.addStretch()
        pl.addLayout(xrow)

        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setObjectName("primary")
        self._preview_btn.clicked.connect(self._preview)
        self._apply_btn = QPushButton("Apply Rename")
        self._apply_btn.setObjectName("primary")
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._preview_btn)
        btn_row.addWidget(self._apply_btn)
        btn_row.addStretch()
        pl.addLayout(btn_row)

        tl.addWidget(pattern_card)
        splitter.addWidget(top)

        # ── Bottom: results table ──────────────────────────────────────
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(20, 10, 20, 20)

        bl.addWidget(SectionLabel("Preview / Results"))
        self._table = QTreeWidget()
        self._table.setColumnCount(3)
        self._table.setHeaderLabels(["Original Name", "→  New Name", "Status"])
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.header().setStretchLastSection(False)
        self._table.header().setSectionResizeMode(0, 1)  # Stretch
        self._table.header().setSectionResizeMode(1, 1)
        self._table.header().setSectionResizeMode(2, 2)  # ResizeToContents
        bl.addWidget(self._table)
        splitter.addWidget(bottom)

        splitter.setSizes([350, 300])

    # ── Public (stub load/clear for main_window compatibility) ──────────

    def load(self, info=None):
        pass  # batch tab manages its own file list

    def clear(self):
        pass

    # ── Slots ─────────────────────────────────────────────────────────

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add Files")
        for f in files:
            if f not in self._paths:
                self._paths.append(f)
        self._update_count()

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder")
        if d:
            for p in Path(d).iterdir():
                if p.is_file() and str(p) not in self._paths:
                    self._paths.append(str(p))
        self._update_count()

    def _clear_list(self):
        self._paths.clear()
        self._table.clear()
        self._update_count()

    def _preview(self):
        if not self._paths:
            self._banner.show_message("Add files first.", "warning")
            return
        pairs = self._compute_pairs()
        self._populate_table(pairs, apply_mode=False)

    def _apply(self):
        if not self._paths:
            self._banner.show_message("Add files first.", "warning")
            return
        pattern = self._find_edit.text()
        replacement = self._replace_edit.text()
        if not self._regex_chk.isChecked():
            # Escape pattern for literal match via re.sub
            import re
            pattern = re.escape(pattern)
        results = batch_rename_apply(self._paths, pattern, replacement)
        # Rebuild paths list with new paths for successes
        new_paths = []
        for orig, ok, msg in results:
            if ok and msg != "No change.":
                p = Path(orig)
                # derive new path from message "→ 'newname'"
                try:
                    new_name = msg.split("'")[1]
                    new_paths.append(str(p.parent / new_name))
                except Exception:
                    new_paths.append(orig)
            else:
                new_paths.append(orig)
        self._paths = new_paths
        self._update_count()
        self._populate_apply_results(results)
        ok_count = sum(1 for _, ok, m in results if ok and m != "No change.")
        self._banner.show_message(
            f"Renamed {ok_count} / {len(results)} files.",
            "success" if ok_count else "warning",
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _compute_pairs(self) -> list[tuple[str, str]]:
        pattern = self._find_edit.text()
        replacement = self._replace_edit.text()
        if not self._regex_chk.isChecked():
            import re
            pattern = re.escape(pattern)
        pairs = batch_rename_preview(self._paths, pattern, replacement)
        # Apply transforms
        result = []
        for old, new in pairs:
            if self._strip_chk.isChecked():
                stem, sep, ext = new.rpartition(".")
                new = (stem.strip() + sep + ext) if sep else new.strip()
            if self._upper_chk.isChecked():
                new = new.upper()
            elif self._lower_chk.isChecked():
                new = new.lower()
            result.append((old, new))
        return result

    def _populate_table(self, pairs: list[tuple[str, str]], apply_mode: bool):
        self._table.clear()
        for old, new in pairs:
            item = QTreeWidgetItem([old, new, "Preview"])
            if old == new:
                item.setForeground(2, QColor(TEXT_MUTED))
                item.setText(2, "No change")
            else:
                item.setForeground(1, QColor(ACCENT))
                item.setForeground(2, QColor(TEXT_MUTED))
            self._table.addTopLevelItem(item)

    def _populate_apply_results(self, results: list[tuple[str, bool, str]]):
        self._table.clear()
        for path, ok, msg in results:
            name = Path(path).name
            item = QTreeWidgetItem([name, msg, "✓" if ok else "✗"])
            item.setForeground(2, QColor(SUCCESS if ok else ERROR))
            if ok and msg != "No change.":
                item.setForeground(1, QColor(ACCENT))
            self._table.addTopLevelItem(item)

    def _update_count(self):
        n = len(self._paths)
        self._file_count_lbl.setText(f"{n} file{'s' if n != 1 else ''}")

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        return f