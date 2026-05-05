"""
comparison_dialog.py — Dialog for comparing two files.
"""

from __future__ import annotations
import os
import difflib
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFileDialog, QSplitter,
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem,
    QTabWidget, QWidget, QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont

from modules.theme import BG_CARD, BORDER, ACCENT, TEXT_SECONDARY
from modules.file_info import read_file_info
from modules.entropy_calculator import calculate_entropy


# ── Worker thread ─────────────────────────────────────────────────────────

class ComparisonWorker(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)  # Comparison results
    error = pyqtSignal(str)

    def __init__(self, path1: str, path2: str):
        super().__init__()
        self._path1 = path1
        self._path2 = path2

    def run(self):
        try:
            self.progress.emit(10)

            # Read file infos
            info1 = read_file_info(self._path1)
            info2 = read_file_info(self._path2)
            self.progress.emit(30)

            # Compare basic properties
            results = {
                'info1': info1,
                'info2': info2,
                'differences': self._compare_infos(info1, info2)
            }
            self.progress.emit(60)

            # Compare content if both are text or small files
            if info1.size < 1024 * 1024 and info2.size < 1024 * 1024:  # 1MB limit
                try:
                    with open(self._path1, 'rb') as f1, open(self._path2, 'rb') as f2:
                        content1 = f1.read()
                        content2 = f2.read()

                    # Try as text
                    try:
                        text1 = content1.decode('utf-8', errors='replace')
                        text2 = content2.decode('utf-8', errors='replace')
                        diff = list(difflib.unified_diff(
                            text1.splitlines(keepends=True),
                            text2.splitlines(keepends=True),
                            fromfile=os.path.basename(self._path1),
                            tofile=os.path.basename(self._path2)
                        ))
                        results['text_diff'] = diff
                    except UnicodeDecodeError:
                        pass

                    # Hex diff for binary files
                    if len(content1) == len(content2):
                        hex_diff = []
                        for i, (b1, b2) in enumerate(zip(content1, content2)):
                            if b1 != b2:
                                hex_diff.append(f"{i:08X}: {b1:02X} != {b2:02X}")
                        results['hex_diff'] = hex_diff[:1000]  # Limit to first 1000 differences

                except (OSError, IOError):
                    pass

            self.progress.emit(100)
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))

    def _compare_infos(self, info1, info2) -> list:
        """Compare two FileInfo objects and return list of differences."""
        differences = []

        # Basic properties
        if info1.size != info2.size:
            differences.append(f"Size: {info1.size_human} vs {info2.size_human}")

        if info1.mime_type != info2.mime_type:
            differences.append(f"MIME type: {info1.mime_type} vs {info2.mime_type}")

        if info1.kind != info2.kind:
            differences.append(f"Kind: {info1.kind} vs {info2.kind}")

        # Permissions
        if info1.permissions.octal != info2.permissions.octal:
            differences.append(f"Permissions: {info1.permissions.octal} vs {info2.permissions.octal}")

        # Timestamps (allow small differences)
        time_diff_threshold = 2  # seconds
        if abs(info1.modified - info2.modified) > time_diff_threshold:
            differences.append(f"Modified: {info1.modified_str} vs {info2.modified_str}")

        # Hashes (if computed)
        for algo in ['md5', 'sha1', 'sha256']:
            h1 = getattr(info1, algo, None)
            h2 = getattr(info2, algo, None)
            if h1 and h2 and h1 != h2:
                differences.append(f"{algo.upper()}: {h1[:16]}... vs {h2[:16]}...")

        return differences


# ── Dialog ─────────────────────────────────────────────────────────────────

class ComparisonDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Comparison")
        self.resize(1000, 700)
        self.setModal(True)

        self._results = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # File selection
        selection_group = QGroupBox("Select Files to Compare")
        selection_layout = QHBoxLayout(selection_group)

        self._file1_label = QLabel("No file selected")
        self._file1_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._select_file1_btn = QPushButton("Select File 1…")
        self._select_file1_btn.clicked.connect(self._select_file1)

        self._file2_label = QLabel("No file selected")
        self._file2_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._select_file2_btn = QPushButton("Select File 2…")
        self._select_file2_btn.clicked.connect(self._select_file2)

        selection_layout.addWidget(QLabel("File 1:"))
        selection_layout.addWidget(self._file1_label, 1)
        selection_layout.addWidget(self._select_file1_btn)

        selection_layout.addWidget(QLabel("File 2:"))
        selection_layout.addWidget(self._file2_label, 1)
        selection_layout.addWidget(self._select_file2_btn)

        layout.addWidget(selection_group)

        # Compare button
        self._compare_btn = QPushButton("Compare Files")
        self._compare_btn.setObjectName("primary")
        self._compare_btn.clicked.connect(self._compare_files)
        self._compare_btn.setEnabled(False)
        layout.addWidget(self._compare_btn)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Results tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Summary tab
        self._summary_tab = QWidget()
        self._tabs.addTab(self._summary_tab, "Summary")
        self._build_summary_tab()

        # Differences tab
        self._diff_tab = QWidget()
        self._tabs.addTab(self._diff_tab, "Differences")
        self._build_diff_tab()

        # Content comparison tab
        self._content_tab = QWidget()
        self._tabs.addTab(self._content_tab, "Content")
        self._build_content_tab()

        # Buttons
        from PyQt5.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        layout.addWidget(buttons)
        buttons.rejected.connect(self.reject)

    def _build_summary_tab(self):
        layout = QVBoxLayout(self._summary_tab)

        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setFontFamily("Consolas")
        self._summary_text.setFontPointSize(9)
        layout.addWidget(self._summary_text)

    def _build_diff_tab(self):
        layout = QVBoxLayout(self._diff_tab)

        self._diff_list = QListWidget()
        layout.addWidget(self._diff_list)

    def _build_content_tab(self):
        layout = QVBoxLayout(self._content_tab)

        self._content_tabs = QTabWidget()
        layout.addWidget(self._content_tabs)

        # Text diff tab
        text_tab = QWidget()
        self._content_tabs.addTab(text_tab, "Text Diff")
        text_layout = QVBoxLayout(text_tab)
        self._text_diff_edit = QTextEdit()
        self._text_diff_edit.setReadOnly(True)
        self._text_diff_edit.setFontFamily("Consolas")
        self._text_diff_edit.setFontPointSize(9)
        text_layout.addWidget(self._text_diff_edit)

        # Hex diff tab
        hex_tab = QWidget()
        self._content_tabs.addTab(hex_tab, "Hex Differences")
        hex_layout = QVBoxLayout(hex_tab)
        self._hex_diff_edit = QTextEdit()
        self._hex_diff_edit.setReadOnly(True)
        self._hex_diff_edit.setFontFamily("Consolas")
        self._hex_diff_edit.setFontPointSize(9)
        hex_layout.addWidget(self._hex_diff_edit)

    def _select_file1(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select First File")
        if path:
            self._file1_path = path
            self._file1_label.setText(os.path.basename(path))
            self._update_compare_button()

    def _select_file2(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Second File")
        if path:
            self._file2_path = path
            self._file2_label.setText(os.path.basename(path))
            self._update_compare_button()

    def _update_compare_button(self):
        enabled = hasattr(self, '_file1_path') and hasattr(self, '_file2_path')
        self._compare_btn.setEnabled(enabled)

    def _compare_files(self):
        if not (hasattr(self, '_file1_path') and hasattr(self, '_file2_path')):
            return

        self._compare_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)

        worker = ComparisonWorker(self._file1_path, self._file2_path)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._progress.setValue)
        worker.finished.connect(self._on_comparison_done)
        worker.finished.connect(thread.quit)
        worker.error.connect(self._on_comparison_error)
        worker.error.connect(thread.quit)
        thread.finished.connect(lambda: self._compare_btn.setEnabled(True))
        thread.finished.connect(lambda: self._progress.setVisible(False))

        thread.start()

    def _on_comparison_done(self, results: dict):
        self._results = results
        self._display_results(results)

    def _on_comparison_error(self, error: str):
        self._summary_text.setPlainText(f"Error during comparison:\n{error}")

    def _display_results(self, results: dict):
        info1 = results['info1']
        info2 = results['info2']
        differences = results.get('differences', [])

        # Summary
        summary = f"""File Comparison Summary
{'='*40}

File 1: {info1.path}
File 2: {info2.path}

Basic Properties:
- File 1 size: {info1.size_human}
- File 2 size: {info2.size_human}
- File 1 type: {info1.mime_type}
- File 2 type: {info2.mime_type}

Entropy:
- File 1: {calculate_entropy(info1.path):.2f} bits/byte
- File 2: {calculate_entropy(info2.path):.2f} bits/byte

Differences Found: {len(differences)}
"""

        if differences:
            summary += "\nDifferences:\n"
            for diff in differences:
                summary += f"• {diff}\n"

        self._summary_text.setPlainText(summary)

        # Differences list
        self._diff_list.clear()
        for diff in differences:
            item = QListWidgetItem(diff)
            self._diff_list.addItem(item)

        # Content comparison
        if 'text_diff' in results:
            self._text_diff_edit.setPlainText(''.join(results['text_diff']))
        else:
            self._text_diff_edit.setPlainText("No text diff available (files may be binary or too large)")

        if 'hex_diff' in results:
            self._hex_diff_edit.setPlainText('\n'.join(results['hex_diff']))
        else:
            self._hex_diff_edit.setPlainText("No hex differences found or files are identical")