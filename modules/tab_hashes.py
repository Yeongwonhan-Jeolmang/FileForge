"""
tab_hashes.py — Compute & verify MD5 / SHA-1 / SHA-256 / SHA-512 / BLAKE2 hashes in a background thread.
"""

from __future__ import annotations
import time
import threading

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
    QCheckBox,
    QScrollArea,
    QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

from modules.file_info import FileInfo, compute_hashes, HashCancelled, human_size
from modules.metadata_cache import get_cached_hashes, store_hashes
from modules.settings_dialog import AppSettings
from modules.widgets import SectionLabel, StatusBanner, HashProgressBar, Card
from modules.theme import SUCCESS, ERROR, TEXT_SECONDARY

ALGORITHMS = ("md5", "sha1", "sha256", "sha512", "blake2")
_LABELS = {
    "md5": "MD5",
    "sha1": "SHA-1",
    "sha256": "SHA-256",
    "sha512": "SHA-512",
    "blake2": "BLAKE2b",
}
# Hex digest length → candidate algorithms (SHA-512 and BLAKE2b are both 128 chars)
_BY_LENGTH = {32: ["md5"], 40: ["sha1"], 64: ["sha256"], 128: ["sha512", "blake2"]}


# ── Worker thread ─────────────────────────────────────────────────────────


class HashWorker(QObject):
    progress = pyqtSignal(int, int)  # done, total
    finished = pyqtSignal(dict)  # {algo: hexdigest}
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, path: str, algorithms: list[str]):
        super().__init__()
        self._path = path
        self._algorithms = algorithms
        self._stop = threading.Event()

    def cancel(self):
        self._stop.set()

    def run(self):
        try:
            result = compute_hashes(
                self._path,
                self._algorithms,
                progress_cb=lambda d, t: self.progress.emit(d, t),
                cancel_cb=self._stop.is_set,
            )
            self.finished.emit(result)
        except HashCancelled:
            self.cancelled.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Tab ───────────────────────────────────────────────────────────────────


class HashesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None
        self._thread: QThread | None = None
        self._worker: HashWorker | None = None
        self._hashes: dict[str, str] = {}
        self._started_at = 0.0
        self._pending_verify = False

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
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        # ── Algorithm selector ─────────────────────────────────────────
        layout.addWidget(SectionLabel("Select Algorithms"))
        algo_card = self._card()
        al = QHBoxLayout(algo_card)
        al.setContentsMargins(16, 12, 16, 12)
        al.setSpacing(24)
        self._chk_md5 = QCheckBox("MD5")
        self._chk_sha1 = QCheckBox("SHA-1")
        self._chk_sha256 = QCheckBox("SHA-256")
        self._chk_sha512 = QCheckBox("SHA-512")
        self._chk_blake2 = QCheckBox("BLAKE2")
        self._checks = {
            "md5": self._chk_md5,
            "sha1": self._chk_sha1,
            "sha256": self._chk_sha256,
            "sha512": self._chk_sha512,
            "blake2": self._chk_blake2,
        }
        for chk in self._checks.values():
            al.addWidget(chk)
        al.addStretch()

        # ── Compute / cancel buttons ──────────────────────────────────
        self._compute_btn = QPushButton("⚙  Compute Hashes")
        self._compute_btn.setObjectName("primary")
        self._compute_btn.setCursor(Qt.PointingHandCursor)
        self._compute_btn.clicked.connect(self._compute)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel)
        self._cancel_btn.hide()
        al.addWidget(self._cancel_btn)
        al.addWidget(self._compute_btn)
        layout.addWidget(algo_card)
        self.refresh_defaults()

        # ── Progress ───────────────────────────────────────────────────
        self._progress = HashProgressBar()
        layout.addWidget(self._progress)

        # ── Results ────────────────────────────────────────────────────
        results_header = QHBoxLayout()
        results_header.addWidget(SectionLabel("Results"))
        results_header.addStretch()
        self._copy_all_btn = QPushButton("Copy All")
        self._copy_all_btn.setObjectName("ghost")
        self._copy_all_btn.setToolTip(
            "Copy every computed hash, one per line (sha256sum-style)"
        )
        self._copy_all_btn.clicked.connect(self._copy_all)
        results_header.addWidget(self._copy_all_btn)
        layout.addLayout(results_header)

        results_card = self._card()
        rl = QVBoxLayout(results_card)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(10)

        self._hash_fields: dict[str, QLineEdit] = {}
        self._copy_btns: dict[str, QPushButton] = {}

        for algo in ALGORITHMS:
            row = QHBoxLayout()
            lbl = QLabel(_LABELS[algo])
            lbl.setFixedWidth(76)
            lbl.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 11px; letter-spacing: 1px;"
            )
            field = QLineEdit()
            field.setReadOnly(True)
            field.setPlaceholderText("—")
            field.setStyleSheet("letter-spacing: 0.5px;")
            copy_btn = QPushButton("Copy")
            copy_btn.setFixedWidth(64)
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

        hint = QLabel(
            "Paste an expected hash — the algorithm is detected from its length "
            "and computed automatically if needed."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_SECONDARY};")
        vl.addWidget(hint)
        verify_row = QHBoxLayout()
        self._verify_edit = QLineEdit()
        self._verify_edit.setPlaceholderText(
            "Paste MD5, SHA-1, SHA-256, SHA-512 or BLAKE2 hash here…"
        )
        self._verify_edit.setClearButtonEnabled(True)
        self._verify_edit.returnPressed.connect(self._verify)
        self._paste_btn = QPushButton("Paste")
        self._paste_btn.setToolTip("Paste from clipboard and verify")
        self._paste_btn.clicked.connect(self._paste_and_verify)
        self._verify_btn = QPushButton("Verify")
        self._verify_btn.setObjectName("primary")
        self._verify_btn.clicked.connect(self._verify)
        verify_row.addWidget(self._verify_edit, 1)
        verify_row.addWidget(self._paste_btn)
        verify_row.addWidget(self._verify_btn)
        vl.addLayout(verify_row)

        self._verify_result = QLabel("")
        self._verify_result.setWordWrap(True)
        vl.addWidget(self._verify_result)
        layout.addWidget(verify_card)

        layout.addStretch()
        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._cancel()
        self._info = info
        self._hashes = {}
        for f in self._hash_fields.values():
            f.clear()
            f.setStyleSheet("letter-spacing: 0.5px;")
        self._verify_result.clear()
        self._set_enabled(True)

        # Show digests we already know for these exact contents (size+mtime match)
        cached = get_cached_hashes(info.path)
        if cached:
            self._show_results(cached)
            self._banner.show_message(
                "Showing cached hashes for this file.", "info", 2500
            )

        if AppSettings().auto_hash_on_load():
            missing = [a for a in self._selected_algorithms() if a not in self._hashes]
            if missing:
                self._compute()

    def clear(self):
        self._cancel()
        self._info = None
        for f in self._hash_fields.values():
            f.clear()
        self._hashes = {}
        self._verify_result.clear()
        self._set_enabled(False)

    def refresh_defaults(self):
        """Apply the default algorithm selection from Settings."""
        defaults = set(AppSettings().default_hash_algorithms()) or {"sha256"}
        for algo, chk in self._checks.items():
            chk.setChecked(algo in defaults)

    def shutdown(self):
        self._cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)

    # ── Slots ─────────────────────────────────────────────────────────

    def _selected_algorithms(self) -> list[str]:
        return [a for a, chk in self._checks.items() if chk.isChecked()]

    def _compute(self, algos: list[str] | None = None):
        if not self._info:
            return
        if self._thread is not None:
            return  # already running
        if not algos:
            algos = self._selected_algorithms()
        if not algos:
            self._banner.show_message("Select at least one algorithm.", "warning")
            return

        self._compute_btn.setEnabled(False)
        self._cancel_btn.show()
        names = ", ".join(_LABELS[a] for a in algos)
        self._progress.start(f"Computing {names} for {self._info.size_human}…")
        self._started_at = time.perf_counter()

        worker = HashWorker(self._info.path, algos)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_hashes_done)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(
            lambda: self._banner.show_message("Hashing cancelled.", "warning")
        )
        worker.cancelled.connect(thread.quit)
        worker.error.connect(lambda e: self._banner.show_message(e, "error"))
        worker.error.connect(thread.quit)
        thread.finished.connect(self._progress.finish)

        self._worker = worker
        self._thread = thread
        thread.finished.connect(self._cleanup_thread)
        thread.start()

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()
        self._pending_verify = False

    def _on_progress(self, done: int, total: int):
        self._progress.set_progress(done, total)
        elapsed = time.perf_counter() - self._started_at
        if elapsed > 0.5 and done:
            rate = done / elapsed
            remaining = (total - done) / rate if rate else 0
            self._progress.set_label(
                f"{human_size(done)} of {human_size(total)}  ·  {human_size(int(rate))}/s"
                f"  ·  ~{remaining:.0f}s left"
            )

    def _on_hashes_done(self, results: dict):
        elapsed = time.perf_counter() - self._started_at
        if self._info:
            store_hashes(self._info.path, results)
            for algo, digest in results.items():
                if hasattr(self._info, algo):
                    setattr(self._info, algo, digest)
        self._show_results(results)
        self._banner.show_message(f"Hashes computed in {elapsed:.2f}s.", "success")
        if self._pending_verify:
            self._pending_verify = False
            self._verify()

    def _show_results(self, results: dict):
        self._hashes.update(results)
        for algo, digest in results.items():
            if algo in self._hash_fields:
                self._hash_fields[algo].setText(digest)
                self._hash_fields[algo].setCursorPosition(0)

    def _copy_hash(self, algo: str):
        text = self._hash_fields[algo].text()
        if text:
            QApplication.clipboard().setText(text)
            self._banner.show_message(
                f"{_LABELS[algo]} copied to clipboard.", "info", 2000
            )

    def _copy_all(self):
        if not self._hashes or not self._info:
            self._banner.show_message("Compute hashes first.", "warning")
            return
        lines = [
            f"{_LABELS[a]:<8} {self._hashes[a]}  {self._info.name}"
            for a in ALGORITHMS
            if a in self._hashes
        ]
        QApplication.clipboard().setText("\n".join(lines))
        self._banner.show_message(f"Copied {len(lines)} hash(es).", "info", 2000)

    def _paste_and_verify(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self._verify_edit.setText(text)
            self._verify()

    def _verify(self):
        raw = self._verify_edit.text().strip()
        if not raw:
            self._banner.show_message("Paste a hash to verify.", "warning")
            return
        # Accept bare digests, "hash  filename" lines from *sum tools, and "SHA256:hash"
        tokens = raw.replace(":", " ").replace("=", " ").split()
        hexchars = set("0123456789abcdefABCDEF")
        digests = [t for t in tokens if len(t) in _BY_LENGTH and set(t) <= hexchars]
        if not digests:
            self._show_verify(
                "✗  No MD5 / SHA / BLAKE2 hex digest found in that text.", ERROR
            )
            return
        expected = digests[0].lower()

        candidates = _BY_LENGTH.get(len(expected))
        if not candidates:
            self._show_verify(
                f"✗  Unrecognised hash length ({len(expected)} hex chars).", ERROR
            )
            return

        known = [a for a in candidates if a in self._hashes]
        for algo in known:
            if self._hashes[algo].lower() == expected:
                self._show_verify(f"✓  Match  ({_LABELS[algo]})", SUCCESS)
                return

        missing = [a for a in candidates if a not in self._hashes]
        if missing:
            # Compute just what we need, then re-run verification
            self._pending_verify = True
            self._show_verify(
                f"…  Computing {' / '.join(_LABELS[a] for a in missing)} to verify…",
                TEXT_SECONDARY,
            )
            self._compute(missing)
            return

        names = " / ".join(_LABELS[a] for a in candidates)
        self._show_verify(f"✗  No match — the file's {names} is different.", ERROR)

    def _show_verify(self, text: str, color: str):
        self._verify_result.setText(text)
        self._verify_result.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _cleanup_thread(self):
        self._compute_btn.setEnabled(self._info is not None)
        self._cancel_btn.hide()
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        self._compute_btn.setEnabled(en and self._thread is None)
        self._verify_btn.setEnabled(en)
        self._verify_edit.setEnabled(en)
        self._paste_btn.setEnabled(en)
        self._copy_all_btn.setEnabled(en)
        for b in self._copy_btns.values():
            b.setEnabled(en)

    @staticmethod
    def _card() -> QFrame:
        return Card()
