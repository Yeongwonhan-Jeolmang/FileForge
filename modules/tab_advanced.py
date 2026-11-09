"""
tab_advanced.py — Advanced operations: truncate, zero, extended attributes,
                  symlink info, EXIF viewer, hex preview.
"""

from __future__ import annotations
import os

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QAbstractItemView,
    QPlainTextEdit,
    QComboBox,
    QHeaderView,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFontDatabase

from modules.file_info import FileInfo
from modules.file_ops import truncate_file, zero_file
from modules.widgets import SectionLabel, StatusBanner, Card
from modules.theme import BORDER, TEXT_MUTED, TEXT_SECONDARY, HEX_BG, HEX_FG
from modules.file_info import human_size


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

        # ── Hex viewer (paged) ─────────────────────────────────────────
        layout.addWidget(SectionLabel("Hex Viewer"))
        hex_card = self._card()
        hl = QVBoxLayout(hex_card)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(8)

        nav = QHBoxLayout()
        nav.setSpacing(6)
        nav.addWidget(QLabel("Offset:"))
        self._hex_offset_edit = QLineEdit("0x0")
        self._hex_offset_edit.setFixedWidth(130)
        self._hex_offset_edit.setToolTip(
            "Hex (0x1F0) or decimal (496). Press Enter to jump."
        )
        self._hex_offset_edit.returnPressed.connect(self._jump_hex)
        nav.addWidget(self._hex_offset_edit)
        self._hex_page_combo = QComboBox()
        for size in (256, 512, 1024, 4096, 16384):
            self._hex_page_combo.addItem(f"{size:,} bytes", size)
        self._hex_page_combo.setCurrentIndex(2)
        self._hex_page_combo.currentIndexChanged.connect(lambda _: self._load_hex())
        self._hex_page_combo.setMinimumWidth(110)
        nav.addWidget(self._hex_page_combo)
        self._hex_first = QPushButton("«")
        self._hex_prev = QPushButton("◀ Prev")
        self._hex_next = QPushButton("Next ▶")
        self._hex_last = QPushButton("»")
        self._hex_first.setToolTip("Start of file")
        self._hex_last.setToolTip("End of file")
        self._hex_first.clicked.connect(lambda: self._goto_hex(0))
        self._hex_prev.clicked.connect(
            lambda: self._goto_hex(self._hex_offset - self._page_size())
        )
        self._hex_next.clicked.connect(
            lambda: self._goto_hex(self._hex_offset + self._page_size())
        )
        self._hex_last.clicked.connect(lambda: self._goto_hex(self._last_page_offset()))
        for b in (self._hex_first, self._hex_prev, self._hex_next, self._hex_last):
            nav.addWidget(b)
        nav.addStretch()
        self._hex_pos_lbl = QLabel("")
        self._hex_pos_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        nav.addWidget(self._hex_pos_lbl)
        hl.addLayout(nav)

        self._hex_view = QPlainTextEdit()
        self._hex_view.setReadOnly(True)
        self._hex_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        mono.setPointSize(10)
        self._hex_view.setFont(mono)
        self._hex_view.setMinimumHeight(300)
        self._hex_view.setStyleSheet(
            f"QPlainTextEdit {{ background: {HEX_BG}; color: {HEX_FG}; border: 1px solid {BORDER};"
            f"border-radius: 6px; padding: 8px; font-family: monospace; }}"
        )
        self._hex_view.setPlaceholderText("Load a file to see hex preview…")
        hl.addWidget(self._hex_view)

        refresh_hex = QPushButton("Refresh Hex")
        refresh_hex.clicked.connect(self._load_hex)
        hl.addWidget(refresh_hex, 0, Qt.AlignRight)
        self._hex_offset = 0
        self._hex_nav = [
            self._hex_offset_edit,
            self._hex_page_combo,
            self._hex_first,
            self._hex_prev,
            self._hex_next,
            self._hex_last,
            refresh_hex,
        ]
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
        self._xattr_tree.setMinimumHeight(120)
        self._xattr_tree.setRootIsDecorated(False)
        self._xattr_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
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
        self._exif_tree.setMinimumHeight(200)
        self._exif_tree.setRootIsDecorated(False)
        self._exif_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        el.addWidget(self._exif_tree)
        layout.addWidget(exif_card)

        layout.addStretch()

        self._editable = [
            self._trunc_btn,
            self._trunc_spin,
            self._zero_btn,
        ] + self._hex_nav
        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        self._trunc_spin.setValue(min(info.size, self._trunc_spin.maximum()))
        self._hex_offset = 0
        self._load_hex()
        self._load_xattrs(info)
        self._load_symlink(info)
        self._load_exif(info)
        self._set_enabled(True)

    def clear(self):
        self._info = None
        self._hex_view.clear()
        self._hex_pos_lbl.setText("")
        self._hex_offset = 0
        self._xattr_tree.clear()
        self._exif_tree.clear()
        self._sym_lbl.setText("—")
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _do_truncate(self):
        if not self._info:
            return
        size = self._trunc_spin.value()
        reply = QMessageBox.question(
            self,
            "Confirm Truncate",
            f"Truncate '{self._info.name}' to {size:,} bytes?\nThis may destroy data.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok, msg = truncate_file(self._info.path, size)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self.file_changed.emit(self._info.path)

    def _do_zero(self):
        if not self._info:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Zero",
            f"Empty '{self._info.name}'? ALL content will be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok, msg = zero_file(self._info.path)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self.file_changed.emit(self._info.path)

    def _page_size(self) -> int:
        return int(self._hex_page_combo.currentData() or 1024)

    def _last_page_offset(self) -> int:
        if not self._info:
            return 0
        page = self._page_size()
        size = self._file_size()
        return max(0, ((size - 1) // page) * page) if size else 0

    def _file_size(self) -> int:
        try:
            return os.path.getsize(self._info.path) if self._info else 0
        except OSError:
            return self._info.size if self._info else 0

    def _goto_hex(self, offset: int):
        self._hex_offset = max(0, min(offset, self._last_page_offset()))
        self._load_hex()

    def _jump_hex(self):
        text = self._hex_offset_edit.text().strip().lower().replace("_", "")
        try:
            offset = int(text, 16) if text.startswith("0x") else int(text)
        except ValueError:
            self._banner.show_message(f"Invalid offset: '{text}'", "warning")
            return
        # Align to 16 so columns stay readable
        self._goto_hex(offset - offset % 16)

    def _load_hex(self):
        if not self._info:
            return
        page = self._page_size()
        try:
            with open(self._info.path, "rb") as f:
                f.seek(self._hex_offset)
                data = f.read(page)
            size = self._file_size()
            width = max(8, len(f"{size:X}"))
            lines = []
            for i in range(0, len(data), 16):
                chunk = data[i : i + 16]
                hex_bytes = [f"{b:02X}" for b in chunk]
                # Gap after 8 bytes, like xxd / hexdump -C
                hex_part = " ".join(hex_bytes[:8]) + "  " + " ".join(hex_bytes[8:])
                asc_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(
                    f"{self._hex_offset + i:0{width}X}  {hex_part:<48}  |{asc_part}|"
                )
            self._hex_view.setPlainText("\n".join(lines) if lines else "(end of file)")
            end = self._hex_offset + len(data)
            self._hex_offset_edit.setText(f"0x{self._hex_offset:X}")
            self._hex_pos_lbl.setText(
                f"0x{self._hex_offset:X}–0x{max(end - 1, 0):X}  of  {size:,} bytes ({human_size(size)})"
            )
            self._hex_prev.setEnabled(self._hex_offset > 0)
            self._hex_first.setEnabled(self._hex_offset > 0)
            self._hex_next.setEnabled(end < size)
            self._hex_last.setEnabled(end < size)
        except Exception as e:
            self._hex_view.setPlainText(f"Error: {e}")

    def _load_xattrs(self, info: FileInfo):
        self._xattr_tree.clear()
        for name, val in info.xattrs.items():
            item = QTreeWidgetItem([name, val])
            self._xattr_tree.addTopLevelItem(item)
        if not info.xattrs:
            item = QTreeWidgetItem(["(none)", ""])
            item.setForeground(0, QColor(TEXT_MUTED))
            self._xattr_tree.addTopLevelItem(item)

    def _load_symlink(self, info: FileInfo):
        if info.is_symlink:
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
            item = QTreeWidgetItem(["(no EXIF data)", ""])
            item.setForeground(0, QColor(TEXT_MUTED))
            self._exif_tree.addTopLevelItem(item)

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        for w in self._editable:
            w.setEnabled(en)

    @staticmethod
    def _card() -> QFrame:
        return Card()
