"""
tab_permissions.py — Visual permission editor with bit toggles and octal input.
"""

from __future__ import annotations
import platform

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QScrollArea, QGridLayout,
)
from PyQt5.QtCore import Qt, pyqtSignal

from modules.file_info import FileInfo, PermissionInfo
from modules.file_ops import set_permissions_bits, set_permissions_octal
from modules.widgets import SectionLabel, PermToggle, StatusBanner
from modules.theme import BG_CARD, BORDER, ACCENT, TEXT_SECONDARY, TEXT_MUTED


# ── Preset permission sets ─────────────────────────────────────────────────
PRESETS = {
    "644 — Default File":   ("0o644", dict(
        owner_read=True, owner_write=True, owner_exec=False,
        group_read=True, group_write=False, group_exec=False,
        other_read=True, other_write=False, other_exec=False,
    )),
    "755 — Executable":     ("0o755", dict(
        owner_read=True, owner_write=True, owner_exec=True,
        group_read=True, group_write=False, group_exec=True,
        other_read=True, other_write=False, other_exec=True,
    )),
    "600 — Private":        ("0o600", dict(
        owner_read=True, owner_write=True, owner_exec=False,
        group_read=False, group_write=False, group_exec=False,
        other_read=False, other_write=False, other_exec=False,
    )),
    "777 — Full Access":    ("0o777", dict(
        owner_read=True, owner_write=True, owner_exec=True,
        group_read=True, group_write=True, group_exec=True,
        other_read=True, other_write=True, other_exec=True,
    )),
    "400 — Read-Only":      ("0o400", dict(
        owner_read=True, owner_write=False, owner_exec=False,
        group_read=False, group_write=False, group_exec=False,
        other_read=False, other_write=False, other_exec=False,
    )),
}


class PermissionsTab(QWidget):
    file_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None
        self._toggles: dict[str, PermToggle] = {}

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

        # ── Visual toggle matrix ───────────────────────────────────────
        layout.addWidget(SectionLabel("Permission Bits"))
        matrix_card = self._card()
        gl = QGridLayout(matrix_card)
        gl.setSpacing(10)
        gl.setContentsMargins(16, 16, 16, 16)

        # Header
        headers = ["", "Read (r)", "Write (w)", "Execute (x)"]
        for c, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; letter-spacing: 1px;")
            lbl.setAlignment(Qt.AlignCenter)
            gl.addWidget(lbl, 0, c)

        categories = [
            ("Owner", "owner_read", "owner_write", "owner_exec"),
            ("Group", "group_read", "group_write", "group_exec"),
            ("Others","other_read", "other_write", "other_exec"),
        ]
        for r, (label, rk, wk, xk) in enumerate(categories, start=1):
            cat_lbl = QLabel(label)
            cat_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
            gl.addWidget(cat_lbl, r, 0)
            for c, key in enumerate([rk, wk, xk], start=1):
                tog = PermToggle(["r", "w", "x"][c - 1])
                tog.toggled.connect(self._on_toggle_changed)
                self._toggles[key] = tog
                gl.addWidget(tog, r, c, alignment=Qt.AlignCenter)

        layout.addWidget(matrix_card)

        # ── Octal display + edit ───────────────────────────────────────
        layout.addWidget(SectionLabel("Octal Mode"))
        oct_card = self._card()
        ol = QHBoxLayout(oct_card)
        ol.setContentsMargins(16, 12, 16, 12)
        ol.setSpacing(12)

        self._octal_lbl = QLabel("Current:")
        self._octal_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._octal_cur = QLabel("—")
        self._octal_cur.setStyleSheet(f"color: {ACCENT}; font-size: 16px; font-weight: bold;")
        self._octal_cur.setFixedWidth(80)

        sep = QLabel("|")
        sep.setStyleSheet(f"color: {BORDER};")

        self._octal_edit = QLineEdit()
        self._octal_edit.setPlaceholderText("0755")
        self._octal_edit.setFixedWidth(80)
        self._octal_edit.setMaxLength(4)

        apply_oct = QPushButton("Apply Octal")
        apply_oct.setObjectName("primary")
        apply_oct.clicked.connect(self._apply_octal)

        ol.addWidget(self._octal_lbl)
        ol.addWidget(self._octal_cur)
        ol.addWidget(sep)
        ol.addWidget(QLabel("Set:"))
        ol.addWidget(self._octal_edit)
        ol.addWidget(apply_oct)
        ol.addStretch()
        layout.addWidget(oct_card)

        # ── Apply toggle matrix ────────────────────────────────────────
        apply_bits = QPushButton("Apply Permission Bits")
        apply_bits.setObjectName("primary")
        apply_bits.clicked.connect(self._apply_bits)
        layout.addWidget(apply_bits)

        # ── Presets ────────────────────────────────────────────────────
        layout.addWidget(SectionLabel("Presets"))
        preset_card = self._card()
        pl = QVBoxLayout(preset_card)
        pl.setContentsMargins(16, 12, 16, 12)
        pl.setSpacing(8)
        for name, (octal, bits) in PRESETS.items():
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, b=bits, o=octal: self._load_preset(b, o))
            pl.addWidget(btn)
        layout.addWidget(preset_card)

        layout.addStretch()

        self._apply_bits_btn = apply_bits
        self._apply_oct_btn = apply_oct
        self._set_enabled(False)

        if platform.system() == "Windows":
            note = QLabel("⚠  Windows: only the read-only flag is controlled via permissions.")
            note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            layout.insertWidget(0, note)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        perm = info.permissions
        self._load_from_perm(perm)
        self._octal_cur.setText(perm.octal)
        self._set_enabled(True)

    def clear(self):
        self._info = None
        self._octal_cur.setText("—")
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_toggle_changed(self):
        """Update octal display as toggles change."""
        bits = self._read_toggles()
        # compute octal from bits
        mode = 0
        import stat
        mapping = {
            "owner_read": stat.S_IRUSR, "owner_write": stat.S_IWUSR, "owner_exec": stat.S_IXUSR,
            "group_read": stat.S_IRGRP, "group_write": stat.S_IWGRP, "group_exec": stat.S_IXGRP,
            "other_read": stat.S_IROTH, "other_write": stat.S_IWOTH, "other_exec": stat.S_IXOTH,
        }
        for k, v in bits.items():
            if v:
                mode |= mapping[k]
        self._octal_edit.setText(oct(mode))

    def _apply_bits(self):
        if not self._info: return
        bits = self._read_toggles()
        ok, msg = set_permissions_bits(self._info.path, **bits)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self.file_changed.emit(self._info.path)

    def _apply_octal(self):
        if not self._info: return
        octal = self._octal_edit.text().strip()
        if not octal:
            self._banner.show_message("Enter an octal value.", "warning")
            return
        ok, msg = set_permissions_octal(self._info.path, octal)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self._octal_cur.setText(oct(int(octal, 8)))
            self.file_changed.emit(self._info.path)

    def _load_preset(self, bits: dict, octal: str):
        self._load_from_bits(bits)
        self._octal_edit.setText(octal.replace("0o", "0"))

    # ── Helpers ────────────────────────────────────────────────────────

    def _load_from_perm(self, perm: PermissionInfo):
        self._toggles["owner_read"].setChecked(perm.owner_read)
        self._toggles["owner_write"].setChecked(perm.owner_write)
        self._toggles["owner_exec"].setChecked(perm.owner_exec)
        self._toggles["group_read"].setChecked(perm.group_read)
        self._toggles["group_write"].setChecked(perm.group_write)
        self._toggles["group_exec"].setChecked(perm.group_exec)
        self._toggles["other_read"].setChecked(perm.other_read)
        self._toggles["other_write"].setChecked(perm.other_write)
        self._toggles["other_exec"].setChecked(perm.other_exec)

    def _load_from_bits(self, bits: dict):
        for k, v in bits.items():
            if k in self._toggles:
                self._toggles[k].setChecked(v)

    def _read_toggles(self) -> dict:
        return {k: t.isChecked() for k, t in self._toggles.items()}

    def _set_enabled(self, en: bool):
        for t in self._toggles.values():
            t.setEnabled(en)
        self._apply_bits_btn.setEnabled(en)
        self._apply_oct_btn.setEnabled(en)
        self._octal_edit.setEnabled(en)

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        return f