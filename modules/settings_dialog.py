"""
settings_dialog.py — User preferences and settings dialog.

Also exposes `AppSettings`, a lightweight typed accessor so the rest of the
app can read preferences without constructing a dialog.
"""

from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QLabel, QCheckBox, QComboBox, QSpinBox,
    QPushButton, QGroupBox, QFormLayout, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
)
from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtGui import QFont

from modules.theme import (
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT, WARNING,
    THEME_NAMES, THEME_NAME, DEFAULT_FONT_PX,
)


HASH_ALGORITHMS = [("md5", "MD5"), ("sha1", "SHA-1"), ("sha256", "SHA-256"),
                   ("sha512", "SHA-512"), ("blake2", "BLAKE2")]
_HASH_DEFAULTS = {"md5": True, "sha1": True, "sha256": True, "sha512": False, "blake2": False}

# (action, shortcut) — kept in one place so the Settings dialog can list them
SHORTCUTS = [
    ("Open file", "Ctrl+O"),
    ("Open folder", "Ctrl+Shift+O"),
    ("Reload current file", "F5"),
    ("Close file", "Ctrl+W"),
    ("Copy file path", "Ctrl+Shift+P"),
    ("Reveal in file manager", "Ctrl+Shift+R"),
    ("Go to Overview … Integrity tabs", "Ctrl+1 … Ctrl+7"),
    ("Focus sidebar filter", "Ctrl+F"),
    ("Compare files", "Ctrl+Shift+C"),
    ("Settings", "Ctrl+,"),
    ("Quit", "Ctrl+Q"),
    ("Open a file", "Drag & drop onto the window"),
    ("Add several files to Batch", "Drop multiple files"),
]


class AppSettings:
    """Typed access to persisted preferences (QSettings 'FileForge/FileForge')."""

    def __init__(self):
        self._s = QSettings("FileForge", "FileForge")

    # General
    def auto_refresh(self) -> bool:
        return self._s.value("auto_refresh", False, type=bool)

    def auto_hash_on_load(self) -> bool:
        return self._s.value("auto_hash_on_load", False, type=bool)

    def default_hash_algorithms(self) -> list[str]:
        return [a for a, _ in HASH_ALGORITHMS
                if self._s.value(f"default_{a}", _HASH_DEFAULTS[a], type=bool)]

    def remember_recent(self) -> bool:
        return self._s.value("remember_recent", True, type=bool)

    def show_hidden_files(self) -> bool:
        return self._s.value("show_hidden_files", False, type=bool)

    # Interface
    def theme(self) -> str:
        name = self._s.value("theme", "Dark")
        return name if name in THEME_NAMES else "Dark"

    def font_px(self) -> int:
        return max(10, min(20, self._s.value("ui_font_px", DEFAULT_FONT_PX, type=int)))

    # Persisted lists
    def recent_files(self) -> list[str]:
        value = self._s.value("recent_files", [])
        if isinstance(value, str):          # QSettings collapses 1-item lists on some platforms
            value = [value]
        return [v for v in (value or []) if isinstance(v, str)]

    def set_recent_files(self, paths: list[str]):
        self._s.setValue("recent_files", list(paths))

    def value(self, key: str, default=None, type_=None):
        if type_ is None:
            return self._s.value(key, default)
        return self._s.value(key, default, type=type_)

    def set_value(self, key: str, value):
        self._s.setValue(key, value)


class SettingsDialog(QDialog):
    settings_applied = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(560, 470)
        self.setModal(True)

        self._settings = QSettings("FileForge", "FileForge")

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)

        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # General tab
        general_tab = QWidget()
        tabs.addTab(general_tab, "General")
        self._build_general_tab(general_tab)

        # UI tab
        ui_tab = QWidget()
        tabs.addTab(ui_tab, "Interface")
        self._build_ui_tab(ui_tab)

        # Shortcuts tab
        shortcuts_tab = QWidget()
        tabs.addTab(shortcuts_tab, "Shortcuts")
        self._build_shortcuts_tab(shortcuts_tab)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply,
            Qt.Horizontal, self
        )
        buttons.button(QDialogButtonBox.Ok).setObjectName("primary")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        layout.addWidget(buttons)

    def _build_general_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)

        # Auto-refresh group
        auto_group = QGroupBox("File Watching")
        layout.addWidget(auto_group)
        auto_layout = QVBoxLayout(auto_group)

        self._auto_refresh_chk = QCheckBox("Auto-refresh when file changes externally")
        self._auto_refresh_chk.setToolTip("Automatically reload the current file if it's modified by another program")
        auto_layout.addWidget(self._auto_refresh_chk)

        # Hash defaults group
        hash_group = QGroupBox("Default Hash Algorithms")
        layout.addWidget(hash_group)
        hash_layout = QVBoxLayout(hash_group)

        row = QHBoxLayout()
        self._hash_chks: dict[str, QCheckBox] = {}
        for algo, label in HASH_ALGORITHMS:
            chk = QCheckBox(label)
            self._hash_chks[algo] = chk
            row.addWidget(chk)
        row.addStretch()
        hash_layout.addLayout(row)

        self._auto_hash_chk = QCheckBox("Compute hashes automatically when a file is opened")
        self._auto_hash_chk.setToolTip("Runs in the background; large files may take a while")
        hash_layout.addWidget(self._auto_hash_chk)

        # Kept for backwards compatibility with code that referenced these attributes
        self._default_md5_chk = self._hash_chks["md5"]
        self._default_sha1_chk = self._hash_chks["sha1"]
        self._default_sha256_chk = self._hash_chks["sha256"]
        self._default_sha512_chk = self._hash_chks["sha512"]
        self._default_blake2_chk = self._hash_chks["blake2"]

        # Files group
        files_group = QGroupBox("Files")
        layout.addWidget(files_group)
        files_layout = QVBoxLayout(files_group)
        self._remember_recent_chk = QCheckBox("Remember recent files between sessions")
        self._show_hidden_chk = QCheckBox("Show hidden files in the Browse tree")
        files_layout.addWidget(self._remember_recent_chk)
        files_layout.addWidget(self._show_hidden_chk)

        layout.addStretch()

    def _build_ui_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 8, 12, 12)

        # Theme group
        theme_group = QGroupBox("Appearance")
        layout.addWidget(theme_group)
        theme_layout = QFormLayout(theme_group)
        theme_layout.setSpacing(10)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(THEME_NAMES)
        self._theme_combo.currentTextChanged.connect(self._update_restart_hint)
        theme_layout.addRow("Theme:", self._theme_combo)

        # Font size
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(10, 20)
        self._font_size_spin.setSuffix(" px")
        self._font_size_spin.setValue(DEFAULT_FONT_PX)
        theme_layout.addRow("Font size:", self._font_size_spin)

        self._restart_hint = QLabel("")
        self._restart_hint.setStyleSheet(f"color: {WARNING}; font-size: 11px;")
        self._restart_hint.setWordWrap(True)
        theme_layout.addRow("", self._restart_hint)

        layout.addStretch()

    def _build_shortcuts_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 8, 12, 12)

        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderLabels(["Action", "Shortcut"])
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for action, keys in SHORTCUTS:
            item = QTreeWidgetItem([action, keys])
            item.setForeground(1, Qt.gray)
            tree.addTopLevelItem(item)
        layout.addWidget(tree)

    def _update_restart_hint(self, name: str):
        if name != THEME_NAME:
            self._restart_hint.setText("Theme changes take effect after restarting FileForge.")
        else:
            self._restart_hint.setText("")

    def _load_settings(self):
        s = AppSettings()
        self._auto_refresh_chk.setChecked(s.auto_refresh())
        enabled = set(s.default_hash_algorithms())
        for algo, chk in self._hash_chks.items():
            chk.setChecked(algo in enabled)
        self._auto_hash_chk.setChecked(s.auto_hash_on_load())
        self._remember_recent_chk.setChecked(s.remember_recent())
        self._show_hidden_chk.setChecked(s.show_hidden_files())

        self._theme_combo.setCurrentText(s.theme())
        self._font_size_spin.setValue(s.font_px())
        self._update_restart_hint(self._theme_combo.currentText())

    def _save_settings(self):
        # General settings
        self._settings.setValue("auto_refresh", self._auto_refresh_chk.isChecked())

        # Default hashes
        for algo, chk in self._hash_chks.items():
            self._settings.setValue(f"default_{algo}", chk.isChecked())
        self._settings.setValue("auto_hash_on_load", self._auto_hash_chk.isChecked())
        self._settings.setValue("remember_recent", self._remember_recent_chk.isChecked())
        self._settings.setValue("show_hidden_files", self._show_hidden_chk.isChecked())

        # UI settings
        self._settings.setValue("theme", self._theme_combo.currentText())
        self._settings.setValue("ui_font_px", self._font_size_spin.value())

        self._settings.sync()
        self.settings_applied.emit()

    def _accept(self):
        self._save_settings()
        self.accept()

    def _apply(self):
        self._save_settings()

    # Public API (kept for compatibility)
    def get_auto_refresh_enabled(self) -> bool:
        return AppSettings().auto_refresh()

    def get_default_hash_algorithms(self) -> list[str]:
        return AppSettings().default_hash_algorithms()
