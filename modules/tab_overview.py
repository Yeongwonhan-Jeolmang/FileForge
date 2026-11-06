"""
tab_overview.py — "Overview" tab: summary cards for a loaded file.
"""

from __future__ import annotations
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QScrollArea, QFrame, QSizePolicy, QPushButton, QStackedWidget,
    QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QPixmap, QImageReader
from modules.file_info import FileInfo
from modules.widgets import (
    KVRow, SectionLabel, HSep, TagChip, kind_icon, kind_color, Card,
    EntropyGraph, EmptyState, copy_to_clipboard, reveal_in_file_manager,
    open_with_default_app,
)
from modules.theme import (
    BG_PANEL, BG_CARD, BG_MID, ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BORDER, SUCCESS, ERROR, WARNING, INFO, PURPLE, BG_HOVER, entropy_color, rgba,
)
from modules.entropy_calculator import (
    calculate_entropy, entropy_percentage, entropy_description, entropy_profile,
)


class EntropyWorker(QObject):
    """Worker for calculating entropy in background thread."""
    finished = pyqtSignal(float, float, str)  # entropy, percentage, description
    profile_ready = pyqtSignal(list)          # per-region entropy values

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            entropy = calculate_entropy(self.file_path, sample_size=1_000_000)  # 1MB sample
            entropy_pct = entropy_percentage(entropy)
            entropy_desc = entropy_description(entropy)
            self.finished.emit(entropy, entropy_pct, entropy_desc)
            self.profile_ready.emit(entropy_profile(self.file_path))
        except Exception:
            # Emit default values on error
            self.finished.emit(0.0, 0.0, "Error calculating entropy")
            self.profile_ready.emit([])


class OverviewTab(QWidget):
    open_requested = pyqtSignal()          # empty-state "Open File…" button
    file_requested = pyqtSignal(str)       # recent-file shortcut clicked
    navigate_requested = pyqtSignal(str)   # jump to another tab, e.g. "hashes"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entropy_card = None  # Store reference to entropy card for updates
        self._info: FileInfo | None = None
        self._threads: dict[QThread, EntropyWorker] = {}   # keeps workers alive until done
        self._entropy_token = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack)

        # Page 0: empty state
        self._empty = EmptyState(
            "🗂", "No file loaded",
            "Drop a file anywhere on this window, pick one from the sidebar, or open one below.",
            "Open File…",
        )
        self._empty.action_clicked.connect(self.open_requested)
        self._recent_box = QVBoxLayout()
        self._recent_box.setSpacing(4)
        self._empty.extra_layout().addLayout(self._recent_box)
        self._stack.addWidget(self._empty)

        # Page 1: details
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._stack.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(24, 22, 24, 24)
        self._layout.setSpacing(14)
        self._layout.addStretch()

        self._rows: list[KVRow] = []
        self._entropy_bar: QProgressBar | None = None
        self._entropy_desc: QLabel | None = None
        self._entropy_graph: EntropyGraph | None = None

    # ── Public ─────────────────────────────────────────────────────────

    def load(self, info: FileInfo):
        self._info = info
        self._clear()
        self._build(info)
        self._stack.setCurrentIndex(1)

    def clear(self):
        self._info = None
        self._entropy_token += 1
        self._clear()
        self._stack.setCurrentIndex(0)

    def set_recent_files(self, paths: list[str]):
        """Show a few recent files as one-click shortcuts on the empty page."""
        while self._recent_box.count():
            item = self._recent_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        existing = [p for p in paths if os.path.isfile(p)][:5]
        if not existing:
            return
        title = QLabel("RECENT")
        title.setObjectName("sectionLabel")
        title.setAlignment(Qt.AlignCenter)
        self._recent_box.addWidget(title)
        for path in existing:
            btn = QPushButton(f"{kind_icon(_kind_for(path))}  {os.path.basename(path)}")
            btn.setObjectName("ghost")
            btn.setToolTip(path)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, p=path: self.file_requested.emit(p))
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(btn)
            row.addStretch()
            self._recent_box.addLayout(row)

    def shutdown(self):
        self._entropy_token += 1
        for t in list(self._threads):
            t.quit()
            t.wait(2000)

    # ── Private ────────────────────────────────────────────────────────

    def _clear(self):
        self._entropy_card = None
        self._entropy_bar = None
        self._entropy_desc = None
        self._entropy_graph = None
        while self._layout.count() > 1:  # keep the stretch
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                _delete_layout(item.layout())

    def _add_section(self, title: str):
        lbl = SectionLabel(title)
        self._layout.insertWidget(self._layout.count() - 1, lbl)

    def _add_card(self, widget: QWidget):
        self._layout.insertWidget(self._layout.count() - 1, widget)

    def _section_block(self, title: str, widget: QWidget) -> QWidget:
        """Section label + card stacked, for use inside the two-column grid."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(SectionLabel(title))
        lay.addWidget(widget, 1)
        return box

    def _build(self, info: FileInfo):
        # ── Hero banner ────────────────────────────────────────────────
        hero = self._make_hero(info)
        self._add_card(hero)

        # ── Two-column grid: identity / timestamps / permissions / analysis
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        identity = [
            ("Name",      info.name),
            ("Full Path", info.path),
            ("Size",      f"{info.size_human}  ({info.size:,} bytes)"),
            ("MIME Type", info.mime_type),
            ("Kind",      info.kind.capitalize()),
        ]
        if info.detected_type:
            identity.append(("Detected", info.detected_type))
        id_card = self._make_card(identity)
        if info.extension_mismatch:
            warn = QLabel(f"⚠  The extension '{info.suffix or '(none)'}' does not match the content "
                          f"({info.detected_type}).")
            warn.setWordWrap(True)
            warn.setStyleSheet(
                f"color: {WARNING}; background: {rgba(WARNING, 0.10)}; border: 1px solid {rgba(WARNING, 0.35)};"
                f"border-radius: 5px; padding: 6px 8px; font-size: 11px;"
            )
            id_card.layout().addSpacing(6)
            id_card.layout().addWidget(warn)
        grid.addWidget(self._section_block("Identity", id_card), 0, 0)

        # ── Timestamps ─────────────────────────────────────────────────
        ts_card = self._make_card([
            ("Modified", info.modified_str),
            ("Accessed", info.accessed_str),
            ("Created",  info.created_str),
        ])
        grid.addWidget(self._section_block("Timestamps", ts_card), 0, 1)

        # ── Permissions ────────────────────────────────────────────────
        perm = info.permissions
        perm_card = self._make_card([
            ("Mode (symbolic)", perm.symbolic),
            ("Mode (octal)",    perm.octal.replace("0o", "0")),
            ("Owner",           info.owner),
            ("Group",           info.group),
        ])
        grid.addWidget(self._section_block("Permissions", perm_card), 1, 0)

        # ── Entropy ────────────────────────────────────────────────────
        # Start entropy calculation in background
        self._entropy_card = self._make_entropy_card(0.0, 0.0, "Calculating...")
        grid.addWidget(self._section_block("Analysis", self._entropy_card), 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self._add_card(grid_host)
        self._start_entropy_calculation(info.path)

        # ── Image metadata ─────────────────────────────────────────────
        if info.image_meta:
            im = info.image_meta
            self._add_section("Image Properties")
            megapixels = im.width * im.height / 1_000_000
            rows = [
                ("Dimensions", f"{im.width} × {im.height} px  ({megapixels:.1f} MP)"),
                ("Color Mode", im.mode),
                ("Format",     im.format),
            ]
            if im.dpi:
                try:
                    rows.append(("DPI", f"{float(im.dpi[0]):.0f} × {float(im.dpi[1]):.0f}"))
                except (TypeError, ValueError, IndexError):
                    pass
            if im.has_exif:
                for key in ("Make", "Model", "DateTimeOriginal", "LensModel", "Software"):
                    if key in im.exif:
                        rows.append((_humanize(key), im.exif[key]))
                rows.append(("EXIF Data", f"{len(im.exif)} tags present — see Analysis › Advanced"))
            card = self._make_card(rows)
            self._add_card(card)

        # ── Audio metadata ─────────────────────────────────────────────
        if info.audio_meta:
            am = info.audio_meta
            self._add_section("Audio Properties")
            rows = []
            if am.duration:
                rows.append(("Duration", _fmt_duration(am.duration)))
            if am.bitrate:
                rows.append(("Bitrate", f"{am.bitrate // 1000:,} kbps"))
            if am.sample_rate:
                rows.append(("Sample Rate", f"{am.sample_rate:,} Hz"))
            if am.channels:
                rows.append(("Channels", {1: "1 (mono)", 2: "2 (stereo)"}.get(am.channels, str(am.channels))))
            for k, v in list(am.tags.items())[:8]:
                rows.append((k.capitalize(), v))
            if rows:
                card = self._make_card(rows)
                self._add_card(card)

        # ── Video metadata ─────────────────────────────────────────────
        if info.video_meta:
            vm = info.video_meta
            rows = []
            if vm.width and vm.height:
                rows.append(("Resolution", f"{vm.width} × {vm.height}"))
            if vm.duration:
                rows.append(("Duration", _fmt_duration(vm.duration)))
            if vm.codec:
                rows.append(("Codec", vm.codec))
            if vm.bitrate:
                try:
                    rows.append(("Bitrate", f"{int(vm.bitrate) // 1000:,} kbps"))
                except (TypeError, ValueError):
                    pass
            if rows:
                self._add_section("Video Properties")
                self._add_card(self._make_card(rows))

        # ── Document metadata ──────────────────────────────────────────
        if info.document_meta:
            dm = info.document_meta
            rows = [("Type", dm.doc_type)]
            for label, value in (("Title", dm.title), ("Author", dm.author), ("Subject", dm.subject),
                                 ("Producer", dm.producer), ("Last edited by", dm.software if dm.doc_type != 'PDF' else ''),
                                 ("Keywords", dm.topic if dm.doc_type != 'PDF' else dm.comment)):
                if value:
                    rows.append((label, str(value)))
            if dm.pages is not None:
                rows.append(("Sheets" if dm.doc_type == 'Spreadsheet' else
                             "Slides" if dm.doc_type == 'Presentation' else "Pages", str(dm.pages)))
            self._add_section("Document Properties")
            self._add_card(self._make_card(rows))

        # ── Extended attributes ────────────────────────────────────────
        if info.xattrs:
            self._add_section("Extended Attributes")
            rows = [(k, v[:300]) for k, v in info.xattrs.items()]
            card = self._make_card(rows)
            self._add_card(card)

        if info.windows_ads:
            self._add_section("Alternate Data Streams")
            rows = [(k, f"{v:,} bytes") for k, v in info.windows_ads.items()]
            self._add_card(self._make_card(rows))

    def _start_entropy_calculation(self, file_path: str):
        """Start entropy calculation in background thread."""
        self._entropy_token += 1
        token = self._entropy_token

        worker = EntropyWorker(file_path)
        thread = QThread(self)          # parented: never garbage-collected while running
        worker.moveToThread(thread)
        worker.finished.connect(lambda e, p, d, t=token: self._on_entropy_calculated(e, p, d, t))
        worker.profile_ready.connect(lambda vals, t=token: self._on_profile_ready(vals, t))
        worker.profile_ready.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda th=thread: self._release_thread(th))
        self._threads[thread] = worker
        # Kept for compatibility with code that inspected these attributes
        self._entropy_worker = worker
        self._entropy_thread = thread
        thread.start()

    def _release_thread(self, thread: QThread):
        self._threads.pop(thread, None)
        thread.deleteLater()

    def _on_entropy_calculated(self, entropy: float, percentage: float, description: str, token: int = None):
        """Handle entropy calculation completion."""
        if token is not None and token != self._entropy_token:
            return   # result for a file that is no longer displayed
        if self._entropy_card:
            # Update the existing entropy card
            self._update_entropy_card(self._entropy_card, entropy, percentage, description)

    def _on_profile_ready(self, values: list, token: int):
        if token == self._entropy_token and self._entropy_graph is not None:
            self._entropy_graph.set_values(values)
            if not values:
                self._entropy_graph.hide()

    def _update_entropy_card(self, card: QWidget, entropy: float, percentage: float, description: str):
        """Update entropy card with calculated values."""
        color = entropy_color(entropy)
        if self._entropy_bar is not None:
            self._entropy_bar.setValue(int(percentage))
            self._entropy_bar.setFormat(f"{entropy:.2f} bits/byte ({percentage:.1f}%)")
            self._entropy_bar.setStyleSheet(self._bar_style(color))
        if self._entropy_desc is not None:
            hint = ""
            if entropy >= 7.5:
                hint = " — typical of compressed or encrypted data"
            elif entropy < 1.0 and self._info and self._info.size > 0:
                hint = " — lots of repetition / padding"
            self._entropy_desc.setText(description + hint)

    @staticmethod
    def _bar_style(color: str) -> str:
        return f"""
            QProgressBar {{
                border: 1px solid {BORDER};
                border-radius: 5px;
                text-align: center;
                background: {BG_MID};
                color: {TEXT_PRIMARY};
                min-height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {rgba(color, 0.75)};
                border-radius: 4px;
            }}
        """

    # ── Builders ───────────────────────────────────────────────────────

    def _make_hero(self, info: FileInfo) -> QWidget:
        frame = Card(object_name="heroCard")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(18)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(72, 72)
        icon_lbl.setAlignment(Qt.AlignCenter)
        thumb = _thumbnail(info.path, 72) if info.kind == "image" else None
        if thumb is not None:
            icon_lbl.setPixmap(thumb)
            icon_lbl.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 8px; background: {BG_MID};")
        else:
            color = kind_color(info.kind)
            icon_lbl.setText(kind_icon(info.kind))
            icon_lbl.setStyleSheet(
                f"font-size: 34px; background: {rgba(color, 0.14)}; border: 1px solid {rgba(color, 0.35)};"
                f"border-radius: 12px;"
            )
        layout.addWidget(icon_lbl, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        name_lbl = QLabel(info.name)
        name_lbl.setStyleSheet(f"font-size: 19px; font-weight: bold; color: {TEXT_PRIMARY};")
        name_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        name_lbl.setWordWrap(True)

        sub_lbl = QLabel(f"{info.size_human}  ·  {info.mime_type}  ·  modified {info.modified_str}")
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY};")

        path_lbl = QLabel(os.path.dirname(info.path))
        path_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_lbl.setToolTip(info.path)

        # ── Flags (chips) ─────────────────────────────────────────────
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(TagChip(info.kind.capitalize(), kind_color(info.kind)))
        if info.is_symlink:
            chips.addWidget(TagChip("Symlink", ACCENT))
        if info.is_hidden:
            chips.addWidget(TagChip("Hidden", PURPLE))
        if not info.permissions.owner_write:
            chips.addWidget(TagChip("Read-only", INFO))
        if info.permissions.owner_exec:
            chips.addWidget(TagChip("Executable", ERROR))
        if info.extension_mismatch:
            chips.addWidget(TagChip("Extension mismatch", WARNING))
        if info.xattrs:
            chips.addWidget(TagChip(f"{len(info.xattrs)} xattr", TEXT_SECONDARY))
        chips.addStretch()

        text_col.addWidget(name_lbl)
        text_col.addWidget(sub_lbl)
        text_col.addWidget(path_lbl)
        text_col.addSpacing(2)
        text_col.addLayout(chips)
        layout.addLayout(text_col, 1)

        # ── Quick actions ────────────────────────────────────────────
        actions = QVBoxLayout()
        actions.setSpacing(6)
        for label, tip, handler in (
            ("Copy Path", "Copy the full path to the clipboard", lambda: copy_to_clipboard(info.path)),
            ("Reveal", "Show in Explorer / Finder / file manager", lambda: reveal_in_file_manager(info.path)),
            ("Open", "Open with the default application", lambda: open_with_default_app(info.path)),
            ("Copy Summary", "Copy a plain-text summary of this file", lambda: copy_to_clipboard(self._summary_text(info))),
        ):
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(120)
            btn.clicked.connect(handler)
            actions.addWidget(btn)
        actions.addStretch()
        layout.addLayout(actions)

        return frame

    def _make_card(self, rows: list[tuple[str, str]]) -> QWidget:
        frame = Card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 16, 12)
        layout.setSpacing(0)

        for key, val in rows:
            row = KVRow(key, val)
            layout.addWidget(row)
        layout.addStretch()

        return frame

    def _make_entropy_card(self, entropy: float, percentage: float, description: str) -> QWidget:
        frame = Card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title
        title_row = QHBoxLayout()
        title = QLabel("Shannon Entropy")
        title.setStyleSheet(f"font-weight: bold; color: {TEXT_PRIMARY};")
        title.setToolTip("How random the bytes are: 0 = constant, 8 = indistinguishable from random.\n"
                         "Compressed and encrypted data sit near 8.")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Progress bar
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(int(percentage))
        progress.setTextVisible(True)
        progress.setFormat("Calculating…" if description == "Calculating..." else
                           f"{entropy:.2f} bits/byte ({percentage:.1f}%)")
        progress.setStyleSheet(self._bar_style(entropy_color(entropy)))
        layout.addWidget(progress)
        self._entropy_bar = progress

        # Description
        desc = QLabel(description)
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._entropy_desc = desc

        # Profile graph
        graph_lbl = QLabel("Entropy across the file")
        graph_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; letter-spacing: 1px;")
        layout.addSpacing(4)
        layout.addWidget(graph_lbl)
        self._entropy_graph = EntropyGraph()
        layout.addWidget(self._entropy_graph)
        layout.addStretch()

        return frame

    @staticmethod
    def _summary_text(info: FileInfo) -> str:
        lines = [
            f"Name:      {info.name}",
            f"Path:      {info.path}",
            f"Size:      {info.size_human} ({info.size:,} bytes)",
            f"MIME:      {info.mime_type}",
            f"Kind:      {info.kind}",
        ]
        if info.detected_type:
            lines.append(f"Detected:  {info.detected_type}" + ("  (EXTENSION MISMATCH)" if info.extension_mismatch else ""))
        lines += [
            f"Modified:  {info.modified_str}",
            f"Accessed:  {info.accessed_str}",
            f"Created:   {info.created_str}",
            f"Mode:      {info.permissions.symbolic}  ({info.permissions.octal})",
            f"Owner:     {info.owner}:{info.group}",
        ]
        return "\n".join(lines)


# ── Module helpers ─────────────────────────────────────────────────────────

def _kind_for(path: str) -> str:
    from modules.file_info import classify_path
    return classify_path(path)


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _humanize(key: str) -> str:
    """'DateTimeOriginal' → 'Date Time Original'."""
    out = []
    for i, ch in enumerate(key):
        if ch.isupper() and i and not key[i - 1].isupper():
            out.append(" ")
        out.append(ch)
    return "".join(out)


def _thumbnail(path: str, size: int):
    """
    Fast thumbnail via QImageReader: asking for a scaled size lets JPEG decode
    at reduced resolution instead of decoding the full image first.
    """
    try:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        src = reader.size()
        if not src.isValid() or src.width() <= 0 or src.height() <= 0:
            return None
        scaled = src.scaled(QSize(size * 2, size * 2), Qt.KeepAspectRatio)
        reader.setScaledSize(scaled)
        img = reader.read()
        if img.isNull():
            return None
        pix = QPixmap.fromImage(img).scaled(size - 4, size - 4, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pix
    except Exception:
        return None


def _delete_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _delete_layout(item.layout())
