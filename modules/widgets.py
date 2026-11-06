"""
widgets.py — Reusable PyQt5 widget components for FileForge.
"""

from __future__ import annotations
from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QFrame, QSizePolicy, QProgressBar, QGraphicsOpacityEffect,
    QApplication,
)
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtProperty,
    QTimer, pyqtSignal, QRectF, QSize,
)
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath
from modules.theme import (
    ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BG_CARD, BG_MID, BORDER, SUCCESS, ERROR, WARNING, INFO,
    ON_ACCENT, rgba, entropy_color,
)


# ── Card container ─────────────────────────────────────────────────────────

class Card(QFrame):
    """
    Rounded panel used throughout the app.

    Styled via the global stylesheet (QFrame#card) instead of an inline
    "QFrame { border… }" rule — inline rules cascade into every child QLabel
    (QLabel is a QFrame subclass) and draw a box around each label.
    """

    def __init__(self, parent=None, object_name: str = "card"):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WA_StyledBackground, True)


def make_card() -> Card:
    return Card()


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
        self.setObjectName("sectionLabel")
        self.setFixedHeight(20)


# ── Key/Value row ──────────────────────────────────────────────────────────

class KVRow(QWidget):
    """A label + value pair laid out horizontally."""

    def __init__(self, key: str, value: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(14)

        self._key_lbl = QLabel(key)
        self._key_lbl.setObjectName("subheading")
        self._key_lbl.setFixedWidth(140)
        self._key_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self._key_lbl.setContentsMargins(0, 2, 0, 0)

        self._val_lbl = QLabel(value)
        self._val_lbl.setObjectName("value")
        self._val_lbl.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self._val_lbl.setWordWrap(True)
        self._val_lbl.setToolTip("Select to copy")

        layout.addWidget(self._key_lbl)
        layout.addWidget(self._val_lbl, 1)

    def set_value(self, v: str):
        self._val_lbl.setText(v)

    def set_value_color(self, color: str):
        self._val_lbl.setStyleSheet(f"color: {color};")


# ── Tag chip ───────────────────────────────────────────────────────────────

class TagChip(QLabel):
    def __init__(self, text: str, color: str = ACCENT, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"background: {rgba(color, 0.13)}; color: {color}; border: 1px solid {rgba(color, 0.35)};"
            f"border-radius: 9px; padding: 2px 10px; font-size: 11px;"
        )
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)


# ── Status banner (slides in/out) ──────────────────────────────────────────

class StatusBanner(QWidget):
    """Animated status banner that auto-dismisses."""

    _ICONS = {"success": "✓", "error": "✕", "warning": "!", "info": "i"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(10)

        self._icon = QLabel("●")
        self._icon.setFixedSize(18, 18)
        self._icon.setAlignment(Qt.AlignCenter)
        self._msg = QLabel()
        self._msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._dismiss = QPushButton("×")
        self._dismiss.setFixedSize(24, 24)
        self._dismiss.setCursor(Qt.PointingHandCursor)
        self._dismiss.clicked.connect(self.hide)
        self._dismiss.setToolTip("Dismiss")

        layout.addWidget(self._icon)
        layout.addWidget(self._msg, 1)
        layout.addWidget(self._dismiss)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.hide()

    def show_message(self, msg: str, level: str = "success", auto_hide_ms: int = 4000):
        color_map = {"success": SUCCESS, "error": ERROR, "warning": WARNING, "info": INFO}
        color = color_map.get(level, ACCENT)
        self._icon.setText(self._ICONS.get(level, "●"))
        self._icon.setStyleSheet(
            f"color: {ON_ACCENT}; background: {color}; border-radius: 9px;"
            f"font-weight: bold; font-size: 11px;"
        )
        self._msg.setStyleSheet(f"color: {color}; background: transparent;")
        self._dismiss.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {color}; border: none; font-size: 16px; padding: 0; }}"
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
        )
        self.setStyleSheet(
            f"StatusBanner {{ background: {rgba(color, 0.10)}; border-bottom: 1px solid {rgba(color, 0.30)}; }}"
        )
        self._msg.setText(msg)
        self._msg.setToolTip(msg)
        self.show()
        # Errors stay a little longer so they can actually be read
        if level == "error" and auto_hide_ms > 0:
            auto_hide_ms = max(auto_hide_ms, 7000)
        if auto_hide_ms > 0:
            self._timer.start(auto_hide_ms)
        else:
            self._timer.stop()


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
        self._bar.setFixedHeight(6)
        self._bar.setTextVisible(False)

        layout.addWidget(self._label)
        layout.addWidget(self._bar)
        self.hide()

    def start(self, label: str = "Computing hashes…"):
        self._label.setText(label)
        self._bar.setValue(0)
        self.show()

    def set_progress(self, done: int, total: int):
        pct = int(done / total * 100) if total else 0
        self._bar.setValue(pct)

    def set_label(self, text: str):
        self._label.setText(text)

    def finish(self):
        self._bar.setValue(100)
        QTimer.singleShot(600, self.hide)


# ── Entropy profile graph ─────────────────────────────────────────────────

class EntropyGraph(QWidget):
    """
    Bar chart of entropy across the file (0–8 bits/byte per region).
    Bars are coloured by entropy level so packed / encrypted regions stand out.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(76)
        self.setMouseTracking(True)

    def set_values(self, values: list[float]):
        self._values = list(values)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(400, 76)

    def mouseMoveEvent(self, event):
        if not self._values:
            return
        idx = int(event.x() / max(1, self.width()) * len(self._values))
        idx = max(0, min(idx, len(self._values) - 1))
        pct = idx / len(self._values) * 100
        self.setToolTip(f"Region {idx + 1}/{len(self._values)}  (~{pct:.0f}% into file)\n"
                        f"{self._values[idx]:.2f} bits/byte")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        # Background + guide lines at 4 and 7 bits/byte
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(QColor(BG_MID))
        p.drawRoundedRect(rect, 6, 6)
        h = rect.height() - 8
        for level in (4.0, 7.0):
            y = rect.bottom() - 4 - h * level / 8.0
            pen = QPen(QColor(BORDER), 1, Qt.DashLine)
            p.setPen(pen)
            p.drawLine(int(rect.left() + 4), int(y), int(rect.right() - 4), int(y))

        if not self._values:
            p.setPen(QColor(TEXT_MUTED))
            p.drawText(rect, Qt.AlignCenter, "Calculating…")
            return

        n = len(self._values)
        inner_w = rect.width() - 8
        bar_w = inner_w / n
        gap = 1.0 if bar_w > 4 else 0.0
        p.setPen(Qt.NoPen)
        for i, v in enumerate(self._values):
            bh = max(1.5, h * min(v, 8.0) / 8.0)
            x = rect.left() + 4 + i * bar_w
            p.setBrush(QColor(entropy_color(v)))
            p.drawRoundedRect(QRectF(x, rect.bottom() - 4 - bh, max(1.0, bar_w - gap), bh), 1.5, 1.5)


# ── Empty state ───────────────────────────────────────────────────────────

class EmptyState(QWidget):
    """Centered placeholder: big icon, title, hint and an optional action button."""
    action_clicked = pyqtSignal()

    def __init__(self, icon: str, title: str, hint: str = "", action: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(10)
        layout.addStretch()

        self._icon = QLabel(icon)
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setStyleSheet("font-size: 46px;")
        layout.addWidget(self._icon)

        self._title = QLabel(title)
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(self._title)

        self._hint = QLabel(hint)
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._hint.setVisible(bool(hint))
        layout.addWidget(self._hint)

        self._button = QPushButton(action)
        self._button.setObjectName("primary")
        self._button.setCursor(Qt.PointingHandCursor)
        self._button.clicked.connect(self.action_clicked)
        self._button.setVisible(bool(action))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._button)
        row.addStretch()
        layout.addSpacing(6)
        layout.addLayout(row)

        self._extra = QVBoxLayout()
        self._extra.setSpacing(6)
        layout.addSpacing(12)
        layout.addLayout(self._extra)
        layout.addStretch()

    def extra_layout(self) -> QVBoxLayout:
        """Layout below the button for additional content (e.g. recent files)."""
        return self._extra


# ── Icon badge ────────────────────────────────────────────────────────────

_KIND_ICONS = {
    "image":      "🖼",
    "audio":      "🎵",
    "video":      "🎬",
    "text":       "📄",
    "document":   "📑",
    "archive":    "📦",
    "executable": "⚙",
    "folder":     "📁",
    "other":      "📎",
}

def kind_icon(kind: str) -> str:
    return _KIND_ICONS.get(kind, "📎")


_KIND_COLORS = {
    "image": "#4caf82", "audio": "#9d8cff", "video": "#e05c9c", "text": "#5b9cf6",
    "document": "#f5a623", "archive": "#c88b4a", "executable": "#e05c5c", "other": "#8a90a0",
}

def kind_color(kind: str) -> str:
    return _KIND_COLORS.get(kind, "#8a90a0")


# ── Clickable label ───────────────────────────────────────────────────────

class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# ── Clipboard helper ──────────────────────────────────────────────────────

def copy_to_clipboard(text: str):
    QApplication.clipboard().setText(text)


# ── Permission toggle button ──────────────────────────────────────────────

class PermToggle(QPushButton):
    """A small toggle button for a single permission bit."""

    def __init__(self, letter: str, active: bool = False, parent=None):
        super().__init__(letter, parent)
        self.setCheckable(True)
        self.setChecked(active)
        self.setFixedSize(34, 30)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
        self.toggled.connect(lambda _: self._update_style())

    def _update_style(self):
        if self.isChecked():
            self.setStyleSheet(
                f"QPushButton {{ background: {ACCENT}; color: {ON_ACCENT}; border-radius: 5px;"
                f"font-weight: bold; font-size: 13px; border: 1px solid {ACCENT}; padding: 0; }}"
                f"QPushButton:disabled {{ background: {rgba(ACCENT, 0.35)}; color: {ON_ACCENT}; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background: {BG_MID}; color: {TEXT_MUTED}; border-radius: 5px;"
                f"font-size: 13px; border: 1px solid {BORDER}; padding: 0; }}"
                f"QPushButton:hover {{ border-color: {ACCENT}; color: {TEXT_PRIMARY}; }}"
            )


# ── Desktop integration helpers ───────────────────────────────────────────

def open_with_default_app(path: str) -> bool:
    """Open a file or folder with the OS default application."""
    from PyQt5.QtGui import QDesktopServices
    from PyQt5.QtCore import QUrl
    return QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def reveal_in_file_manager(path: str) -> bool:
    """Show the file selected in Explorer / Finder, or open its folder on Linux."""
    import os
    import sys
    import subprocess
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
            return True
    except OSError:
        pass
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    return open_with_default_app(folder)
