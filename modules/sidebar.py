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
    QListWidget, QListWidgetItem, QTabWidget, QMenu,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter

from modules.theme import (
    BG_DARKEST, BG_MID, BG_CARD, BG_HOVER, BG_SELECTED, BORDER, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ERROR,
)
from modules.widgets import kind_icon, copy_to_clipboard, reveal_in_file_manager
from modules.file_info import classify_path, human_size
from modules.settings_dialog import AppSettings


MAX_RECENT = 20
_PLACEHOLDER = "__loading__"
_ROLE_PATH = Qt.UserRole
_ROLE_IS_DIR = Qt.UserRole + 1


class _RecentDelegate(QStyledItemDelegate):
    """Two-line recent item: file name, then its folder in a muted colour."""

    def sizeHint(self, option, index):
        fm = option.fontMetrics
        return QSize(option.rect.width(), fm.height() * 2 + 14)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        rect = option.rect
        selected = option.state & QStyle.State_Selected
        hovered = option.state & QStyle.State_MouseOver
        if selected:
            painter.fillRect(rect, QColor(BG_SELECTED))
            painter.fillRect(QRect(rect.left(), rect.top(), 3, rect.height()), QColor(ACCENT))
        elif hovered:
            painter.fillRect(rect, QColor(BG_HOVER))

        path = index.data(_ROLE_PATH) or ""
        icon = index.data(Qt.UserRole + 2) or ""
        missing = index.data(Qt.UserRole + 3)
        fm = option.fontMetrics
        line_h = fm.height()
        x = rect.left() + 12

        painter.setPen(QColor(TEXT_PRIMARY))
        painter.drawText(QRect(x, rect.top() + 6, 22, line_h), Qt.AlignLeft | Qt.AlignVCenter, icon)
        name_rect = QRect(x + 24, rect.top() + 6, rect.width() - 44, line_h)
        name_font = QFont(option.font)
        name_font.setStrikeOut(bool(missing))
        painter.setFont(name_font)
        painter.setPen(QColor(TEXT_MUTED if missing else (ACCENT if selected else TEXT_PRIMARY)))
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         fm.elidedText(os.path.basename(path), Qt.ElideMiddle, name_rect.width()))

        small = QFont(option.font)
        small.setPointSizeF(max(7.0, option.font.pointSizeF() - 1.5))
        painter.setFont(small)
        painter.setPen(QColor(ERROR if missing else TEXT_MUTED))
        dir_rect = QRect(x + 24, rect.top() + 6 + line_h, rect.width() - 44, line_h)
        folder = "missing — " + os.path.dirname(path) if missing else os.path.dirname(path)
        painter.drawText(dir_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(folder, Qt.ElideMiddle, dir_rect.width()))
        painter.restore()


class Sidebar(QWidget):
    file_selected = pyqtSignal(str)     # emits path when user picks a file
    folder_selected = pyqtSignal(str)   # emits path when user asks to analyse a folder

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(220)
        self.setMaximumWidth(520)

        self._settings = AppSettings()
        self._show_hidden = self._settings.show_hidden_files()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("sidebarHeader")
        header.setFixedHeight(54)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)

        title = QLabel("◆ FileForge")
        title.setStyleSheet(
            f"color: {ACCENT}; font-size: 15px; font-weight: bold; letter-spacing: 1.5px;"
        )
        hl.addWidget(title)
        hl.addStretch()

        open_btn = QPushButton("Open…")
        open_btn.setObjectName("primary")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setToolTip("Open a file (Ctrl+O)")
        open_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        open_btn.clicked.connect(self._open_dialog)
        hl.addWidget(open_btn)

        layout.addWidget(header)

        # ── Search bar ────────────────────────────────────────────────
        search_frame = QFrame()
        search_frame.setObjectName("sidebarSearch")
        sl = QHBoxLayout(search_frame)
        sl.setContentsMargins(10, 8, 10, 8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Filter files…")
        self._search.setClearButtonEnabled(True)
        self._search.setToolTip("Filter recent files and loaded folders (Ctrl+F)")
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(lambda: self._filter(self._search.text()))
        self._search.textChanged.connect(lambda _: self._filter_timer.start())
        sl.addWidget(self._search)
        layout.addWidget(search_frame)

        # ── Tabs: Recent | Browser ─────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setElideMode(Qt.ElideNone)
        self._tabs.tabBar().setExpanding(True)
        self._tabs.tabBar().setUsesScrollButtons(False)

        # Recent files list
        self._recent_list = QListWidget()
        self._recent_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._recent_list.setItemDelegate(_RecentDelegate(self._recent_list))
        self._recent_list.setMouseTracking(True)
        self._recent_list.setUniformItemSizes(True)
        self._recent_list.itemActivated.connect(self._on_recent_activated)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_activated)
        self._recent_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._recent_list.customContextMenuRequested.connect(self._recent_menu)
        self._tabs.addTab(self._recent_list, "Recent")

        # Directory browser
        self._dir_tree = QTreeWidget()
        self._dir_tree.setHeaderHidden(True)
        self._dir_tree.setAnimated(True)
        self._dir_tree.setIndentation(14)
        self._dir_tree.setUniformRowHeights(True)
        self._dir_tree.itemExpanded.connect(self._on_expand)
        self._dir_tree.itemActivated.connect(self._on_tree_activated)
        self._dir_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._dir_tree.customContextMenuRequested.connect(self._tree_menu)
        self._populate_roots()
        self._tabs.addTab(self._dir_tree, "Browse")

        layout.addWidget(self._tabs, 1)

        # ── Bottom bar ─────────────────────────────────────────────────
        bottom = QFrame()
        bottom.setObjectName("sidebarFooter")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(10, 4, 10, 4)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        clear_btn = QPushButton("Clear Recent")
        clear_btn.setObjectName("ghost")
        clear_btn.setFixedHeight(26)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_recent)
        bl.addWidget(self._count_lbl)
        bl.addStretch()
        bl.addWidget(clear_btn)
        layout.addWidget(bottom)

        self._recent: list[str] = []
        if self._settings.remember_recent():
            self._recent = self._settings.recent_files()[:MAX_RECENT]
        self._rebuild_recent()

    def sizeHint(self) -> QSize:
        return QSize(280, 600)

    # ── Public ─────────────────────────────────────────────────────────

    def add_recent(self, path: str):
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        self._recent = self._recent[:MAX_RECENT]
        self._rebuild_recent()
        self._persist_recent()

    def remove_recent(self, path: str):
        if path in self._recent:
            self._recent.remove(path)
            self._rebuild_recent()
            self._persist_recent()

    def recent_files(self) -> list[str]:
        return list(self._recent)

    def open_file(self, path: str):
        self.file_selected.emit(path)

    def focus_filter(self):
        self._search.setFocus()
        self._search.selectAll()

    def set_show_hidden(self, show: bool):
        if show != self._show_hidden:
            self._show_hidden = show
            self._populate_roots()

    def set_current_folder(self, folder: str):
        """Switch the browser view to a specific directory."""
        if not os.path.isdir(folder):
            return
        self._dir_tree.clear()
        item = QTreeWidgetItem([f"📂  {folder}"])
        item.setData(0, _ROLE_PATH, folder)
        item.setData(0, _ROLE_IS_DIR, True)
        item.setToolTip(0, folder)
        item.setForeground(0, QColor(ACCENT))
        item.addChild(QTreeWidgetItem([_PLACEHOLDER]))
        self._dir_tree.addTopLevelItem(item)
        self._dir_tree.expandItem(item)
        self._tabs.setCurrentWidget(self._dir_tree)

    # ── Slots ─────────────────────────────────────────────────────────

    def _open_dialog(self):
        start = os.path.dirname(self._recent[0]) if self._recent else ""
        path, _ = QFileDialog.getOpenFileName(self, "Open File", start)
        if path:
            self.open_file(path)

    def _on_recent_activated(self, item: QListWidgetItem):
        path = item.data(_ROLE_PATH)
        if path and os.path.isfile(path):
            self.open_file(path)
        elif path:
            self._rebuild_recent()   # refresh "missing" marker

    def _on_tree_activated(self, item: QTreeWidgetItem, col: int = 0):
        path = item.data(0, _ROLE_PATH)
        if path and os.path.isfile(path):
            self.open_file(path)

    def _on_expand(self, item: QTreeWidgetItem):
        path = item.data(0, _ROLE_PATH)
        if path and item.childCount() == 1 and item.child(0).text(0) == _PLACEHOLDER:
            item.takeChildren()
            self._populate_dir(item, path)
            if self._search.text():
                self._filter(self._search.text())

    def _filter(self, text: str):
        text = text.lower().strip()
        for i in range(self._recent_list.count()):
            item = self._recent_list.item(i)
            path = (item.data(_ROLE_PATH) or "").lower()
            item.setHidden(bool(text) and text not in os.path.basename(path))
        for i in range(self._dir_tree.topLevelItemCount()):
            self._filter_tree(self._dir_tree.topLevelItem(i), text, is_root=True)

    def _filter_tree(self, item: QTreeWidgetItem, text: str, is_root: bool = False) -> bool:
        """Hide non-matching loaded items; a folder stays visible if anything inside matches."""
        any_child = False
        for i in range(item.childCount()):
            if self._filter_tree(item.child(i), text):
                any_child = True
        name = os.path.basename(item.data(0, _ROLE_PATH) or item.text(0)).lower()
        visible = is_root or not text or text in name or any_child
        item.setHidden(not visible)
        return visible and (not is_root)

    def _clear_recent(self):
        self._recent.clear()
        self._recent_list.clear()
        self._persist_recent()
        self._update_count()

    # ── Context menus ──────────────────────────────────────────────────

    def _recent_menu(self, pos):
        item = self._recent_list.itemAt(pos)
        if not item:
            return
        path = item.data(_ROLE_PATH)
        menu = QMenu(self)
        exists = os.path.isfile(path)
        act_open = menu.addAction("Open")
        act_open.setEnabled(exists)
        act_copy = menu.addAction("Copy Path")
        act_reveal = menu.addAction("Reveal in File Manager")
        act_reveal.setEnabled(exists)
        act_browse = menu.addAction("Browse Containing Folder")
        act_browse.setEnabled(os.path.isdir(os.path.dirname(path)))
        menu.addSeparator()
        act_remove = menu.addAction("Remove from Recent")
        chosen = menu.exec_(self._recent_list.viewport().mapToGlobal(pos))
        if chosen is act_open:
            self.open_file(path)
        elif chosen is act_copy:
            copy_to_clipboard(path)
        elif chosen is act_reveal:
            reveal_in_file_manager(path)
        elif chosen is act_browse:
            self.set_current_folder(os.path.dirname(path))
        elif chosen is act_remove:
            self.remove_recent(path)

    def _tree_menu(self, pos):
        item = self._dir_tree.itemAt(pos)
        if not item or not item.data(0, _ROLE_PATH):
            return
        path = item.data(0, _ROLE_PATH)
        is_dir = os.path.isdir(path)
        menu = QMenu(self)
        act_open = act_root = act_analyse = None
        if is_dir:
            act_root = menu.addAction("Browse From Here")
            act_analyse = menu.addAction("Analyse Folder")
        else:
            act_open = menu.addAction("Open")
        act_copy = menu.addAction("Copy Path")
        act_reveal = menu.addAction("Reveal in File Manager")
        menu.addSeparator()
        act_refresh = menu.addAction("Refresh")
        chosen = menu.exec_(self._dir_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_open:
            self.open_file(path)
        elif chosen is act_root:
            self.set_current_folder(path)
        elif chosen is act_analyse:
            self.folder_selected.emit(path)
        elif chosen is act_copy:
            copy_to_clipboard(path)
        elif chosen is act_reveal:
            reveal_in_file_manager(path)
        elif chosen is act_refresh:
            target = item if is_dir else item.parent()
            if target is not None:
                target.takeChildren()
                self._populate_dir(target, target.data(0, _ROLE_PATH))
            else:
                self._populate_roots()

    # ── Builders ───────────────────────────────────────────────────────

    def _persist_recent(self):
        if self._settings.remember_recent():
            self._settings.set_recent_files(self._recent)
        else:
            self._settings.set_recent_files([])

    def _update_count(self):
        n = len(self._recent)
        self._count_lbl.setText(f"{n} recent" if n else "")

    def _rebuild_recent(self):
        self._recent_list.clear()
        for path in self._recent:
            item = QListWidgetItem(Path(path).name)
            item.setData(_ROLE_PATH, path)
            item.setData(Qt.UserRole + 2, self._icon_for_path(path))
            missing = not os.path.exists(path)
            item.setData(Qt.UserRole + 3, missing)
            item.setToolTip(path + ("\n(file no longer exists)" if missing else ""))
            self._recent_list.addItem(item)
        self._update_count()

    def _populate_roots(self):
        self._dir_tree.clear()
        roots = self._get_roots()
        for label, path in roots:
            item = QTreeWidgetItem([label])
            item.setData(0, _ROLE_PATH, path)
            item.setData(0, _ROLE_IS_DIR, True)
            item.setToolTip(0, path)
            item.setForeground(0, QColor(ACCENT))
            # Placeholder child so arrow shows
            item.addChild(QTreeWidgetItem([_PLACEHOLDER]))
            self._dir_tree.addTopLevelItem(item)

    def _populate_dir(self, parent: QTreeWidgetItem, dir_path: str):
        dirs: list[tuple[str, str]] = []
        files: list[tuple[str, str, int]] = []
        try:
            # scandir gives us the entry type without an extra stat() per entry
            with os.scandir(dir_path) as it:
                for entry in it:
                    if not self._show_hidden and entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir():
                            dirs.append((entry.name, entry.path))
                        else:
                            try:
                                size = entry.stat().st_size
                            except OSError:
                                size = -1
                            files.append((entry.name, entry.path, size))
                    except OSError:
                        continue
        except (PermissionError, OSError) as e:
            err = QTreeWidgetItem(["(permission denied)" if isinstance(e, PermissionError) else "(unreadable)"])
            err.setForeground(0, QColor(TEXT_MUTED))
            err.setFlags(Qt.NoItemFlags)
            parent.addChild(err)
            return

        children = []
        for name, path in sorted(dirs, key=lambda d: d[0].lower()):
            child = QTreeWidgetItem([f"📁  {name}"])
            child.setData(0, _ROLE_PATH, path)
            child.setData(0, _ROLE_IS_DIR, True)
            child.setForeground(0, QColor(TEXT_SECONDARY))
            child.addChild(QTreeWidgetItem([_PLACEHOLDER]))
            children.append(child)
        for name, path, size in sorted(files, key=lambda f: f[0].lower()):
            child = QTreeWidgetItem([f"{kind_icon(classify_path(path))}  {name}"])
            child.setData(0, _ROLE_PATH, path)
            child.setForeground(0, QColor(TEXT_PRIMARY))
            child.setToolTip(0, f"{path}\n{human_size(size)}" if size >= 0 else path)
            children.append(child)
        if not children:
            empty = QTreeWidgetItem(["(empty)"])
            empty.setForeground(0, QColor(TEXT_MUTED))
            empty.setFlags(Qt.NoItemFlags)
            children.append(empty)
        # One batched insert is much faster than addChild() per entry for big folders
        parent.addChildren(children)

    @staticmethod
    def _icon_for_path(file_path: str) -> str:
        return kind_icon(classify_path(file_path))

    @staticmethod
    def _get_roots() -> list[tuple[str, str]]:
        import platform
        if platform.system() == "Windows":
            import string, ctypes
            drives = []
            home = str(Path.home())
            drives.append(("🏠  Home", home))
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drives.append((f"💽  {letter}:\\", f"{letter}:\\"))
                bitmask >>= 1
            return drives
        else:
            roots = [("💽  / (Root)", "/")]
            home = str(Path.home())
            if home != "/":
                roots.insert(0, ("🏠  Home", home))
            for extra in ("/Volumes", "/media", "/mnt"):
                try:
                    if os.path.isdir(extra) and os.listdir(extra):
                        roots.append((f"🔌  {extra}", extra))
                except OSError:
                    continue
            return roots
