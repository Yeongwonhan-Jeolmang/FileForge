"""
sidebar.py — Left-panel file browser: recent files + directory tree.
"""

from __future__ import annotations
import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QFrame, QLineEdit, QAbstractItemView,
    QListWidget, QListWidgetItem, QTabWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal, QDir
from PyQt5.QtGui import QColor

from modules.theme import (
    BG_DARKEST, BG_MID, BG_CARD, BORDER, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
)
from modules.widgets import kind_icon
from modules.file_info import read_file_info


MAX_RECENT = 20


class Sidebar(QWidget):
    file_selected = pyqtSignal(str)   # emits path when user picks a file

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet(f"background: {BG_DARKEST};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(f"background: {BG_MID}; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 12, 0)

        title = QLabel("FileForge")
        title.setStyleSheet(
            f"color: {ACCENT}; font-size: 15px; font-weight: bold; letter-spacing: 2px;"
        )
        hl.addWidget(title)
        hl.addStretch()

        open_btn = QPushButton("Open…")
        open_btn.setMinimumWidth(80)
        open_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        open_btn.clicked.connect(self._open_dialog)
        hl.addWidget(open_btn)

        layout.addWidget(header)

        # ── Search bar ────────────────────────────────────────────────
        search_frame = QFrame()
        search_frame.setStyleSheet(f"background: {BG_MID}; border-bottom: 1px solid {BORDER};")
        sl = QHBoxLayout(search_frame)
        sl.setContentsMargins(10, 6, 10, 6)
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Filter…")
        self._search.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 3px;"
            f"padding: 4px 8px; color: {TEXT_PRIMARY};"
        )
        self._search.textChanged.connect(self._filter)
        sl.addWidget(self._search)
        layout.addWidget(search_frame)

        # ── Tabs: Recent | Browser ─────────────────────────────────────
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabBar::tab { padding: 6px 14px; font-size: 11px; }"
            f"QTabWidget::pane {{ border: none; background: {BG_DARKEST}; }}"
        )

        # Recent files list
        self._recent_list = QListWidget()
        self._recent_list.setAlternatingRowColors(True)
        self._recent_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_dclick)
        self._recent_list.setStyleSheet(
            f"QListWidget {{ background: {BG_DARKEST}; border: none; }}"
            f"QListWidget::item {{ padding: 5px 8px; }}"
            f"QListWidget::item:hover {{ background: #1e2230; }}"
            f"QListWidget::item:selected {{ background: #2a3040; color: {ACCENT}; }}"
        )
        tabs.addTab(self._recent_list, "Recent")

        # Directory browser
        self._dir_tree = QTreeWidget()
        self._dir_tree.setHeaderHidden(True)
        self._dir_tree.setAnimated(True)
        self._dir_tree.setIndentation(14)
        self._dir_tree.itemExpanded.connect(self._on_expand)
        self._dir_tree.itemDoubleClicked.connect(self._on_tree_dclick)
        self._dir_tree.setStyleSheet(
            f"QTreeWidget {{ background: {BG_DARKEST}; border: none; }}"
            f"QTreeWidget::item {{ padding: 3px 4px; }}"
            f"QTreeWidget::item:hover {{ background: #1e2230; }}"
            f"QTreeWidget::item:selected {{ background: #2a3040; color: {ACCENT}; }}"
        )
        self._populate_roots()
        tabs.addTab(self._dir_tree, "Browse")

        layout.addWidget(tabs, 1)

        # ── Bottom clear-recent button ─────────────────────────────────
        bottom = QFrame()
        bottom.setStyleSheet(f"background: {BG_MID}; border-top: 1px solid {BORDER};")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(10, 4, 10, 4)
        clear_btn = QPushButton("Clear Recent")
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self._clear_recent)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_MUTED}; border: none; font-size: 11px; }}"
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
        )
        bl.addStretch()
        bl.addWidget(clear_btn)
        layout.addWidget(bottom)

        self._recent: list[str] = []

    # ── Public ─────────────────────────────────────────────────────────

    def add_recent(self, path: str):
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        self._recent = self._recent[:MAX_RECENT]
        self._rebuild_recent()

    def open_file(self, path: str):
        self.add_recent(path)
        self.file_selected.emit(path)

    # ── Slots ─────────────────────────────────────────────────────────

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File")
        if path:
            self.open_file(path)

    def _on_recent_dclick(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path and os.path.isfile(path):
            self.open_file(path)

    def _on_tree_dclick(self, item: QTreeWidgetItem, col: int):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            self.open_file(path)

    def _on_expand(self, item: QTreeWidgetItem):
        path = item.data(0, Qt.UserRole)
        if path and item.childCount() == 1 and item.child(0).text(0) == "__loading__":
            item.takeChildren()
            self._populate_dir(item, path)

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self._recent_list.count()):
            item = self._recent_list.item(i)
            item.setHidden(text not in item.text().lower())

    def _clear_recent(self):
        self._recent.clear()
        self._recent_list.clear()

    # ── Builders ───────────────────────────────────────────────────────

    def _rebuild_recent(self):
        self._recent_list.clear()
        for path in self._recent:
            p = Path(path)
            try:
                info = read_file_info(path)
                icon = kind_icon(info.kind)
            except Exception:
                icon = "📄"
            item = QListWidgetItem(f"{icon}  {p.name}")
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            item.setForeground(QColor(TEXT_PRIMARY))
            self._recent_list.addItem(item)

    def _populate_roots(self):
        self._dir_tree.clear()
        roots = self._get_roots()
        for label, path in roots:
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, path)
            item.setForeground(0, QColor(ACCENT))
            # Placeholder child so arrow shows
            placeholder = QTreeWidgetItem(["__loading__"])
            item.addChild(placeholder)
            self._dir_tree.addTopLevelItem(item)

    def _populate_dir(self, parent: QTreeWidgetItem, dir_path: str):
        try:
            entries = sorted(Path(dir_path).iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            err = QTreeWidgetItem(["(permission denied)"])
            err.setForeground(0, QColor(TEXT_MUTED))
            parent.addChild(err)
            return
        for entry in entries:
            name = entry.name
            if name.startswith("."):
                continue
            if entry.is_dir():
                child = QTreeWidgetItem([f"📁  {name}"])
                child.setData(0, Qt.UserRole, str(entry))
                child.setForeground(0, QColor(TEXT_SECONDARY))
                placeholder = QTreeWidgetItem(["__loading__"])
                child.addChild(placeholder)
            else:
                try:
                    info = read_file_info(str(entry))
                    icon = kind_icon(info.kind)
                except Exception:
                    icon = "📄"
                child = QTreeWidgetItem([f"{icon}  {name}"])
                child.setData(0, Qt.UserRole, str(entry))
                child.setForeground(0, QColor(TEXT_PRIMARY))
            parent.addChild(child)

    @staticmethod
    def _get_roots() -> list[tuple[str, str]]:
        import platform
        if platform.system() == "Windows":
            import string, ctypes
            drives = []
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drives.append((f"{letter}:\\", f"{letter}:\\"))
                bitmask >>= 1
            return drives
        else:
            roots = [("/ (Root)", "/")]
            home = str(Path.home())
            if home != "/":
                roots.insert(0, ("🏠 Home", home))
            return roots