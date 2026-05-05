"""
settings_dialog.py — User preferences and settings dialog.
"""

from __future__ import annotations
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QLabel, QCheckBox, QComboBox, QSpinBox,
    QPushButton, QGroupBox, QFormLayout, QDialogButtonBox,
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont

from modules.theme import TEXT_PRIMARY, TEXT_SECONDARY, ACCENT


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 400)
        self.setModal(True)

        self._settings = QSettings("FileForge", "FileForge")

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)

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
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        layout.addWidget(buttons)

    def _build_general_tab(self, parent):
        layout = QVBoxLayout(parent)

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

        self._default_md5_chk = QCheckBox("MD5")
        self._default_sha1_chk = QCheckBox("SHA-1")
        self._default_sha256_chk = QCheckBox("SHA-256")
        self._default_sha512_chk = QCheckBox("SHA-512")
        self._default_blake2_chk = QCheckBox("BLAKE2")

        self._default_md5_chk.setChecked(True)
        self._default_sha1_chk.setChecked(True)
        self._default_sha256_chk.setChecked(True)

        for chk in (self._default_md5_chk, self._default_sha1_chk, self._default_sha256_chk,
                   self._default_sha512_chk, self._default_blake2_chk):
            hash_layout.addWidget(chk)

        layout.addStretch()

    def _build_ui_tab(self, parent):
        layout = QVBoxLayout(parent)

        # Theme group
        theme_group = QGroupBox("Appearance")
        layout.addWidget(theme_group)
        theme_layout = QFormLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Default", "Dark", "Light"])
        theme_layout.addRow("Theme:", self._theme_combo)

        # Font size
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 24)
        self._font_size_spin.setValue(10)
        theme_layout.addRow("Font size:", self._font_size_spin)

        layout.addStretch()

    def _build_shortcuts_tab(self, parent):
        layout = QVBoxLayout(parent)

        label = QLabel("Keyboard shortcuts can be customized in future versions.")
        label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(label)

        layout.addStretch()

    def _load_settings(self):
        # General settings
        self._auto_refresh_chk.setChecked(
            self._settings.value("auto_refresh", False, type=bool)
        )

        # Default hashes
        self._default_md5_chk.setChecked(
            self._settings.value("default_md5", True, type=bool)
        )
        self._default_sha1_chk.setChecked(
            self._settings.value("default_sha1", True, type=bool)
        )
        self._default_sha256_chk.setChecked(
            self._settings.value("default_sha256", True, type=bool)
        )
        self._default_sha512_chk.setChecked(
            self._settings.value("default_sha512", False, type=bool)
        )
        self._default_blake2_chk.setChecked(
            self._settings.value("default_blake2", False, type=bool)
        )

        # UI settings
        theme = self._settings.value("theme", "Default")
        self._theme_combo.setCurrentText(theme)

        font_size = self._settings.value("font_size", 10, type=int)
        self._font_size_spin.setValue(font_size)

    def _save_settings(self):
        # General settings
        self._settings.setValue("auto_refresh", self._auto_refresh_chk.isChecked())

        # Default hashes
        self._settings.setValue("default_md5", self._default_md5_chk.isChecked())
        self._settings.setValue("default_sha1", self._default_sha1_chk.isChecked())
        self._settings.setValue("default_sha256", self._default_sha256_chk.isChecked())
        self._settings.setValue("default_sha512", self._default_sha512_chk.isChecked())
        self._settings.setValue("default_blake2", self._default_blake2_chk.isChecked())

        # UI settings
        self._settings.setValue("theme", self._theme_combo.currentText())
        self._settings.setValue("font_size", self._font_size_spin.value())

        self._settings.sync()

    def _accept(self):
        self._save_settings()
        self.accept()

    def _apply(self):
        self._save_settings()

    # Public API
    def get_auto_refresh_enabled(self) -> bool:
        return self._settings.value("auto_refresh", False, type=bool)

    def get_default_hash_algorithms(self) -> list[str]:
        algos = []
        if self._settings.value("default_md5", True, type=bool):
            algos.append("md5")
        if self._settings.value("default_sha1", True, type=bool):
            algos.append("sha1")
        if self._settings.value("default_sha256", True, type=bool):
            algos.append("sha256")
        if self._settings.value("default_sha512", False, type=bool):
            algos.append("sha512")
        if self._settings.value("default_blake2", False, type=bool):
            algos.append("blake2")
        return algos