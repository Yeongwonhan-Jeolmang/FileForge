"""
tab_batch.py — Batch rename multiple files with regex/plain-text find-replace.

Replacement templates support tokens:
    {n}     running number (start / padding configurable)
    {name}  original name without extension
    {ext}   original extension without the dot
    {date}  file modified date, YYYY-MM-DD
    {parent} name of the containing folder
If "Find" is left empty, the whole name (minus extension when "keep extension"
is on) is replaced by the template — handy for "Holiday_{n}" style renames.
"""

from __future__ import annotations
import os
import re
import time
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
    QCheckBox,
    QTreeWidget,
    QTreeWidgetItem,
    QFileDialog,
    QAbstractItemView,
    QSplitter,
    QComboBox,
    QSpinBox,
    QMessageBox,
    QHeaderView,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor

from modules.file_ops import batch_rename_to, batch_rename_conflicts
from modules.widgets import SectionLabel, StatusBanner, Card
from modules.theme import (
    SUCCESS,
    ERROR,
    ACCENT,
    TEXT_SECONDARY,
    TEXT_MUTED,
)

_CASES = [
    "Case: unchanged",
    "lowercase",
    "UPPERCASE",
    "Title Case",
    "snake_case",
    "kebab-case",
]
_TOKEN_RE = re.compile(r"\{(n|name|ext|date|parent)\}")


class BatchTab(QWidget):
    file_open_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[str] = []
        self._undo_stack: list[list[tuple[str, str]]] = []  # [(new_path, old_name)]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        splitter = QSplitter(Qt.Vertical)
        outer.addWidget(splitter)

        # ── Top: controls ──────────────────────────────────────────────
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(24, 20, 24, 10)
        tl.setSpacing(12)

        tl.addWidget(SectionLabel("Add Files"))
        add_card = self._card()
        al = QHBoxLayout(add_card)
        al.setContentsMargins(12, 8, 12, 8)
        self._add_btn = QPushButton("Add Files…")
        self._add_btn.clicked.connect(self._add_files)
        self._add_dir_btn = QPushButton("Add Folder…")
        self._add_dir_btn.clicked.connect(self._add_folder)
        self._recursive_chk = QCheckBox("Include subfolders")
        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.clicked.connect(self._remove_selected)
        self._clear_list_btn = QPushButton("Clear List")
        self._clear_list_btn.clicked.connect(self._clear_list)
        self._file_count_lbl = QLabel("0 files")
        self._file_count_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        al.addWidget(self._add_btn)
        al.addWidget(self._add_dir_btn)
        al.addWidget(self._recursive_chk)
        al.addStretch()
        al.addWidget(self._file_count_lbl)
        al.addWidget(self._remove_btn)
        al.addWidget(self._clear_list_btn)
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
        self._find_edit.setPlaceholderText(
            "Text or regex pattern… (leave empty to replace the whole name)"
        )
        self._find_edit.setClearButtonEnabled(True)
        self._regex_chk = QCheckBox("Regex")
        self._ignore_case_chk = QCheckBox("Ignore case")
        row1.addWidget(lbl_find)
        row1.addWidget(self._find_edit, 1)
        row1.addWidget(self._regex_chk)
        row1.addWidget(self._ignore_case_chk)
        pl.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_rep = QLabel("Replace:")
        lbl_rep.setFixedWidth(70)
        lbl_rep.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText(
            "Replacement (blank = delete). Tokens: {n} {name} {ext} {date} {parent}"
        )
        self._replace_edit.setClearButtonEnabled(True)
        self._replace_edit.setToolTip(
            "{n}       running number\n"
            "{name}    original name without extension\n"
            "{ext}     original extension (no dot)\n"
            "{date}    modified date, YYYY-MM-DD\n"
            "{parent}  containing folder name\n\n"
            "With Regex on, \\1 \\2 … refer to capture groups."
        )
        row2.addWidget(lbl_rep)
        row2.addWidget(self._replace_edit, 1)
        pl.addLayout(row2)

        # Extra transforms
        xrow = QHBoxLayout()
        xrow.setSpacing(14)
        self._case_combo = QComboBox()
        self._case_combo.addItems(_CASES)
        self._strip_chk = QCheckBox("Strip whitespace")
        self._keep_ext_chk = QCheckBox("Keep extension")
        self._keep_ext_chk.setChecked(True)
        self._keep_ext_chk.setToolTip(
            "Apply find/replace and case changes to the name only, not the extension"
        )
        num_lbl = QLabel("{n} start:")
        num_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._num_start = QSpinBox()
        self._num_start.setRange(0, 999_999)
        self._num_start.setValue(1)
        pad_lbl = QLabel("digits:")
        pad_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._num_pad = QSpinBox()
        self._num_pad.setRange(1, 8)
        self._num_pad.setValue(3)
        xrow.addWidget(self._case_combo)
        xrow.addWidget(self._strip_chk)
        xrow.addWidget(self._keep_ext_chk)
        xrow.addStretch()
        xrow.addWidget(num_lbl)
        xrow.addWidget(self._num_start)
        xrow.addWidget(pad_lbl)
        xrow.addWidget(self._num_pad)
        pl.addLayout(xrow)

        # Kept for backwards compatibility with older code paths
        self._upper_chk = QCheckBox()
        self._lower_chk = QCheckBox()

        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton("Refresh Preview")
        self._preview_btn.clicked.connect(self._preview)
        self._undo_btn = QPushButton("↶  Undo Last Rename")
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self._undo)
        self._apply_btn = QPushButton("Apply Rename")
        self._apply_btn.setObjectName("primary")
        self._apply_btn.setCursor(Qt.PointingHandCursor)
        self._apply_btn.clicked.connect(self._apply)
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        btn_row.addWidget(self._summary_lbl)
        btn_row.addStretch()
        btn_row.addWidget(self._undo_btn)
        btn_row.addWidget(self._preview_btn)
        btn_row.addWidget(self._apply_btn)
        pl.addLayout(btn_row)

        tl.addWidget(pattern_card)
        tl.addStretch()
        splitter.addWidget(top)

        # ── Bottom: results table ──────────────────────────────────────
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(24, 10, 24, 20)

        bl.addWidget(SectionLabel("Preview / Results"))
        self._table = QTreeWidget()
        self._table.setColumnCount(3)
        self._table.setHeaderLabels(["Original Name", "→  New Name", "Status"])
        self._table.setRootIsDecorated(False)
        self._table.setAlternatingRowColors(True)
        self._table.setUniformRowHeights(True)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.header().setStretchLastSection(False)
        self._table.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.itemDoubleClicked.connect(self._on_row_double_clicked)
        self._table.setToolTip(
            "Double-click a row to open that file. Drop files here to add them."
        )
        bl.addWidget(self._table)
        splitter.addWidget(bottom)

        splitter.setSizes([360, 320])

        # Live preview: re-compute shortly after any option changes
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(180)
        self._preview_timer.timeout.connect(self._preview)
        for sig in (
            self._find_edit.textChanged,
            self._replace_edit.textChanged,
            self._regex_chk.toggled,
            self._ignore_case_chk.toggled,
            self._strip_chk.toggled,
            self._keep_ext_chk.toggled,
            self._case_combo.currentIndexChanged,
            self._num_start.valueChanged,
            self._num_pad.valueChanged,
        ):
            sig.connect(lambda *_: self._preview_timer.start())

        self._update_count()

    # ── Public (stub load/clear for main_window compatibility) ──────────

    def load(self, info=None):
        pass  # batch tab manages its own file list

    def clear(self):
        pass

    def add_paths(self, files: list[str], folders: list[str] | None = None) -> int:
        """Add files (and the files inside folders) to the batch list. Returns how many were added."""
        before = len(self._paths)
        existing = set(self._paths)
        candidates = list(files)
        for folder in folders or []:
            candidates.extend(self._files_in(folder, self._recursive_chk.isChecked()))
        for f in candidates:
            if f not in existing and os.path.isfile(f):
                self._paths.append(f)
                existing.add(f)
        self._update_count()
        self._preview()
        return len(self._paths) - before

    # ── Slots ─────────────────────────────────────────────────────────

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add Files")
        if files:
            self.add_paths(files)

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder")
        if d:
            added = self.add_paths([], [d])
            self._banner.show_message(
                f"Added {added} file(s) from {os.path.basename(d) or d}.", "info", 2500
            )

    @staticmethod
    def _files_in(folder: str, recursive: bool) -> list[str]:
        out = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                out.extend(
                    os.path.join(root, f)
                    for f in sorted(files)
                    if not f.startswith(".")
                )
        else:
            try:
                out = [
                    str(p)
                    for p in sorted(Path(folder).iterdir())
                    if p.is_file() and not p.name.startswith(".")
                ]
            except OSError:
                pass
        return out

    def _remove_selected(self):
        rows = sorted(
            {self._table.indexOfTopLevelItem(i) for i in self._table.selectedItems()},
            reverse=True,
        )
        for r in rows:
            if 0 <= r < len(self._paths):
                del self._paths[r]
        self._update_count()
        self._preview()

    def _clear_list(self):
        self._paths.clear()
        self._table.clear()
        self._update_count()
        self._summary_lbl.setText("")

    def _preview(self):
        if not self._paths:
            self._table.clear()
            self._summary_lbl.setText("")
            return
        try:
            pairs = self._compute_pairs()
        except re.error as e:
            self._summary_lbl.setText(f"Invalid regex: {e}")
            self._summary_lbl.setStyleSheet(f"color: {ERROR};")
            return
        self._populate_table(pairs, apply_mode=False)

    def _apply(self):
        if not self._paths:
            self._banner.show_message("Add files first.", "warning")
            return
        try:
            pairs = self._compute_pairs()
        except re.error as e:
            self._banner.show_message(f"Invalid regex: {e}", "error")
            return
        new_names = [new for _, new in pairs]
        changes = sum(1 for old, new in pairs if old != new)
        if not changes:
            self._banner.show_message(
                "Nothing to rename — every name is unchanged.", "info"
            )
            return
        problems = batch_rename_conflicts(self._paths, new_names)
        if problems:
            self._populate_table(pairs, apply_mode=False)
            self._banner.show_message(
                f"{len(problems)} conflict(s) — fix the highlighted rows before applying.",
                "error",
            )
            return
        if changes >= 20:
            reply = QMessageBox.question(
                self,
                "Confirm Batch Rename",
                f"Rename {changes} files?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

        results = batch_rename_to(self._paths, new_names)
        # Rebuild paths list with new paths for successes
        undo = [
            (new_path, Path(orig).name)
            for orig, ok, msg, new_path in results
            if ok and new_path != orig
        ]
        if undo:
            self._undo_stack.append(undo)
        self._undo_btn.setEnabled(bool(self._undo_stack))
        self._paths = [new_path for _, _, _, new_path in results]
        self._update_count()
        self._populate_apply_results(results)
        ok_count = len(undo)
        failed = sum(1 for _, ok, _, _ in results if not ok)
        self._banner.show_message(
            f"Renamed {ok_count} / {changes} files."
            + (f"  {failed} failed." if failed else ""),
            "success"
            if ok_count and not failed
            else ("warning" if ok_count else "error"),
        )

    def _undo(self):
        if not self._undo_stack:
            return
        batch = self._undo_stack.pop()
        paths = [p for p, _ in batch]
        names = [n for _, n in batch]
        results = batch_rename_to(paths, names)
        mapping = {orig: new for orig, ok, _, new in results}
        self._paths = [mapping.get(p, p) for p in self._paths]
        self._undo_btn.setEnabled(bool(self._undo_stack))
        ok = sum(1 for _, ok, _, _ in results if ok)
        self._banner.show_message(
            f"Undo: restored {ok} / {len(results)} name(s).",
            "success" if ok == len(results) else "warning",
        )
        self._preview()

    def _on_row_double_clicked(self, item: QTreeWidgetItem, col: int):
        row = self._table.indexOfTopLevelItem(item)
        if 0 <= row < len(self._paths) and os.path.isfile(self._paths[row]):
            self.file_open_requested.emit(self._paths[row])

    # ── Helpers ────────────────────────────────────────────────────────

    def _expand_tokens(self, template: str, path: str, index: int) -> str:
        p = Path(path)
        if not _TOKEN_RE.search(template):
            return template

        def repl(m):
            token = m.group(1)
            if token == "n":
                return str(self._num_start.value() + index).zfill(self._num_pad.value())
            if token == "name":
                return p.stem
            if token == "ext":
                return p.suffix.lstrip(".")
            if token == "date":
                try:
                    return time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime))
                except OSError:
                    return "unknown-date"
            if token == "parent":
                return p.parent.name
            return m.group(0)

        return _TOKEN_RE.sub(repl, template)

    @staticmethod
    def _apply_case(text: str, mode: int) -> str:
        if mode == 1:
            return text.lower()
        if mode == 2:
            return text.upper()
        if mode == 3:
            return text.title()
        if mode in (4, 5):
            sep = "_" if mode == 4 else "-"
            words = re.findall(
                r"[A-Za-z0-9]+", re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
            )
            return sep.join(w.lower() for w in words) or text
        return text

    def _compute_pairs(self) -> list[tuple[str, str]]:
        find = self._find_edit.text()
        use_regex = self._regex_chk.isChecked()
        flags = re.IGNORECASE if self._ignore_case_chk.isChecked() else 0
        pattern = (
            re.compile(find if use_regex else re.escape(find), flags) if find else None
        )
        keep_ext = self._keep_ext_chk.isChecked()
        case_mode = self._case_combo.currentIndex()

        result = []
        for index, path in enumerate(self._paths):
            old = Path(path).name
            stem, ext = (Path(old).stem, Path(old).suffix) if keep_ext else (old, "")
            replacement = self._expand_tokens(self._replace_edit.text(), path, index)

            if pattern is not None:
                if use_regex:
                    new_stem = pattern.sub(replacement, stem)
                else:
                    new_stem = pattern.sub(lambda m: replacement, stem)
            elif replacement:
                new_stem = replacement  # empty Find: template replaces the whole name
            else:
                new_stem = stem

            if self._strip_chk.isChecked():
                new_stem = re.sub(r"\s+", " ", new_stem).strip()
            new_stem = self._apply_case(new_stem, case_mode)
            result.append((old, new_stem + ext))
        return result

    def _populate_table(self, pairs: list[tuple[str, str]], apply_mode: bool):
        self._table.setUpdatesEnabled(False)
        self._table.clear()
        problems = batch_rename_conflicts(self._paths, [n for _, n in pairs])
        changes = 0
        items = []
        for i, (old, new) in enumerate(pairs):
            item = QTreeWidgetItem([old, new, ""])
            item.setToolTip(0, self._paths[i] if i < len(self._paths) else old)
            if i in problems:
                item.setText(2, "⚠ " + problems[i])
                for c in range(3):
                    item.setForeground(c, QColor(ERROR))
            elif old == new:
                item.setForeground(1, QColor(TEXT_MUTED))
                item.setForeground(2, QColor(TEXT_MUTED))
                item.setText(2, "No change")
            else:
                changes += 1
                item.setForeground(1, QColor(ACCENT))
                item.setForeground(2, QColor(TEXT_SECONDARY))
                item.setText(2, "Will rename")
            items.append(item)
        self._table.addTopLevelItems(items)
        self._table.setUpdatesEnabled(True)
        if problems:
            self._summary_lbl.setText(
                f"{changes} to rename · {len(problems)} conflict(s)"
            )
            self._summary_lbl.setStyleSheet(f"color: {ERROR};")
        else:
            self._summary_lbl.setText(
                f"{changes} of {len(pairs)} file(s) will be renamed"
            )
            self._summary_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._apply_btn.setEnabled(changes > 0 and not problems)

    def _populate_apply_results(self, results: list):
        self._table.clear()
        for row in results:
            path, ok, msg = row[0], row[1], row[2]
            name = Path(path).name
            item = QTreeWidgetItem([name, msg, "✓" if ok else "✗"])
            item.setForeground(2, QColor(SUCCESS if ok else ERROR))
            if ok and msg != "No change.":
                item.setForeground(1, QColor(ACCENT))
            elif not ok:
                item.setForeground(1, QColor(ERROR))
            self._table.addTopLevelItem(item)
        self._apply_btn.setEnabled(False)
        self._summary_lbl.setText("Done — edit the pattern to preview another rename.")
        self._summary_lbl.setStyleSheet(f"color: {SUCCESS};")

    def _update_count(self):
        n = len(self._paths)
        self._file_count_lbl.setText(f"{n} file{'s' if n != 1 else ''}")
        self._remove_btn.setEnabled(n > 0)
        self._clear_list_btn.setEnabled(n > 0)
        self._preview_btn.setEnabled(n > 0)
        self._apply_btn.setEnabled(n > 0)

    @staticmethod
    def _card() -> QFrame:
        return Card()
