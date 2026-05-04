"""
widgets.py — Reusable PyQt5 widget components for FileForge.
"""

from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QFrame, QSizePolicy, QProgressBar, QGraphicsOpacityEffect,
)
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtProperty,
    QTimer, pyqtSignal,
)
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont
from modules.theme import (
    ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BG_CARD, BG_MID, BORDER, SUCCESS, ERROR, WARNING,
)


# ── Horizontal separator ───────────────────────────────────────────────────

class HSep(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {BORDER};")


# ── Section header label ───────────────────────────────────────────────────

class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setObjectName("subheading")
        self.setFixedHeight(20)


# ── Key/Value row ──────────────────────────────────────────────────────────

class KVRow(QWidget):
    """A label + value pair laid out horizontally."""

    def __init__(self, key: str, value: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(12)

        self._key_lbl = QLabel(key + ":")
        self._key_lbl.setObjectName("subheading")
        self._key_lbl.setFixedWidth(140)
        self._key_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._val_lbl = QLabel(value)
        self._val_lbl.setObjectName("value")
        self._val_lbl.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self._val_lbl.setWordWrap(True)

        layout.addWidget(self._key_lbl)
        layout.addWidget(self._val_lbl, 1)

    def set_value(self, v: str):
        self._val_lbl.setText(v)

    def set_value_color(self, color: str):
        self._val_lbl.setStyleSheet(f"color: {color};")


# ── Tag chip ───────────────────────────────────────────────────────────────

class TagChip(QLabel):
    def __init__(self, text: str, color: str = ACCENT, parent=None):
        super().__init__(f"  {text}  ", parent)
        self.setStyleSheet(
            f"background: {color}22; color: {color}; border: 1px solid {color}55;"
            f"border-radius: 10px; padding: 2px 6px; font-size: 11px;"
        )


# ── Status banner (slides in/out) ──────────────────────────────────────────

class StatusBanner(QWidget):
    """Animated status banner that auto-dismisses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        self._icon = QLabel("●")
        self._icon.setFixedWidth(16)
        self._msg = QLabel()
        self._msg.setFont(QFont("Consolas", 11))
        self._dismiss = QPushButton("×")
        self._dismiss.setFixedSize(22, 22)
        self._dismiss.clicked.connect(self.hide)
        self._dismiss.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: none; font-size: 14px; }"
            "QPushButton:hover { color: white; }"
        )

        layout.addWidget(self._icon)
        layout.addWidget(self._msg, 1)
        layout.addWidget(self._dismiss)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.hide()

    def show_message(self, msg: str, level: str = "success", auto_hide_ms: int = 4000):
        color_map = {"success": SUCCESS, "error": ERROR, "warning": WARNING, "info": ACCENT}
        color = color_map.get(level, ACCENT)
        self._icon.setStyleSheet(f"color: {color};")
        self._msg.setStyleSheet(f"color: {color};")
        self.setStyleSheet(f"background: {color}18; border-bottom: 1px solid {color}44;")
        self._msg.setText(msg)
        self.show()
        if auto_hide_ms > 0:
            self._timer.start(auto_hide_ms)


# ── Animated progress overlay ─────────────────────────────────────────────

class HashProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._label = QLabel("Computing hashes…")
        self._label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setFixedHeight(5)

        layout.addWidget(self._label)
        layout.addWidget(self._bar)
        self.hide()

    def start(self, label: str = "Computing hashes…"):
        self._label.setText(label)
        self._bar.setValue(0)
        self.show()

    def update(self, done: int, total: int):
        pct = int(done / total * 100) if total else 0
        self._bar.setValue(pct)

    def finish(self):
        self._bar.setValue(100)
        QTimer.singleShot(600, self.hide)


# ── Icon badge ────────────────────────────────────────────────────────────

_KIND_ICONS = {
    "image":    "🖼",
    "audio":    "🎵",
    "video":    "🎬",
    "text":     "📄",
    "document": "📑",
    "archive":  "📦",
    "other":    "📁",
}

def kind_icon(kind: str) -> str:
    return _KIND_ICONS.get(kind, "📁")


# ── Clickable label ───────────────────────────────────────────────────────

class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# ── Permission toggle button ──────────────────────────────────────────────

class PermToggle(QPushButton):
    """A small toggle button for a single permission bit."""

    def __init__(self, letter: str, active: bool = False, parent=None):
        super().__init__(letter, parent)
        self.setCheckable(True)
        self.setChecked(active)
        self.setFixedSize(28, 28)
        self._update_style()
        self.toggled.connect(lambda _: self._update_style())

    def _update_style(self):
        if self.isChecked():
            self.setStyleSheet(
                f"QPushButton {{ background: {ACCENT}; color: #000; border-radius: 4px;"
                f"font-weight: bold; font-size: 12px; border: none; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background: {BG_MID}; color: {TEXT_MUTED}; border-radius: 4px;"
                f"font-size: 12px; border: 1px solid {BORDER}; }}"
                f"QPushButton:hover {{ border-color: {ACCENT}; color: {TEXT_PRIMARY}; }}"
            )