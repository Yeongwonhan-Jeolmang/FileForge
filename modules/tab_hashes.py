"""
tab_hashes.py — Compute & verify MD5 / SHA-1 / SHA-256 hashes in a background thread.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QCheckBox,
    QScrollArea, QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

from modules.file_info import FileInfo, compute_hashes
from modules.widgets import SectionLabel, StatusBanner, HashProgressBar
from modules.theme import BG_CARD, BORDER, ACCENT, SUCCESS, ERROR, TEXT_SECONDARY


# ── Worker thread ─────────────────────────────────────────────────────────

class HashWorker(QObject):
    progress = pyqtSignal(int, int)       # done, total
    finished = pyqtSignal(dict)           # {algo: hexdigest}
    error    = pyqtSignal(str)

    def __init__(self, path: str, algorithms: list[str]):
        super().__init__()
        self._path = path
        self._algorithms = algorithms

    def run(self):
        try:
            result = compute_hashes(
                self._path, self._algorithms,
                progress_cb=lambda d, t: self.progress.emit(d, t),
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ── Tab ───────────────────────────────────────────────────────────────────

class HashesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None
        self._thread: QThread | None = None
        self._hashes: dict[str, str] = {}

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

        # ── Algorithm selector ─────────────────────────────────────────
        layout.addWidget(SectionLabel("Select Algorithms"))
        algo_card = self._card()
        al = QHBoxLayout(algo_card)
        al.setContentsMargins(16, 12, 16, 12)
        al.setSpacing(24)
        self._chk_md5    = QCheckBox("MD5")
        self._chk_sha1   = QCheckBox("SHA-1")
        self._chk_sha256 = QCheckBox("SHA-256")
        self._chk_md5.setChecked(True)
        self._chk_sha1.setChecked(True)
        self._chk_sha256.setChecked(True)
        for chk in (self._chk_md5, self._chk_sha1, self._chk_sha256):
            al.addWidget(chk)
        al.addStretch()
        layout.addWidget(algo_card)

        # ── Progress ───────────────────────────────────────────────────
        self._progress = HashProgressBar()
        layout.addWidget(self._progress)

        # ── Compute button ─────────────────────────────────────────────
        self._compute_btn = QPushButton("⚙  Compute Hashes")
        self._compute_btn.setObjectName("primary")
        self._compute_btn.clicked.connect(self._compute)
        layout.addWidget(self._compute_btn)

        # ── Results ────────────────────────────────────────────────────
        layout.addWidget(SectionLabel("Results"))
        results_card = self._card()
        rl = QVBoxLayout(results_card)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(12)

        self._hash_fields: dict[str, QLineEdit] = {}
        self._copy_btns:  dict[str, QPushButton] = {}

        for algo in ("md5", "sha1", "sha256"):
            row = QHBoxLayout()
            lbl = QLabel(algo.upper() + ":")
            lbl.setFixedWidth(70)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            field = QLineEdit()
            field.setReadOnly(True)
            field.setPlaceholderText("—")
            field.setFont(self.font())
            field.setStyleSheet(
                f"font-family: 'Consolas', monospace; letter-spacing: 0.5px;"
            )
            copy_btn = QPushButton("Copy")
            copy_btn.setFixedWidth(60)
            copy_btn.clicked.connect(lambda _, a=algo: self._copy_hash(a))
            self._hash_fields[algo] = field
            self._copy_btns[algo] = copy_btn
            row.addWidget(lbl)
            row.addWidget(field, 1)
            row.addWidget(copy_btn)
            rl.addLayout(row)

        layout.addWidget(results_card)

        # ── Verify ────────────────────────────────────────────────────
        layout.addWidget(SectionLabel("Verify Hash"))
        verify_card = self._card()
        vl = QVBoxLayout(verify_card)
        vl.setContentsMargins(16, 12, 16, 12)
        vl.setSpacing(10)

        vl.addWidget(QLabel("Paste expected hash to verify:"))
        verify_row = QHBoxLayout()
        self._verify_edit = QLineEdit()
        self._verify_edit.setPlaceholderText("Paste MD5, SHA-1 or SHA-256 hash here…")
        self._verify_btn = QPushButton("Verify")
        self._verify_btn.setObjectName("primary")
        self._verify_btn.clicked.connect(self._verify)
        verify_row.addWidget(self._verify_edit, 1)
        verify_row.addWidget(self._verify_btn)
        vl.addLayout(verify_row)

        self._verify_result = QLabel("")
        vl.addWidget(self._verify_result)
        layout.addWidget(verify_card)

        layout.addStretch()
        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        self._hashes = {}
        for f in self._hash_fields.values():
            f.clear()
        self._verify_result.clear()
        self._set_enabled(True)

    def clear(self):
        self._info = None
        for f in self._hash_fields.values():
            f.clear()
        self._hashes = {}
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _compute(self):
        if not self._info: return
        algos = []
        if self._chk_md5.isChecked():    algos.append("md5")
        if self._chk_sha1.isChecked():   algos.append("sha1")
        if self._chk_sha256.isChecked(): algos.append("sha256")
        if not algos:
            self._banner.show_message("Select at least one algorithm.", "warning")
            return

        self._compute_btn.setEnabled(False)
        self._progress.start("Computing hashes…")

        worker = HashWorker(self._info.path, algos)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._progress.update)
        worker.finished.connect(self._on_hashes_done)
        worker.finished.connect(thread.quit)
        worker.error.connect(lambda e: self._banner.show_message(e, "error"))
        worker.error.connect(thread.quit)
        thread.finished.connect(lambda: self._compute_btn.setEnabled(True))
        thread.finished.connect(self._progress.finish)

        self._thread = thread
        thread.start()

    def _on_hashes_done(self, results: dict):
        self._hashes = results
        for algo, digest in results.items():
            if algo in self._hash_fields:
                self._hash_fields[algo].setText(digest)
        self._banner.show_message("Hashes computed.", "success")

    def _copy_hash(self, algo: str):
        text = self._hash_fields[algo].text()
        if text:
            QApplication.clipboard().setText(text)
            self._banner.show_message(f"{algo.upper()} copied to clipboard.", "info")

    def _verify(self):
        expected = self._verify_edit.text().strip().lower()
        if not expected:
            self._banner.show_message("Paste a hash to verify.", "warning")
            return
        if not self._hashes:
            self._banner.show_message("Compute hashes first.", "warning")
            return
        for algo, digest in self._hashes.items():
            if digest.lower() == expected:
                self._verify_result.setText(f"✓  Match  ({algo.upper()})")
                self._verify_result.setStyleSheet(f"color: {SUCCESS}; font-weight: bold;")
                return
        self._verify_result.setText("✗  No match with any computed hash.")
        self._verify_result.setStyleSheet(f"color: {ERROR}; font-weight: bold;")

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        self._compute_btn.setEnabled(en)
        self._verify_btn.setEnabled(en)
        self._verify_edit.setEnabled(en)
        for b in self._copy_btns.values():
            b.setEnabled(en)

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        return f