"""
tab_rename.py — Rename, move, copy, extension change, hidden toggle.
"""

from __future__ import annotations
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox, QCheckBox,
    QFileDialog, QScrollArea, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal

from modules.file_info import FileInfo
from modules.file_ops import (
    rename_file, move_file, copy_file,
    change_extension, set_hidden,
)
from modules.widgets import SectionLabel, HSep, StatusBanner
from modules.theme import BG_CARD, BORDER, ACCENT, TEXT_SECONDARY


class RenameTab(QWidget):
    file_changed = pyqtSignal(str)   # emits new path after rename/move

    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # ── Rename ─────────────────────────────────────────────────────
        layout.addWidget(self._section("RENAME"))
        rename_group = self._card()
        gl = QVBoxLayout(rename_group)
        gl.setSpacing(10)

        gl.addWidget(QLabel("New filename (including extension):"))
        row = QHBoxLayout()
        self._rename_edit = QLineEdit()
        self._rename_edit.setPlaceholderText("e.g.  my_document.pdf")
        self._rename_btn = QPushButton("Rename")
        self._rename_btn.setObjectName("primary")
        self._rename_btn.clicked.connect(self._do_rename)
        row.addWidget(self._rename_edit, 1)
        row.addWidget(self._rename_btn)
        gl.addLayout(row)
        layout.addWidget(rename_group)

        # ── Extension ──────────────────────────────────────────────────
        layout.addWidget(self._section("CHANGE EXTENSION"))
        ext_group = self._card()
        el = QVBoxLayout(ext_group)
        el.setSpacing(10)

        el.addWidget(QLabel("New extension (e.g. .txt, .jpg):"))
        row2 = QHBoxLayout()
        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText(".txt")
        self._ext_edit.setFixedWidth(120)
        self._ext_btn = QPushButton("Change Extension")
        self._ext_btn.setObjectName("primary")
        self._ext_btn.clicked.connect(self._do_ext)
        row2.addWidget(self._ext_edit)
        row2.addWidget(self._ext_btn)
        row2.addStretch()
        el.addLayout(row2)
        layout.addWidget(ext_group)

        # ── Hidden ────────────────────────────────────────────────────
        layout.addWidget(self._section("VISIBILITY"))
        hid_group = self._card()
        hl = QVBoxLayout(hid_group)
        self._hidden_chk = QCheckBox("Mark file as hidden")
        self._hidden_btn = QPushButton("Apply Visibility")
        self._hidden_btn.setObjectName("primary")
        self._hidden_btn.clicked.connect(self._do_hidden)
        hrow = QHBoxLayout()
        hrow.addWidget(self._hidden_chk)
        hrow.addStretch()
        hrow.addWidget(self._hidden_btn)
        hl.addLayout(hrow)
        layout.addWidget(hid_group)

        # ── Move ──────────────────────────────────────────────────────
        layout.addWidget(self._section("MOVE FILE"))
        move_group = self._card()
        ml = QVBoxLayout(move_group)
        ml.setSpacing(10)

        ml.addWidget(QLabel("Destination directory:"))
        row3 = QHBoxLayout()
        self._move_edit = QLineEdit()
        self._move_edit.setPlaceholderText("/path/to/destination/")
        self._move_browse = QPushButton("Browse…")
        self._move_browse.clicked.connect(self._browse_move)
        self._move_btn = QPushButton("Move")
        self._move_btn.setObjectName("primary")
        self._move_btn.clicked.connect(self._do_move)
        row3.addWidget(self._move_edit, 1)
        row3.addWidget(self._move_browse)
        row3.addWidget(self._move_btn)
        ml.addLayout(row3)
        layout.addWidget(move_group)

        # ── Copy ──────────────────────────────────────────────────────
        layout.addWidget(self._section("COPY FILE"))
        copy_group = self._card()
        cl = QVBoxLayout(copy_group)
        cl.setSpacing(10)

        cl.addWidget(QLabel("Copy to (full path including filename):"))
        row4 = QHBoxLayout()
        self._copy_edit = QLineEdit()
        self._copy_edit.setPlaceholderText("/path/to/copy.txt")
        self._copy_browse = QPushButton("Browse…")
        self._copy_browse.clicked.connect(self._browse_copy)
        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("primary")
        self._copy_btn.clicked.connect(self._do_copy)
        row4.addWidget(self._copy_edit, 1)
        row4.addWidget(self._copy_browse)
        row4.addWidget(self._copy_btn)
        cl.addLayout(row4)
        layout.addWidget(copy_group)

        layout.addStretch()
        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        p = Path(info.path)
        self._rename_edit.setText(p.name)
        self._ext_edit.setText(p.suffix)
        self._hidden_chk.setChecked(info.is_hidden)
        self._set_enabled(True)

    def clear(self):
        self._info = None
        self._rename_edit.clear()
        self._ext_edit.clear()
        self._hidden_chk.setChecked(False)
        self._move_edit.clear()
        self._copy_edit.clear()
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _do_rename(self):
        if not self._info: return
        new_name = self._rename_edit.text().strip()
        if not new_name:
            self._banner.show_message("Enter a new filename.", "warning")
            return
        ok, msg = rename_file(self._info.path, new_name)
        if ok:
            new_path = str(Path(self._info.path).parent / new_name)
            self._banner.show_message(msg, "success")
            self.file_changed.emit(new_path)
        else:
            self._banner.show_message(msg, "error")

    def _do_ext(self):
        if not self._info: return
        ext = self._ext_edit.text().strip()
        if not ext:
            self._banner.show_message("Enter an extension.", "warning")
            return
        ok, msg = change_extension(self._info.path, ext)
        if ok:
            p = Path(self._info.path)
            new_ext = ext if ext.startswith(".") else "." + ext
            new_path = str(p.with_suffix(new_ext))
            self._banner.show_message(msg, "success")
            self.file_changed.emit(new_path)
        else:
            self._banner.show_message(msg, "error")

    def _do_hidden(self):
        if not self._info: return
        ok, msg = set_hidden(self._info.path, self._hidden_chk.isChecked())
        if ok:
            self._banner.show_message(msg, "success")
            # hidden toggle may rename, reload
            self.file_changed.emit(self._info.path)
        else:
            self._banner.show_message(msg, "error")

    def _do_move(self):
        if not self._info: return
        dest = self._move_edit.text().strip()
        if not dest:
            self._banner.show_message("Enter a destination directory.", "warning")
            return
        ok, msg = move_file(self._info.path, dest)
        if ok:
            self._banner.show_message(msg, "success")
            new_path = str(Path(dest) / Path(self._info.path).name)
            self.file_changed.emit(new_path)
        else:
            self._banner.show_message(msg, "error")

    def _do_copy(self):
        if not self._info: return
        dest = self._copy_edit.text().strip()
        if not dest:
            self._banner.show_message("Enter a destination path.", "warning")
            return
        ok, msg = copy_file(self._info.path, dest)
        self._banner.show_message(msg, "success" if ok else "error")

    def _browse_move(self):
        d = QFileDialog.getExistingDirectory(self, "Select destination directory")
        if d:
            self._move_edit.setText(d)

    def _browse_copy(self):
        if not self._info: return
        p = Path(self._info.path)
        dest, _ = QFileDialog.getSaveFileName(
            self, "Copy to…", str(p.parent / p.name)
        )
        if dest:
            self._copy_edit.setText(dest)

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        for w in [self._rename_btn, self._ext_btn, self._hidden_btn,
                  self._move_btn, self._copy_btn, self._rename_edit,
                  self._ext_edit, self._move_edit, self._copy_edit,
                  self._move_browse, self._copy_browse, self._hidden_chk]:
            w.setEnabled(en)

    @staticmethod
    def _section(title: str) -> SectionLabel:
        return SectionLabel(title)

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        return f