"""
tab_advanced.py — Advanced operations: truncate, zero, extended attributes,
                  symlink info, EXIF viewer, hex preview.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QScrollArea,
    QSpinBox, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QAbstractItemView, QTextEdit,
    QSplitter,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from modules.file_info import FileInfo
from modules.file_ops import truncate_file, zero_file
from modules.widgets import SectionLabel, StatusBanner
from modules.theme import BG_CARD, BORDER, TEXT_MUTED, ACCENT, TEXT_SECONDARY


class AdvancedTab(QWidget):
    file_changed = pyqtSignal(str)

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

        # ── Content operations ─────────────────────────────────────────
        layout.addWidget(SectionLabel("Content Operations"))
        content_card = self._card()
        cl = QVBoxLayout(content_card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(12)

        # Truncate
        trunc_row = QHBoxLayout()
        trunc_lbl = QLabel("Truncate to (bytes):")
        trunc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        trunc_lbl.setFixedWidth(160)
        self._trunc_spin = QSpinBox()
        self._trunc_spin.setRange(0, 2_147_483_647)
        self._trunc_spin.setSuffix(" bytes")
        self._trunc_spin.setFixedWidth(160)
        self._trunc_btn = QPushButton("Truncate")
        self._trunc_btn.clicked.connect(self._do_truncate)
        trunc_row.addWidget(trunc_lbl)
        trunc_row.addWidget(self._trunc_spin)
        trunc_row.addWidget(self._trunc_btn)
        trunc_row.addStretch()
        cl.addLayout(trunc_row)

        # Zero
        zero_row = QHBoxLayout()
        zero_info = QLabel("Empty file contents (set size to 0 bytes):")
        zero_info.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._zero_btn = QPushButton("Zero File")
        self._zero_btn.setObjectName("danger")
        self._zero_btn.clicked.connect(self._do_zero)
        zero_row.addWidget(zero_info)
        zero_row.addStretch()
        zero_row.addWidget(self._zero_btn)
        cl.addLayout(zero_row)

        layout.addWidget(content_card)

        # ── Hex preview ────────────────────────────────────────────────
        layout.addWidget(SectionLabel("Hex Preview  (first 512 bytes)"))
        hex_card = self._card()
        hl = QVBoxLayout(hex_card)
        hl.setContentsMargins(12, 8, 12, 8)
        self._hex_view = QTextEdit()
        self._hex_view.setReadOnly(True)
        self._hex_view.setFont(QFont("Courier New", 10))
        self._hex_view.setFixedHeight(180)
        self._hex_view.setStyleSheet(
            f"background: #0d0f12; color: #a0ffb0; border: none;"
        )
        self._hex_view.setPlaceholderText("Load a file to see hex preview…")
        hl.addWidget(self._hex_view)

        refresh_hex = QPushButton("Refresh Hex")
        refresh_hex.clicked.connect(self._load_hex)
        hl.addWidget(refresh_hex)
        layout.addWidget(hex_card)

        # ── Extended attributes ────────────────────────────────────────
        layout.addWidget(SectionLabel("Extended Attributes  (xattr)"))
        xattr_card = self._card()
        xl = QVBoxLayout(xattr_card)
        xl.setContentsMargins(12, 8, 12, 8)
        xl.setSpacing(8)

        self._xattr_tree = QTreeWidget()
        self._xattr_tree.setColumnCount(2)
        self._xattr_tree.setHeaderLabels(["Name", "Value"])
        self._xattr_tree.setAlternatingRowColors(True)
        self._xattr_tree.setFixedHeight(140)
        self._xattr_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        xl.addWidget(self._xattr_tree)

        xattr_note = QLabel("Extended attributes are only supported on Linux/macOS.")
        xattr_note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        xl.addWidget(xattr_note)
        layout.addWidget(xattr_card)

        # ── Symlink info ───────────────────────────────────────────────
        layout.addWidget(SectionLabel("Symlink Target"))
        sym_card = self._card()
        sl = QVBoxLayout(sym_card)
        sl.setContentsMargins(16, 12, 16, 12)
        self._sym_lbl = QLabel("—")
        self._sym_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._sym_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sl.addWidget(self._sym_lbl)
        layout.addWidget(sym_card)

        # ── EXIF viewer ────────────────────────────────────────────────
        layout.addWidget(SectionLabel("EXIF / Image Metadata"))
        exif_card = self._card()
        el = QVBoxLayout(exif_card)
        el.setContentsMargins(12, 8, 12, 8)
        self._exif_tree = QTreeWidget()
        self._exif_tree.setColumnCount(2)
        self._exif_tree.setHeaderLabels(["Tag", "Value"])
        self._exif_tree.setAlternatingRowColors(True)
        self._exif_tree.setFixedHeight(180)
        el.addWidget(self._exif_tree)
        layout.addWidget(exif_card)

        layout.addStretch()

        self._editable = [self._trunc_btn, self._trunc_spin, self._zero_btn]
        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        self._trunc_spin.setValue(info.size)
        self._load_hex()
        self._load_xattrs(info)
        self._load_symlink(info)
        self._load_exif(info)
        self._set_enabled(True)

    def clear(self):
        self._info = None
        self._hex_view.clear()
        self._xattr_tree.clear()
        self._exif_tree.clear()
        self._sym_lbl.setText("—")
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _do_truncate(self):
        if not self._info: return
        size = self._trunc_spin.value()
        reply = QMessageBox.question(
            self, "Confirm Truncate",
            f"Truncate '{self._info.name}' to {size:,} bytes?\nThis may destroy data.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes: return
        ok, msg = truncate_file(self._info.path, size)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self.file_changed.emit(self._info.path)

    def _do_zero(self):
        if not self._info: return
        reply = QMessageBox.question(
            self, "Confirm Zero",
            f"Empty '{self._info.name}'? ALL content will be deleted.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes: return
        ok, msg = zero_file(self._info.path)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self.file_changed.emit(self._info.path)

    def _load_hex(self):
        if not self._info: return
        try:
            with open(self._info.path, "rb") as f:
                data = f.read(512)
            lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i + 16]
                hex_part = " ".join(f"{b:02X}" for b in chunk)
                asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(f"{i:04X}  {hex_part:<47}  {asc_part}")
            self._hex_view.setPlainText("\n".join(lines))
        except Exception as e:
            self._hex_view.setPlainText(f"Error: {e}")

    def _load_xattrs(self, info: FileInfo):
        self._xattr_tree.clear()
        for name, val in info.xattrs.items():
            item = QTreeWidgetItem([name, val])
            self._xattr_tree.addTopLevelItem(item)
        if not info.xattrs:
            item = QTreeWidgetItem(["(none)", ""])
            item.setForeground(0, __import__("PyQt5.QtGui", fromlist=["QColor"]).QColor(TEXT_MUTED))
            self._xattr_tree.addTopLevelItem(item)

    def _load_symlink(self, info: FileInfo):
        if info.is_symlink:
            import os
            try:
                target = os.readlink(info.path)
                self._sym_lbl.setText(target)
            except Exception:
                self._sym_lbl.setText("(unreadable)")
        else:
            self._sym_lbl.setText("Not a symlink")

    def _load_exif(self, info: FileInfo):
        self._exif_tree.clear()
        if info.image_meta and info.image_meta.exif:
            for tag, val in info.image_meta.exif.items():
                item = QTreeWidgetItem([tag, str(val)[:120]])
                self._exif_tree.addTopLevelItem(item)
        else:
            from PyQt5.QtGui import QColor
            item = QTreeWidgetItem(["(no EXIF data)", ""])
            item.setForeground(0, QColor(TEXT_MUTED))
            self._exif_tree.addTopLevelItem(item)

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        for w in self._editable:
            w.setEnabled(en)

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        return f