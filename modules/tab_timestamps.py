"""
tab_timestamps.py — Precise timestamp editing with calendar pickers.
"""

from __future__ import annotations
import time
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QDateTimeEdit, QScrollArea,
)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal

from modules.file_info import FileInfo
from modules.file_ops import set_timestamps, touch_file
from modules.widgets import SectionLabel, StatusBanner
from modules.theme import BG_CARD, BORDER, ACCENT, TEXT_SECONDARY


class TimestampsTab(QWidget):
    file_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll_area)

        container = QWidget()
        scroll_area.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # ── Current timestamps (read-only display) ─────────────────────
        layout.addWidget(SectionLabel("Current Timestamps"))
        info_card = self._card()
        ic = QVBoxLayout(info_card)

        self._cur_labels = {}
        for key in ("Modified", "Accessed", "Created"):
            row = QHBoxLayout()
            lbl = QLabel(f"{key}:")
            lbl.setFixedWidth(80)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            val = QLabel("—")
            val.setObjectName("value")
            row.addWidget(lbl)
            row.addWidget(val, 1)
            ic.addLayout(row)
            self._cur_labels[key] = val

        layout.addWidget(info_card)

        # ── Edit modified ──────────────────────────────────────────────
        layout.addWidget(SectionLabel("Set Modified Time"))
        mod_card = self._card()
        ml = QVBoxLayout(mod_card)
        ml.setSpacing(12)
        self._mod_dt = QDateTimeEdit()
        self._mod_dt.setDisplayFormat("yyyy-MM-dd  HH:mm:ss")
        self._mod_dt.setCalendarPopup(True)
        row = QHBoxLayout()
        row.addWidget(self._mod_dt, 1)
        now_mod = QPushButton("Set to Now")
        now_mod.clicked.connect(lambda: self._mod_dt.setDateTime(QDateTime.currentDateTime()))
        row.addWidget(now_mod)
        ml.addLayout(row)
        apply_mod = QPushButton("Apply Modified Time")
        apply_mod.setObjectName("primary")
        apply_mod.clicked.connect(self._apply_modified)
        ml.addWidget(apply_mod)
        layout.addWidget(mod_card)

        # ── Edit accessed ─────────────────────────────────────────────
        layout.addWidget(SectionLabel("Set Accessed Time"))
        acc_card = self._card()
        al = QVBoxLayout(acc_card)
        al.setSpacing(12)
        self._acc_dt = QDateTimeEdit()
        self._acc_dt.setDisplayFormat("yyyy-MM-dd  HH:mm:ss")
        self._acc_dt.setCalendarPopup(True)
        row2 = QHBoxLayout()
        row2.addWidget(self._acc_dt, 1)
        now_acc = QPushButton("Set to Now")
        now_acc.clicked.connect(lambda: self._acc_dt.setDateTime(QDateTime.currentDateTime()))
        row2.addWidget(now_acc)
        al.addLayout(row2)
        apply_acc = QPushButton("Apply Accessed Time")
        apply_acc.setObjectName("primary")
        apply_acc.clicked.connect(self._apply_accessed)
        al.addWidget(apply_acc)
        layout.addWidget(acc_card)

        # ── Apply both ────────────────────────────────────────────────
        layout.addWidget(SectionLabel("Quick Actions"))
        quick_card = self._card()
        ql = QHBoxLayout(quick_card)
        ql.setSpacing(12)

        touch_btn = QPushButton("⟳  Touch (set both to Now)")
        touch_btn.setObjectName("primary")
        touch_btn.clicked.connect(self._touch)
        apply_both = QPushButton("Apply Both Times")
        apply_both.clicked.connect(self._apply_both)

        ql.addWidget(touch_btn)
        ql.addWidget(apply_both)
        layout.addWidget(quick_card)

        layout.addStretch()

        # Store editable widgets for enable/disable
        self._editable = [
            self._mod_dt, self._acc_dt,
            apply_mod, apply_acc, apply_both, touch_btn,
            now_mod, now_acc,
        ]
        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        self._cur_labels["Modified"].setText(info.modified_str)
        self._cur_labels["Accessed"].setText(info.accessed_str)
        self._cur_labels["Created"].setText(info.created_str)

        self._mod_dt.setDateTime(self._ts_to_qdt(info.modified))
        self._acc_dt.setDateTime(self._ts_to_qdt(info.accessed))
        self._set_enabled(True)

    def clear(self):
        self._info = None
        for v in self._cur_labels.values():
            v.setText("—")
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _apply_modified(self):
        if not self._info: return
        ts = self._qdt_to_ts(self._mod_dt.dateTime())
        ok, msg = set_timestamps(self._info.path, modified=ts)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self._cur_labels["Modified"].setText(
                self._mod_dt.dateTime().toString("yyyy-MM-dd  HH:mm:ss"))
            self.file_changed.emit(self._info.path)

    def _apply_accessed(self):
        if not self._info: return
        ts = self._qdt_to_ts(self._acc_dt.dateTime())
        ok, msg = set_timestamps(self._info.path, accessed=ts)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self._cur_labels["Accessed"].setText(
                self._acc_dt.dateTime().toString("yyyy-MM-dd  HH:mm:ss"))
            self.file_changed.emit(self._info.path)

    def _apply_both(self):
        if not self._info: return
        mts = self._qdt_to_ts(self._mod_dt.dateTime())
        ats = self._qdt_to_ts(self._acc_dt.dateTime())
        ok, msg = set_timestamps(self._info.path, modified=mts, accessed=ats)
        self._banner.show_message(msg, "success" if ok else "error")
        if ok:
            self.file_changed.emit(self._info.path)

    def _touch(self):
        if not self._info: return
        ok, msg = touch_file(self._info.path)
        if ok:
            now = QDateTime.currentDateTime()
            self._mod_dt.setDateTime(now)
            self._acc_dt.setDateTime(now)
            now_str = now.toString("yyyy-MM-dd  HH:mm:ss")
            self._cur_labels["Modified"].setText(now_str)
            self._cur_labels["Accessed"].setText(now_str)
            self.file_changed.emit(self._info.path)
        self._banner.show_message(msg, "success" if ok else "error")

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        for w in self._editable:
            w.setEnabled(en)

    @staticmethod
    def _ts_to_qdt(ts: float) -> QDateTime:
        dt = datetime.fromtimestamp(ts)
        return QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)

    @staticmethod
    def _qdt_to_ts(qdt: QDateTime) -> float:
        d = qdt.toPyDateTime()
        return d.timestamp()

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        return f