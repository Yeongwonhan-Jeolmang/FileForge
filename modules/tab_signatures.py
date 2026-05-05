"""
tab_signatures.py — Display digital signature information for files.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTextEdit, QGroupBox,
    QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

from modules.file_info import FileInfo
from modules.widgets import SectionLabel, StatusBanner
from modules.theme import BG_CARD, BORDER, ACCENT, SUCCESS, ERROR, TEXT_SECONDARY
from modules.signature_inspector import inspect_signature, check_pgp_signature, SignatureInfo


# ── Worker thread ─────────────────────────────────────────────────────────

class SignatureWorker(QObject):
    progress = pyqtSignal(int)  # Progress percentage
    finished = pyqtSignal(object)  # SignatureInfo
    error = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self._file_path = file_path

    def run(self):
        try:
            self.progress.emit(25)

            # Check for Authenticode signature
            sig_info = inspect_signature(self._file_path)
            self.progress.emit(75)

            # Also check for PGP signature
            pgp_info = check_pgp_signature(self._file_path)
            self.progress.emit(100)

            # Combine results (prefer Authenticode if both exist)
            if sig_info.is_signed:
                final_info = sig_info
            elif pgp_info.is_signed:
                final_info = pgp_info
            else:
                final_info = sig_info

            self.finished.emit(final_info)

        except Exception as e:
            self.error.emit(str(e))


# ── Tab ───────────────────────────────────────────────────────────────────

class SignaturesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None
        self._thread: QThread | None = None
        self._worker: SignatureWorker | None = None
        self._current_sig_info: SignatureInfo | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        # Inspect button
        button_layout = QHBoxLayout()
        self._inspect_btn = QPushButton("Inspect Signatures")
        self._inspect_btn.setObjectName("primary")
        self._inspect_btn.clicked.connect(self._inspect_signatures)
        button_layout.addWidget(self._inspect_btn)
        button_layout.addStretch()
        outer.addLayout(button_layout)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        outer.addWidget(self._progress)

        # Results area
        self._results_text = QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setFontFamily("Consolas")
        self._results_text.setFontPointSize(9)
        outer.addWidget(self._results_text)

        self._set_enabled(False)

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        self._current_sig_info = None
        self._results_text.clear()
        self._set_enabled(True)

    def clear(self):
        self._info = None
        self._current_sig_info = None
        self._results_text.clear()
        self._set_enabled(False)

    # ── Slots ─────────────────────────────────────────────────────────

    def _inspect_signatures(self):
        if not self._info:
            return

        self._inspect_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._banner.show_message("Inspecting signatures…")

        worker = SignatureWorker(self._info.path)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._progress.setValue)
        worker.finished.connect(self._on_signature_inspected)
        worker.finished.connect(thread.quit)
        worker.error.connect(lambda e: self._banner.show_message(e, "error"))
        worker.error.connect(thread.quit)
        thread.finished.connect(lambda: self._inspect_btn.setEnabled(True))
        thread.finished.connect(lambda: self._progress.setVisible(False))

        self._worker = worker
        self._thread = thread
        thread.start()

    def _on_signature_inspected(self, sig_info: SignatureInfo):
        self._current_sig_info = sig_info
        self._display_signature_info(sig_info)

        if sig_info.is_signed and sig_info.is_valid:
            self._banner.show_message("Valid signature found.", "success")
        elif sig_info.is_signed and not sig_info.is_valid:
            self._banner.show_message("Invalid signature detected.", "error")
        elif sig_info.error_message:
            self._banner.show_message(f"Signature inspection failed: {sig_info.error_message}", "warning")
        else:
            self._banner.show_message("No digital signature found.", "info")

    def _display_signature_info(self, sig_info: SignatureInfo):
        if not sig_info:
            self._results_text.setPlainText("No signature information available.")
            return

        text = f"""Digital Signature Information
{'='*40}

Status: {'Signed' if sig_info.is_signed else 'Not Signed'}
"""

        if sig_info.is_signed:
            text += f"""
Validity: {'Valid' if sig_info.is_valid else 'Invalid'}
Signature Type: {sig_info.signature_type or 'Unknown'}
"""

            if sig_info.signer_name:
                text += f"Signer: {sig_info.signer_name}\n"

            if sig_info.issuer_name:
                text += f"Issuer: {sig_info.issuer_name}\n"

            if sig_info.serial_number:
                text += f"Serial Number: {sig_info.serial_number}\n"

            if sig_info.thumbprint:
                text += f"Thumbprint: {sig_info.thumbprint}\n"

            if sig_info.valid_from:
                text += f"Valid From: {sig_info.valid_from}\n"

            if sig_info.valid_to:
                text += f"Valid To: {sig_info.valid_to}\n"

        if sig_info.error_message:
            text += f"\nError: {sig_info.error_message}\n"

        self._results_text.setPlainText(text.strip())

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_enabled(self, en: bool):
        self._inspect_btn.setEnabled(en)