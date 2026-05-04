"""
tab_audio.py — Edit audio metadata tags (via mutagen).
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QScrollArea,
    QFormLayout, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal

from modules.file_info import FileInfo
from modules.file_ops import write_audio_tags, delete_audio_tags
from modules.widgets import SectionLabel, StatusBanner
from modules.theme import BG_CARD, BORDER, TEXT_SECONDARY, TEXT_MUTED, ACCENT


# Standard ID3 / Vorbis tags (easy interface names)
COMMON_TAGS = [
    ("title",        "Title"),
    ("artist",       "Artist"),
    ("albumartist",  "Album Artist"),
    ("album",        "Album"),
    ("date",         "Year"),
    ("tracknumber",  "Track #"),
    ("discnumber",   "Disc #"),
    ("genre",        "Genre"),
    ("composer",     "Composer"),
    ("comment",      "Comment"),
    ("copyright",    "Copyright"),
    ("encodedby",    "Encoded By"),
    ("language",     "Language"),
    ("lyricist",     "Lyricist"),
    ("organization", "Label"),
    ("website",      "Website"),
]


class AudioTab(QWidget):
    file_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None
        self._fields: dict[str, QLineEdit] = {}

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

        # ── Not-audio note ─────────────────────────────────────────────
        self._not_audio_lbl = QLabel(
            "ℹ  Audio tag editing is only available for audio files\n"
            "(MP3, FLAC, OGG, M4A, etc.)."
        )
        self._not_audio_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        self._not_audio_lbl.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self._not_audio_lbl)

        # ── Tag form ───────────────────────────────────────────────────
        layout.addWidget(SectionLabel("Common Tags"))
        form_card = self._card()
        form = QFormLayout(form_card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        for key, label in COMMON_TAGS:
            field = QLineEdit()
            field.setPlaceholderText(f"Enter {label.lower()}…")
            self._fields[key] = field
            lbl = QLabel(label + ":")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            form.addRow(lbl, field)

        layout.addWidget(form_card)

        # ── Buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("💾  Save Tags")
        self._save_btn.setObjectName("primary")
        self._save_btn.clicked.connect(self._save)

        self._clear_btn = QPushButton("Clear Fields")
        self._clear_btn.clicked.connect(self._clear_fields)

        self._delete_btn = QPushButton("Delete All Tags")
        self._delete_btn.setObjectName("danger")
        self._delete_btn.clicked.connect(self._delete_all)

        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._delete_btn)
        layout.addLayout(btn_row)

        layout.addStretch()
        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        is_audio = (info.kind == "audio")
        self._not_audio_lbl.setVisible(not is_audio)

        # Populate from existing tags
        for field in self._fields.values():
            field.clear()

        if is_audio and info.audio_meta and info.audio_meta.tags:
            for key, field in self._fields.items():
                val = info.audio_meta.tags.get(key, "")
                field.setText(val)

        self._set_enabled(is_audio)

    def clear(self):
        self._info = None
        for f in self._fields.values():
            f.clear()
        self._not_audio_lbl.setVisible(True)
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _save(self):
        if not self._info: return
        tags = {k: v.text().strip() for k, v in self._fields.items() if v.text().strip()}
        if not tags:
            self._banner.show_message("No tags to save.", "warning")
            return
        ok, msg = write_audio_tags(self._info.path, tags)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self.file_changed.emit(self._info.path)

    def _clear_fields(self):
        for f in self._fields.values():
            f.clear()

    def _delete_all(self):
        if not self._info: return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete ALL audio tags from this file? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok, msg = delete_audio_tags(self._info.path)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            for f in self._fields.values():
                f.clear()
            self.file_changed.emit(self._info.path)

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        for f in self._fields.values():
            f.setEnabled(en)
        self._save_btn.setEnabled(en)
        self._clear_btn.setEnabled(en)
        self._delete_btn.setEnabled(en)

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        return f