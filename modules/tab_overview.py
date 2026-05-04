"""
tab_overview.py — "Overview" tab: summary cards for a loaded file.
"""

from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt
from modules.file_info import FileInfo
from modules.widgets import KVRow, SectionLabel, HSep, TagChip, kind_icon
from modules.theme import (
    BG_PANEL, BG_CARD, ACCENT, TEXT_PRIMARY, TEXT_SECONDARY,
    BORDER, SUCCESS, ERROR, BG_HOVER,
)


class OverviewTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(16)
        self._layout.addStretch()

        self._rows: list[KVRow] = []

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._clear()
        self._build(info)

    def clear(self):
        self._clear()

    # ── Private ────────────────────────────────────────────────────────

    def _clear(self):
        while self._layout.count() > 1:  # keep the stretch
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_section(self, title: str):
        lbl = SectionLabel(title)
        self._layout.insertWidget(self._layout.count() - 1, lbl)
        sep = HSep()
        self._layout.insertWidget(self._layout.count() - 1, sep)

    def _add_card(self, widget: QWidget):
        self._layout.insertWidget(self._layout.count() - 1, widget)

    def _build(self, info: FileInfo):
        # ── Hero banner ────────────────────────────────────────────────
        hero = self._make_hero(info)
        self._add_card(hero)

        # ── Basic info ─────────────────────────────────────────────────
        self._add_section("Identity")
        card = self._make_card([
            ("Name",      info.name),
            ("Full Path", info.path),
            ("Size",      f"{info.size_human}  ({info.size:,} bytes)"),
            ("MIME Type", info.mime_type),
            ("Kind",      info.kind.capitalize()),
        ])
        self._add_card(card)

        # ── Timestamps ─────────────────────────────────────────────────
        self._add_section("Timestamps")
        card = self._make_card([
            ("Modified", info.modified_str),
            ("Accessed", info.accessed_str),
            ("Created",  info.created_str),
        ])
        self._add_card(card)

        # ── Permissions ────────────────────────────────────────────────
        self._add_section("Permissions")
        perm = info.permissions
        card = self._make_card([
            ("Mode (symbolic)", perm.symbolic),
            ("Mode (octal)",    perm.octal),
            ("Owner",           info.owner),
            ("Group",           info.group),
        ])
        self._add_card(card)

        # ── Flags ─────────────────────────────────────────────────────
        flags_row = QHBoxLayout()
        flags_row.setSpacing(8)
        if info.is_symlink:
            flags_row.addWidget(TagChip("Symlink", ACCENT))
        if info.is_hidden:
            flags_row.addWidget(TagChip("Hidden", "#8888ff"))
        flags_row.addStretch()
        w = QWidget()
        w.setLayout(flags_row)
        self._add_card(w)

        # ── Image metadata ─────────────────────────────────────────────
        if info.image_meta:
            im = info.image_meta
            self._add_section("Image Properties")
            rows = [
                ("Dimensions", f"{im.width} × {im.height} px"),
                ("Color Mode", im.mode),
                ("Format",     im.format),
            ]
            if im.dpi:
                rows.append(("DPI", f"{im.dpi[0]:.0f} × {im.dpi[1]:.0f}"))
            if im.has_exif:
                rows.append(("EXIF Data", f"{len(im.exif)} tags present"))
            card = self._make_card(rows)
            self._add_card(card)

        # ── Audio metadata ─────────────────────────────────────────────
        if info.audio_meta:
            am = info.audio_meta
            self._add_section("Audio Properties")
            rows = []
            if am.duration:
                mins, secs = divmod(int(am.duration), 60)
                rows.append(("Duration", f"{mins}:{secs:02d}"))
            if am.bitrate:
                rows.append(("Bitrate", f"{am.bitrate:,} bps"))
            if am.sample_rate:
                rows.append(("Sample Rate", f"{am.sample_rate:,} Hz"))
            if am.channels:
                rows.append(("Channels", str(am.channels)))
            for k, v in list(am.tags.items())[:8]:
                rows.append((k.capitalize(), v))
            if rows:
                card = self._make_card(rows)
                self._add_card(card)

        # ── Extended attributes ────────────────────────────────────────
        if info.xattrs:
            self._add_section("Extended Attributes")
            rows = [(k, v) for k, v in info.xattrs.items()]
            card = self._make_card(rows)
            self._add_card(card)

    # ── Builders ───────────────────────────────────────────────────────

    def _make_hero(self, info: FileInfo) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER};"
            f"border-radius: 6px; }}"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(20)

        icon_lbl = QLabel(kind_icon(info.kind))
        icon_lbl.setStyleSheet("font-size: 40px; background: transparent; border: none;")
        icon_lbl.setFixedSize(56, 56)
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        name_lbl = QLabel(info.name)
        name_lbl.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {TEXT_PRIMARY};"
            f"background: transparent; border: none;"
        )
        name_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)

        sub_lbl = QLabel(f"{info.size_human}  ·  {info.mime_type}")
        sub_lbl.setStyleSheet(
            f"font-size: 11px; color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )

        text_col.addWidget(name_lbl)
        text_col.addWidget(sub_lbl)
        layout.addLayout(text_col, 1)

        return frame

    def _make_card(self, rows: list[tuple[str, str]]) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER};"
            f"border-radius: 6px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(0)

        for key, val in rows:
            row = KVRow(key, val)
            layout.addWidget(row)

        return frame