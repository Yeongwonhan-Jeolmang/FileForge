"""
comparison_dialog.py — Dialog for comparing two files.
"""

from __future__ import annotations
import os
import html
import difflib
import filecmp
from typing import Any
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QWidget,
    QProgressBar,
    QCheckBox,
)
from PyQt5.QtCore import QThread, pyqtSignal, QObject

from modules.theme import TEXT_SECONDARY, TEXT_MUTED, SUCCESS, ERROR, INFO, WARNING
from modules.file_info import read_file_info
from modules.entropy_calculator import calculate_entropy


# ── Worker thread ─────────────────────────────────────────────────────────


class ComparisonWorker(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)  # Comparison results
    error = pyqtSignal(str)

    def __init__(self, path1: str, path2: str, compare_dirs: bool = False):
        super().__init__()
        self._path1 = path1
        self._path2 = path2
        self._compare_dirs = compare_dirs

    def run(self):
        try:
            self.progress.emit(10)

            if (
                self._compare_dirs
                and os.path.isdir(self._path1)
                and os.path.isdir(self._path2)
            ):
                results = self._compare_directories(self._path1, self._path2)
                self.progress.emit(100)
                self.finished.emit(results)
                return

            # Read file infos
            info1 = read_file_info(self._path1)
            info2 = read_file_info(self._path2)
            self.progress.emit(30)

            # Compare basic properties
            results: dict[str, Any] = {
                "info1": info1,
                "info2": info2,
                "differences": self._compare_infos(info1, info2),
            }
            self.progress.emit(60)

            # Byte-for-byte identity (stops at the first differing chunk)
            try:
                results["identical"] = info1.size == info2.size and filecmp.cmp(
                    self._path1, self._path2, shallow=False
                )
            except OSError:
                results["identical"] = False

            # Entropy is sampled so this stays fast for huge files (was computed on the UI thread)
            results["entropy1"] = calculate_entropy(self._path1, sample_size=1_000_000)
            results["entropy2"] = calculate_entropy(self._path2, sample_size=1_000_000)
            self.progress.emit(75)

            # Compare content if both are text or small files
            if (
                not results["identical"]
                and info1.size < 4 * 1024 * 1024
                and info2.size < 4 * 1024 * 1024
            ):
                try:
                    with open(self._path1, "rb") as f1, open(self._path2, "rb") as f2:
                        content1 = f1.read()
                        content2 = f2.read()

                    # Try as text — strict decoding, so binary files don't produce a garbage "diff"
                    try:
                        if b"\x00" in content1[:8192] or b"\x00" in content2[:8192]:
                            raise UnicodeDecodeError("utf-8", b"", 0, 1, "binary")
                        text1 = content1.decode("utf-8")
                        text2 = content2.decode("utf-8")
                        diff = list(
                            difflib.unified_diff(
                                text1.splitlines(keepends=True),
                                text2.splitlines(keepends=True),
                                fromfile=os.path.basename(self._path1),
                                tofile=os.path.basename(self._path2),
                            )
                        )
                        results["text_diff"] = diff[:20000]
                    except UnicodeDecodeError:
                        pass

                    # Hex diff for binary files (over the common length)
                    hex_diff = []
                    common = min(len(content1), len(content2))
                    for i in range(common):
                        if content1[i] != content2[i]:
                            hex_diff.append(
                                f"{i:08X}: {content1[i]:02X} != {content2[i]:02X}"
                            )
                            if len(hex_diff) >= 1000:  # Limit to first 1000 differences
                                hex_diff.append("… (more differences not shown)")
                                break
                    if len(content1) != len(content2):
                        longer = "File 1" if len(content1) > len(content2) else "File 2"
                        hex_diff.append(
                            f"{common:08X}: {longer} has {abs(len(content1) - len(content2)):,} extra byte(s) from here"
                        )
                    results["hex_diff"] = hex_diff

                except (OSError, IOError):
                    pass

            self.progress.emit(100)
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))

    def _compare_directories(self, dir1: str, dir2: str) -> dict:
        summary: dict[str, Any] = {
            "mode": "directory",
            "root1": dir1,
            "root2": dir2,
            "differences": [],
            "files": [],
        }
        map1 = {}
        map2 = {}

        for root, dirs, files in os.walk(dir1):
            for name in files:
                rel = os.path.relpath(os.path.join(root, name), dir1)
                map1[rel] = os.path.join(root, name)
        for root, dirs, files in os.walk(dir2):
            for name in files:
                rel = os.path.relpath(os.path.join(root, name), dir2)
                map2[rel] = os.path.join(root, name)

        all_keys = sorted(set(map1) | set(map2))
        identical = 0
        for idx, rel in enumerate(all_keys):
            if idx % 50 == 0 and all_keys:
                self.progress.emit(10 + int(85 * idx / len(all_keys)))
            if rel not in map1:
                summary["differences"].append(f"Only in second folder: {rel}")
            elif rel not in map2:
                summary["differences"].append(f"Only in first folder: {rel}")
            else:
                try:
                    size1 = os.path.getsize(map1[rel])
                    size2 = os.path.getsize(map2[rel])
                    if size1 != size2:
                        summary["differences"].append(
                            f"Size differs: {rel} ({size1:,} vs {size2:,} bytes)"
                        )
                    # filecmp stops at the first differing block — much cheaper than two full hashes
                    elif not filecmp.cmp(map1[rel], map2[rel], shallow=False):
                        summary["differences"].append(f"Content differs: {rel}")
                    else:
                        identical += 1
                except OSError as e:
                    summary["differences"].append(f"Unreadable: {rel} ({e})")
        summary["identical_count"] = identical
        summary["total_count"] = len(all_keys)
        return summary

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
            differences.append(
                f"Permissions: {info1.permissions.octal} vs {info2.permissions.octal}"
            )

        # Timestamps (allow small differences)
        time_diff_threshold = 2  # seconds
        if abs(info1.modified - info2.modified) > time_diff_threshold:
            differences.append(
                f"Modified: {info1.modified_str} vs {info2.modified_str}"
            )

        # Hashes (if computed)
        for algo in ["md5", "sha1", "sha256"]:
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
        self._file1_path: str | None = None
        self._file2_path: str | None = None
        self._thread: QThread | None = None
        self._worker: ComparisonWorker | None = None

        self._build_ui()

    def set_first_path(self, path: str):
        """Pre-fill File 1 (e.g. with the file currently open in the main window)."""
        if path and os.path.isfile(path):
            self._file1_path = path
            self._file1_label.setText(os.path.basename(path))
            self._file1_label.setToolTip(path)
            self._update_compare_button()

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

        self._swap_btn = QPushButton("⇄")
        self._swap_btn.setToolTip("Swap File 1 and File 2")
        self._swap_btn.setFixedWidth(40)
        self._swap_btn.clicked.connect(self._swap)
        selection_layout.addWidget(self._swap_btn)

        layout.addWidget(selection_group)

        self._directory_mode_chk = QCheckBox("Compare directories instead")
        self._directory_mode_chk.stateChanged.connect(self._on_directory_mode_changed)
        layout.addWidget(self._directory_mode_chk)

        self._verdict = QLabel("")
        self._verdict.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._verdict)

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
        self._summary_text.setFontPointSize(10)
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
        self._text_diff_edit.setFontPointSize(10)
        text_layout.addWidget(self._text_diff_edit)

        # Hex diff tab
        hex_tab = QWidget()
        self._content_tabs.addTab(hex_tab, "Hex Differences")
        hex_layout = QVBoxLayout(hex_tab)
        self._hex_diff_edit = QTextEdit()
        self._hex_diff_edit.setReadOnly(True)
        self._hex_diff_edit.setFontPointSize(10)
        hex_layout.addWidget(self._hex_diff_edit)

    def _select_file1(self):
        if self._directory_mode_chk.isChecked():
            path = QFileDialog.getExistingDirectory(self, "Select First Folder")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select First File")
        if path:
            self._file1_path = path
            self._file1_label.setText(
                os.path.basename(path) if os.path.isfile(path) else path
            )
            self._file1_label.setToolTip(path)
            self._update_compare_button()

    def _select_file2(self):
        if self._directory_mode_chk.isChecked():
            path = QFileDialog.getExistingDirectory(self, "Select Second Folder")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select Second File")
        if path:
            self._file2_path = path
            self._file2_label.setText(
                os.path.basename(path) if os.path.isfile(path) else path
            )
            self._file2_label.setToolTip(path)
            self._update_compare_button()

    def _swap(self):
        self._file1_path, self._file2_path = self._file2_path, self._file1_path
        t1, t2 = self._file1_label.text(), self._file2_label.text()
        self._file1_label.setText(t2)
        self._file2_label.setText(t1)
        tt1, tt2 = self._file1_label.toolTip(), self._file2_label.toolTip()
        self._file1_label.setToolTip(tt2)
        self._file2_label.setToolTip(tt1)

    def _on_directory_mode_changed(self):
        if self._directory_mode_chk.isChecked():
            self._select_file1_btn.setText("Select Folder 1…")
            self._select_file2_btn.setText("Select Folder 2…")
            self._compare_btn.setText("Compare Folders")
        else:
            self._select_file1_btn.setText("Select File 1…")
            self._select_file2_btn.setText("Select File 2…")
            self._compare_btn.setText("Compare Files")
        self._file1_path = None
        self._file2_path = None
        self._file1_label.setText("No file selected")
        self._file2_label.setText("No file selected")
        self._update_compare_button()

    def _update_compare_button(self):
        # Paths are reset to None when switching file/directory mode, so check values, not attributes
        enabled = (
            bool(self._file1_path) and bool(self._file2_path) and self._thread is None
        )
        self._compare_btn.setEnabled(enabled)

    def _compare_files(self):
        if not (self._file1_path and self._file2_path) or self._thread is not None:
            return
        self._verdict.setText("")

        self._compare_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)

        worker = ComparisonWorker(
            self._file1_path,
            self._file2_path,
            compare_dirs=self._directory_mode_chk.isChecked(),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._progress.setValue)
        worker.finished.connect(self._on_comparison_done)
        worker.finished.connect(thread.quit)
        worker.error.connect(self._on_comparison_error)
        worker.error.connect(thread.quit)
        thread.finished.connect(lambda: self._progress.setVisible(False))
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._worker = worker
        self._thread = thread
        thread.start()

    def _on_thread_finished(self):
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self._update_compare_button()

    def done(self, a0):
        # Don't destroy the dialog while a comparison thread is still running
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
        super().done(a0)

    def _on_comparison_done(self, results: dict):
        self._results = results
        self._display_results(results)

    def _on_comparison_error(self, error: str):
        self._summary_text.setPlainText(f"Error during comparison:\n{error}")
        self._set_verdict(f"✕  Comparison failed: {error}", ERROR)

    def _set_verdict(self, text: str, color: str):
        self._verdict.setText(text)
        self._verdict.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {color};"
        )

    def _render_diff(self, lines: list[str]):
        """Unified diff with +/- lines coloured, rendered as lightweight HTML."""
        out = []
        for line in lines[:20000]:
            esc = html.escape(line.rstrip("\n"))
            if line.startswith("+++") or line.startswith("---"):
                out.append(f'<span style="color:{TEXT_MUTED}">{esc}</span>')
            elif line.startswith("@@"):
                out.append(f'<span style="color:{INFO}">{esc}</span>')
            elif line.startswith("+"):
                out.append(f'<span style="color:{SUCCESS}">{esc}</span>')
            elif line.startswith("-"):
                out.append(f'<span style="color:{ERROR}">{esc}</span>')
            else:
                out.append(esc)
        self._text_diff_edit.setHtml(
            '<pre style="margin:0">' + "\n".join(out) + "</pre>"
        )

    def _display_results(self, results: dict):
        if results.get("mode") == "directory":
            differences = results.get("differences", [])
            summary = f"""Directory Comparison Summary
{"=" * 40}

Folder 1: {results.get("root1")}
Folder 2: {results.get("root2")}

Differences Found: {len(differences)}
"""
            if differences:
                summary += "\nDifferences:\n"
                for diff in differences:
                    summary += f"• {diff}\n"
            else:
                summary += "\nNo differences were detected."
            self._summary_text.setPlainText(summary)
            self._diff_list.clear()
            for diff in differences:
                self._diff_list.addItem(QListWidgetItem(diff))
            self._text_diff_edit.setPlainText(
                "Directory comparison does not support text diff."
            )
            self._hex_diff_edit.setPlainText(
                "Directory comparison does not support hex diff."
            )
            if differences:
                self._set_verdict(
                    f"≠  {len(differences):,} difference(s) · "
                    f"{results.get('identical_count', 0):,} of {results.get('total_count', 0):,} files identical",
                    WARNING,
                )
            else:
                self._set_verdict(
                    f"✓  Folders are identical ({results.get('total_count', 0):,} files)",
                    SUCCESS,
                )
            return

        info1 = results["info1"]
        info2 = results["info2"]
        differences = results.get("differences", [])

        # Summary
        summary = f"""File Comparison Summary
{"=" * 40}

File 1: {info1.path}
File 2: {info2.path}

Basic Properties:
- File 1 size: {info1.size_human}
- File 2 size: {info2.size_human}
- File 1 type: {info1.mime_type}
- File 2 type: {info2.mime_type}

Entropy (sampled):
- File 1: {results.get("entropy1", 0.0):.2f} bits/byte
- File 2: {results.get("entropy2", 0.0):.2f} bits/byte

Content: {"IDENTICAL (byte-for-byte)" if results.get("identical") else "different"}

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

        if results.get("identical"):
            self._set_verdict("✓  Files are byte-for-byte identical", SUCCESS)
        else:
            self._set_verdict(
                f"≠  Files differ  ·  {len(differences)} property difference(s)",
                WARNING,
            )

        # Content comparison
        if results.get("identical"):
            self._text_diff_edit.setPlainText("Files are identical.")
        elif "text_diff" in results:
            self._render_diff(results["text_diff"])
            self._content_tabs.setCurrentIndex(0)
        else:
            self._text_diff_edit.setPlainText(
                "No text diff available (files are binary or larger than 4 MB)"
            )
            self._content_tabs.setCurrentIndex(1)

        if "hex_diff" in results and results["hex_diff"]:
            self._hex_diff_edit.setPlainText("\n".join(results["hex_diff"]))
        else:
            self._hex_diff_edit.setPlainText(
                "No hex differences found or files are identical"
            )
