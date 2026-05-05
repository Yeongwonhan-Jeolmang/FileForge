"""
tab_strings.py — Display printable strings extracted from binary files.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QComboBox,
    QSpinBox, QListWidget, QListWidgetItem, QTextEdit,
    QSplitter, QCheckBox, QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

from modules.file_info import FileInfo
from modules.widgets import SectionLabel, StatusBanner
from modules.theme import BG_CARD, BORDER, ACCENT, TEXT_SECONDARY
from modules.strings_extractor import extract_strings, filter_strings


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

    def run(self):
        try:
            self.progress.emit(10)
            strings = extract_strings(self._file_path, self._min_length, self._encoding)
            self.progress.emit(100)
            self.finished.emit(strings)
        except Exception as e:
            self.error.emit(str(e))


# ── Tab ───────────────────────────────────────────────────────────────────

class StringsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None
        self._thread: QThread | None = None
        self._worker: StringsWorker | None = None
        self._all_strings: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        # Controls
        controls_card = self._card()
        controls_layout = QHBoxLayout(controls_card)
        controls_layout.setContentsMargins(16, 12, 16, 12)
        controls_layout.setSpacing(16)

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
        self._encoding_combo.currentTextChanged.connect(self._update_strings)
        controls_layout.addWidget(self._encoding_combo)

        # Extract button
        self._extract_btn = QPushButton("Extract Strings")
        self._extract_btn.setObjectName("primary")
        self._extract_btn.clicked.connect(self._extract_strings)
        controls_layout.addWidget(self._extract_btn)

        controls_layout.addStretch()
        outer.addWidget(controls_card)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        outer.addWidget(self._progress)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter)

        # Strings list
        list_frame = QFrame()
        list_frame.setFrameStyle(QFrame.StyledPanel)
        list_layout = QVBoxLayout(list_frame)

        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter strings...")
        self._search_edit.textChanged.connect(self._filter_strings)
        search_layout.addWidget(self._search_edit)

        self._case_sensitive_chk = QCheckBox("Case sensitive")
        self._case_sensitive_chk.stateChanged.connect(self._filter_strings)
        search_layout.addWidget(self._case_sensitive_chk)

        list_layout.addLayout(search_layout)

        self._strings_list = QListWidget()
        self._strings_list.itemSelectionChanged.connect(self._on_string_selected)
        list_layout.addWidget(self._strings_list)

        splitter.addWidget(list_frame)

        # Details panel
        details_frame = QFrame()
        details_frame.setFrameStyle(QFrame.StyledPanel)
        details_layout = QVBoxLayout(details_frame)

        details_layout.addWidget(QLabel("String Details:"))

        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setFontFamily("Consolas")
        self._details_text.setFontPointSize(9)
        details_layout.addWidget(self._details_text)

        splitter.addWidget(details_frame)

        splitter.setSizes([400, 400])

        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        self._all_strings = []
        self._strings_list.clear()
        self._details_text.clear()
        self._set_enabled(True)

    def clear(self):
        self._info = None
        self._all_strings = []
        self._strings_list.clear()
        self._details_text.clear()
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _extract_strings(self):
        if not self._info:
            return

        self._extract_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._banner.show_message("Extracting strings…")

        worker = StringsWorker(
            self._info.path,
            self._min_length_spin.value(),
            self._encoding_combo.currentText()
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._progress.setValue)
        worker.finished.connect(self._on_strings_extracted)
        worker.finished.connect(thread.quit)
        worker.error.connect(lambda e: self._banner.show_message(e, "error"))
        worker.error.connect(thread.quit)
        thread.finished.connect(lambda: self._extract_btn.setEnabled(True))
        thread.finished.connect(lambda: self._progress.setVisible(False))

        self._worker = worker
        self._thread = thread
        thread.start()

    def _on_strings_extracted(self, strings: list):
        self._all_strings = strings
        self._update_strings_list()
        count = len(strings)
        self._banner.show_message(f"Found {count} strings.", "success")

    def _update_strings(self):
        if self._all_strings:
            self._update_strings_list()

    def _update_strings_list(self):
        self._strings_list.clear()
        strings = self._all_strings

        # Apply current filters
        min_len = self._min_length_spin.value()
        encoding = self._encoding_combo.currentText()

        # Re-extract if parameters changed
        if (not strings or
            (hasattr(self, '_current_min_len') and self._current_min_len != min_len) or
            (hasattr(self, '_current_encoding') and self._current_encoding != encoding)):
            self._extract_strings()
            return

        self._current_min_len = min_len
        self._current_encoding = encoding

        for offset, string in strings:
            item_text = f"{offset:08X}: {string[:100]}{'...' if len(string) > 100 else ''}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, (offset, string))
            self._strings_list.addItem(item)

    def _filter_strings(self):
        search_text = self._search_edit.text()
        case_sensitive = self._case_sensitive_chk.isChecked()

        if not search_text:
            # Show all
            for i in range(self._strings_list.count()):
                self._strings_list.item(i).setHidden(False)
        else:
            filtered = filter_strings(self._all_strings, search_text, case_sensitive)
            filtered_offsets = {offset for offset, _ in filtered}

            for i in range(self._strings_list.count()):
                item = self._strings_list.item(i)
                offset, _ = item.data(Qt.UserRole)
                item.setHidden(offset not in filtered_offsets)

    def _on_string_selected(self):
        current_item = self._strings_list.currentItem()
        if not current_item:
            self._details_text.clear()
            return

        offset, string = current_item.data(Qt.UserRole)

        # Format details
        details = f"""Offset: 0x{offset:08X} ({offset:,} bytes)
Length: {len(string)} characters

String:
{string}

Hex dump of string:
{string.encode('utf-8', errors='replace').hex(' ')}
"""

        self._details_text.setPlainText(details)

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        self._extract_btn.setEnabled(en)
        self._min_length_spin.setEnabled(en)
        self._encoding_combo.setEnabled(en)
        self._search_edit.setEnabled(en)
        self._case_sensitive_chk.setEnabled(en)

    def _card(self):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER};"
            f"border-radius: 6px; }}"
        )
        return frame