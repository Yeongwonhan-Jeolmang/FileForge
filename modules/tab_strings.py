"""
tab_strings.py — Display printable strings extracted from binary files.
"""

from __future__ import annotations
import re
import threading

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QComboBox,
    QSpinBox, QListView, QTextEdit, QFileDialog,
    QSplitter, QCheckBox, QProgressBar, QAbstractItemView, QApplication,
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QObject, QAbstractListModel, QModelIndex, QTimer, QVariant,
)
from PyQt5.QtGui import QFont, QColor

from modules.file_info import FileInfo
from modules.widgets import SectionLabel, StatusBanner, Card
from modules.theme import BG_CARD, BORDER, ACCENT, TEXT_SECONDARY, TEXT_MUTED, HEX_OFFSET
from modules.strings_extractor import extract_strings, filter_strings

MAX_STRINGS = 500_000


# ── Worker thread ─────────────────────────────────────────────────────────

class StringsWorker(QObject):
    progress = pyqtSignal(int)  # Progress percentage
    finished = pyqtSignal(list)  # List of (offset, string) tuples
    error = pyqtSignal(str)

    def __init__(self, file_path: str, min_length: int, encoding: str):
        super().__init__()
        self._file_path = file_path
        self._min_length = min_length
        self._encoding = encoding
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            self.progress.emit(10)
            strings = extract_strings(self._file_path, self._min_length, self._encoding,
                                      max_results=MAX_STRINGS, cancel_cb=self._stop.is_set)
            self.progress.emit(100)
            self.finished.emit(strings)
        except Exception as e:
            self.error.emit(str(e))


# ── Virtual list model ────────────────────────────────────────────────────

class _StringsModel(QAbstractListModel):
    """
    Holds every extracted string but only exposes the filtered subset.
    QListView asks only for visible rows, so 500k strings scroll smoothly —
    unlike QListWidget, which allocates a QListWidgetItem per row up front.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all: list[tuple[int, str]] = []
        self._rows: list[int] = []        # indexes into _all

    def set_strings(self, strings: list[tuple[int, str]]):
        self.beginResetModel()
        self._all = strings
        self._rows = list(range(len(strings)))
        self.endResetModel()

    def set_filter(self, indexes: list[int] | None):
        self.beginResetModel()
        self._rows = list(range(len(self._all))) if indexes is None else indexes
        self.endResetModel()

    def entry(self, row: int) -> tuple[int, str]:
        return self._all[self._rows[row]]

    def visible_entries(self):
        return (self._all[i] for i in self._rows)

    def total(self) -> int:
        return len(self._all)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        offset, string = self._all[self._rows[index.row()]]
        if role == Qt.DisplayRole:
            text = string if len(string) <= 160 else string[:160] + "…"
            return f"{offset:08X}  {text}"
        if role == Qt.ToolTipRole and len(string) > 160:
            return string[:2000]
        return QVariant()


# ── Tab ───────────────────────────────────────────────────────────────────

class StringsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None
        self._thread: QThread | None = None
        self._worker: StringsWorker | None = None
        self._all_strings: list = []
        self._extracted_params: tuple | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 18, 24, 18)
        bl.setSpacing(12)
        outer.addWidget(body, 1)

        # Controls
        controls_card = self._card()
        controls_layout = QHBoxLayout(controls_card)
        controls_layout.setContentsMargins(16, 10, 16, 10)
        controls_layout.setSpacing(12)

        # Min length
        controls_layout.addWidget(QLabel("Min length:"))
        self._min_length_spin = QSpinBox()
        self._min_length_spin.setRange(1, 100)
        self._min_length_spin.setValue(4)
        self._min_length_spin.valueChanged.connect(self._update_strings)
        controls_layout.addWidget(self._min_length_spin)

        # Encoding
        controls_layout.addWidget(QLabel("Encoding:"))
        self._encoding_combo = QComboBox()
        self._encoding_combo.addItems(["ascii", "utf-8", "utf-16", "latin-1"])
        self._encoding_combo.setToolTip("utf-16 = little-endian wide strings (common in Windows binaries)")
        self._encoding_combo.currentTextChanged.connect(self._update_strings)
        controls_layout.addWidget(self._encoding_combo)

        controls_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel)
        self._cancel_btn.hide()
        controls_layout.addWidget(self._cancel_btn)

        # Extract button
        self._extract_btn = QPushButton("Extract Strings")
        self._extract_btn.setObjectName("primary")
        self._extract_btn.setCursor(Qt.PointingHandCursor)
        self._extract_btn.clicked.connect(self._extract_strings)
        controls_layout.addWidget(self._extract_btn)

        bl.addWidget(controls_card)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)      # indeterminate: extraction is streamed
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        bl.addWidget(self._progress)

        # Search
        search_layout = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter strings (regex supported)…")
        self._search_edit.setClearButtonEnabled(True)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(220)
        self._filter_timer.timeout.connect(self._filter_strings)
        self._search_edit.textChanged.connect(lambda _: self._filter_timer.start())
        search_layout.addWidget(self._search_edit, 1)

        self._case_sensitive_chk = QCheckBox("Case sensitive")
        self._case_sensitive_chk.stateChanged.connect(self._filter_strings)
        search_layout.addWidget(self._case_sensitive_chk)

        self._export_btn = QPushButton("Export…")
        self._export_btn.setToolTip("Save the (filtered) strings to a text file")
        self._export_btn.clicked.connect(self._export)
        search_layout.addWidget(self._export_btn)
        bl.addLayout(search_layout)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        bl.addWidget(splitter, 1)

        # Strings list
        list_box = QWidget()
        list_layout = QVBoxLayout(list_box)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        list_layout.addWidget(self._count_lbl)

        self._model = _StringsModel(self)
        self._strings_list = QListView()
        self._strings_list.setModel(self._model)
        self._strings_list.setUniformItemSizes(True)     # big speed-up for long lists
        self._strings_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._strings_list.setAlternatingRowColors(True)
        self._strings_list.selectionModel().currentChanged.connect(lambda *_: self._on_string_selected())
        list_layout.addWidget(self._strings_list, 1)
        splitter.addWidget(list_box)

        # Details panel
        details_box = QWidget()
        details_layout = QVBoxLayout(details_box)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)
        details_header = QHBoxLayout()
        details_title = QLabel("STRING DETAILS")
        details_title.setObjectName("sectionLabel")
        details_header.addWidget(details_title)
        details_header.addStretch()
        self._copy_btn = QPushButton("Copy Selected")
        self._copy_btn.setObjectName("ghost")
        self._copy_btn.clicked.connect(self._copy_selected)
        details_header.addWidget(self._copy_btn)
        details_layout.addLayout(details_header)

        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setPlaceholderText("Select a string to see its offset, length and bytes.")
        details_layout.addWidget(self._details_text, 1)

        splitter.addWidget(details_box)
        splitter.setSizes([560, 360])

        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._cancel()
        self._info = info
        self._all_strings = []
        self._extracted_params = None
        self._model.set_strings([])
        self._details_text.clear()
        self._count_lbl.setText(f"Click “Extract Strings” to scan {info.name} ({info.size_human}).")
        self._set_enabled(True)

    def clear(self):
        self._cancel()
        self._info = None
        self._all_strings = []
        self._extracted_params = None
        self._model.set_strings([])
        self._details_text.clear()
        self._count_lbl.setText("")
        self._set_enabled(False)

    def shutdown(self):
        self._cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)

    # ── Slots ─────────────────────────────────────────────────────────

    def _extract_strings(self):
        if not self._info or self._thread is not None:
            return

        self._extract_btn.setEnabled(False)
        self._cancel_btn.show()
        self._progress.setVisible(True)
        self._banner.show_message("Extracting strings…", "info", 0)

        params = (self._min_length_spin.value(), self._encoding_combo.currentText())
        worker = StringsWorker(self._info.path, *params)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(lambda strings, p=params: self._on_strings_extracted(strings, p))
        worker.finished.connect(thread.quit)
        worker.error.connect(lambda e: self._banner.show_message(e, "error"))
        worker.error.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)

        self._worker = worker
        self._thread = thread
        thread.start()

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def _on_thread_finished(self):
        self._extract_btn.setEnabled(self._info is not None)
        self._cancel_btn.hide()
        self._progress.setVisible(False)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def _on_strings_extracted(self, strings: list, params: tuple = None):
        self._all_strings = strings
        self._extracted_params = params
        self._model.set_strings(strings)
        self._filter_strings()
        count = len(strings)
        capped = " (limit reached — raise Min length to narrow it down)" if count >= MAX_STRINGS else ""
        self._banner.show_message(f"Found {count:,} strings{capped}.", "success" if not capped else "warning")

    def _update_strings(self):
        """Encoding / min-length changed: offer to re-run (results no longer match)."""
        if self._extracted_params is None:
            return
        current = (self._min_length_spin.value(), self._encoding_combo.currentText())
        if current != self._extracted_params:
            self._extract_btn.setText("Re-extract Strings")
            self._count_lbl.setText("Settings changed — click “Re-extract Strings” to refresh the list.")
        else:
            self._extract_btn.setText("Extract Strings")
            self._update_count()

    def _update_strings_list(self):
        # Kept for compatibility: the model now owns the list contents
        self._model.set_strings(self._all_strings)
        self._filter_strings()

    def _filter_strings(self):
        search_text = self._search_edit.text()
        case_sensitive = self._case_sensitive_chk.isChecked()

        if not search_text:
            self._model.set_filter(None)
        else:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                pattern = re.compile(search_text, flags)
                match = pattern.search
            except re.error:
                needle = search_text if case_sensitive else search_text.lower()
                match = (lambda s: needle in s) if case_sensitive else (lambda s: needle in s.lower())
            self._model.set_filter([i for i, (_, s) in enumerate(self._all_strings) if match(s)])
        self._details_text.clear()
        self._update_count()
        if self._extracted_params is not None:
            self._extract_btn.setText("Extract Strings")

    def _update_count(self):
        total = self._model.total()
        shown = self._model.rowCount()
        if not total:
            self._count_lbl.setText("No strings found." if self._extracted_params else self._count_lbl.text())
        elif shown == total:
            self._count_lbl.setText(f"{total:,} strings")
        else:
            self._count_lbl.setText(f"{shown:,} of {total:,} strings match")

    def _on_string_selected(self):
        index = self._strings_list.currentIndex()
        if not index.isValid():
            self._details_text.clear()
            return

        offset, string = self._model.entry(index.row())
        encoding = self._extracted_params[1] if self._extracted_params else "ascii"
        codec = {"utf-16": "utf-16-le", "utf-8": "utf-8", "latin-1": "latin-1"}.get(encoding, "ascii")
        raw = string.encode(codec, errors="replace")
        hex_dump = raw[:512].hex(" ")
        more = f"\n… ({len(raw) - 512:,} more bytes)" if len(raw) > 512 else ""

        # Format details
        details = f"""Offset: 0x{offset:08X} ({offset:,} bytes)
Length: {len(string)} characters / {len(raw)} bytes ({encoding})

String:
{string}

Hex dump of string:
{hex_dump}{more}
"""

        self._details_text.setPlainText(details)

    def _copy_selected(self):
        rows = sorted(i.row() for i in self._strings_list.selectionModel().selectedIndexes())
        if not rows:
            return
        QApplication.clipboard().setText("\n".join(self._model.entry(r)[1] for r in rows))
        self._banner.show_message(f"Copied {len(rows)} string(s).", "info", 2000)

    def _export(self):
        if not self._model.rowCount() or not self._info:
            self._banner.show_message("Nothing to export — extract strings first.", "warning")
            return
        default = f"{self._info.name}.strings.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Export Strings", default, "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for offset, string in self._model.visible_entries():
                    f.write(f"{offset:08X}\t{string}\n")
            self._banner.show_message(f"Exported {self._model.rowCount():,} strings.", "success")
        except OSError as e:
            self._banner.show_message(str(e), "error")

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        self._extract_btn.setEnabled(en and self._thread is None)
        self._min_length_spin.setEnabled(en)
        self._encoding_combo.setEnabled(en)
        self._search_edit.setEnabled(en)
        self._case_sensitive_chk.setEnabled(en)
        self._export_btn.setEnabled(en)
        self._copy_btn.setEnabled(en)

    def _card(self):
        return Card()
