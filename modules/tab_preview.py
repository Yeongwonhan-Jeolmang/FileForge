"""
tab_preview.py — Rich preview pane for files, archives, and document/media metadata.
"""

from __future__ import annotations
import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QTextEdit, QPlainTextEdit,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QSplitter, QHeaderView,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QColor, QImageReader

from modules.file_info import FileInfo
from modules.archive_tools import list_archive_contents, archive_entry_count
from modules.metadata_cache import get_cached_hashes
from modules.widgets import SectionLabel, StatusBanner, Card
from modules.theme import BG_CARD, BORDER, TEXT_SECONDARY, TEXT_MUTED, ACCENT, BG_MID

ARCHIVE_PREVIEW_LIMIT = 1000
TEXT_PREVIEW_CHARS = 200_000


class PreviewTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._info: FileInfo | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._banner = StatusBanner()
        outer.addWidget(self._banner)

        top = QWidget()
        tl = QHBoxLayout(top)
        tl.setContentsMargins(24, 16, 24, 8)
        tl.setSpacing(10)

        self._path_label = QLabel('No file loaded')
        self._path_label.setStyleSheet(f'color: {TEXT_SECONDARY};')
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._type_label = QLabel('')
        self._type_label.setStyleSheet(f'color: {ACCENT}; font-weight: bold;')

        self._export_btn = QPushButton('Export Metadata…')
        self._export_btn.clicked.connect(self._export_metadata)
        self._export_btn.setObjectName('primary')
        self._export_btn.setEnabled(False)

        tl.addWidget(self._path_label, 1)
        tl.addWidget(self._type_label)
        tl.addWidget(self._export_btn)
        outer.addWidget(top)

        splitter = QSplitter(Qt.Vertical)
        outer.addWidget(splitter)

        self._preview_area = QScrollArea()
        self._preview_area.setWidgetResizable(True)
        self._preview_area.setFrameShape(QFrame.NoFrame)
        self._preview_content = QWidget()
        self._preview_layout = QVBoxLayout(self._preview_content)
        self._preview_layout.setContentsMargins(20, 20, 20, 20)
        self._preview_layout.setSpacing(16)
        self._preview_area.setWidget(self._preview_content)
        splitter.addWidget(self._preview_area)

        self._meta_tree = QTreeWidget()
        self._meta_tree.setColumnCount(2)
        self._meta_tree.setHeaderLabels(['Property', 'Value'])
        self._meta_tree.setAlternatingRowColors(True)
        self._meta_tree.setRootIsDecorated(False)
        self._meta_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        splitter.addWidget(self._meta_tree)

        splitter.setSizes([520, 260])

    def load(self, info: FileInfo):
        self._info = info
        self._path_label.setText(info.path)
        self._type_label.setText(info.kind.capitalize())
        self._export_btn.setEnabled(True)
        self._render_preview(info)
        self._populate_metadata(info)

    def clear(self):
        self._info = None
        self._path_label.setText('No file loaded')
        self._type_label.setText('')
        self._export_btn.setEnabled(False)
        self._clear_preview()
        self._meta_tree.clear()

    def _render_preview(self, info: FileInfo):
        self._clear_preview()
        preview_widget = None

        if info.kind == 'image':
            preview_widget = self._image_preview(info)
        elif info.kind == 'text':
            preview_widget = self._text_preview(info)
        elif info.kind == 'document':
            preview_widget = self._document_preview(info)
        elif info.kind == 'archive':
            preview_widget = self._archive_preview(info)
        elif info.kind == 'audio':
            preview_widget = self._audio_preview(info)
        elif info.kind == 'video':
            preview_widget = self._video_preview(info)
        else:
            preview_widget = self._generic_preview(info)

        if preview_widget:
            self._preview_layout.addWidget(preview_widget)

    def _clear_preview(self):
        while self._preview_layout.count():
            item = self._preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _image_preview(self, info: FileInfo) -> QWidget:
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        target = 720
        pixmap = None

        # 1) Qt's reader can decode JPEG at reduced size (fast) and honours EXIF rotation
        reader = QImageReader(info.path)
        reader.setAutoTransform(True)
        src = reader.size()
        if src.isValid() and src.width() > 0:
            if src.width() > target or src.height() > target:
                reader.setScaledSize(src.scaled(QSize(target, target), Qt.KeepAspectRatio))
            img = reader.read()
            if not img.isNull():
                pixmap = QPixmap.fromImage(img)

        # 2) Fall back to Pillow for formats Qt lacks plugins for (CMYK, 16-bit, PSD…)
        if pixmap is None:
            try:
                from PIL import Image, ImageOps
                from PIL.ImageQt import ImageQt
                resample = getattr(Image, "Resampling", Image).LANCZOS
                with Image.open(info.path) as img:
                    img.draft("RGB", (target, target))      # cheap JPEG down-scaling
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((target, target), resample)
                    if img.mode not in ("RGB", "RGBA"):
                        img = img.convert("RGBA")
                    pixmap = QPixmap.fromImage(ImageQt(img).copy())
            except Exception:
                pixmap = None

        if pixmap is not None and not pixmap.isNull():
            label.setPixmap(pixmap)
            if info.image_meta:
                label.setToolTip(f"{info.image_meta.width} × {info.image_meta.height} px (shown scaled)")
        else:
            label.setText('Unable to render image preview.')

        label.setStyleSheet(f'background: {BG_MID}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;')
        return label

    def _text_preview(self, info: FileInfo) -> QWidget:
        edit = QPlainTextEdit()      # much faster than QTextEdit for large plain text
        edit.setReadOnly(True)
        edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        edit.setMinimumHeight(360)
        try:
            with open(info.path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read(TEXT_PREVIEW_CHARS)
            if info.size > len(text.encode('utf-8', errors='replace')):
                text += f"\n\n… preview truncated ({info.size_human} total)"
            edit.setPlainText(text)
        except Exception as e:
            edit.setPlainText(f'Unable to load text preview: {e}')
        return edit

    def _document_preview(self, info: FileInfo) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        lines = [f"Document preview for {info.name}"]
        if info.document_meta:
            meta = info.document_meta
            lines.append(f"Type: {meta.doc_type}")
            if meta.title:
                lines.append(f"Title: {meta.title}")
            if meta.author:
                lines.append(f"Author: {meta.author}")
            if meta.pages is not None:
                lines.append(f"Pages: {meta.pages}")
            if meta.topic:
                lines.append(f"Topic: {meta.topic}")
            if meta.software:
                lines.append(f"Software: {meta.software}")
            if meta.comment:
                lines.append(f"Comment: {meta.comment}")
            if meta.snippet:
                lines.append('')
                lines.append('Snippet:')
                lines.append(meta.snippet)
        else:
            lines.append('No detailed document preview available.')
        label = QLabel('\n'.join(lines))
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setStyleSheet(f'background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;')
        layout.addWidget(label)
        return widget

    def _archive_preview(self, info: FileInfo) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        contents = list_archive_contents(info.path, limit=ARCHIVE_PREVIEW_LIMIT)
        if contents:
            total = archive_entry_count(info.path)
            files = [c for c in contents if not c.get('is_dir')]
            uncompressed = sum(int(c['size'] or 0) for c in files)
            shown = f"{len(contents):,}" + (f" of {total:,}" if total and total > len(contents) else
                                            ("+" if len(contents) >= ARCHIVE_PREVIEW_LIMIT else ""))
            ratio = ""
            if uncompressed and info.size:
                ratio = f"  ·  ratio {info.size / uncompressed:.0%}"
            encrypted = any(c.get('encrypted') for c in contents)
            header = QLabel(f'Archive contains {shown} items  ·  {len(files):,} files  ·  '
                            f'{_human(uncompressed)} uncompressed{ratio}'
                            + ('  ·  🔒 encrypted entries' if encrypted else ''))
            header.setStyleSheet(f'color: {TEXT_SECONDARY};')
            layout.addWidget(header)
            tree = QTreeWidget()
            tree.setColumnCount(3)
            tree.setHeaderLabels(['Name', 'Size', 'Compressed'])
            tree.setAlternatingRowColors(True)
            tree.setRootIsDecorated(False)
            tree.setUniformRowHeights(True)
            tree.setMinimumHeight(360)
            tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
            items = []
            for entry in contents:
                icon = '📁 ' if entry.get('is_dir') else ('🔒 ' if entry.get('encrypted') else '')
                item = QTreeWidgetItem([icon + entry['name'], entry.get('size_human', entry['size']),
                                        entry.get('compressed_human', entry['compressed'])])
                item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
                items.append(item)
            tree.addTopLevelItems(items)
            layout.addWidget(tree)
        else:
            label = QLabel('Archive preview is unavailable for this file type or package support is missing.')
            label.setStyleSheet(f'color: {TEXT_SECONDARY};')
            layout.addWidget(label)

        return widget

    def _audio_preview(self, info: FileInfo) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        text = ['Audio preview available.']
        if info.audio_meta:
            am = info.audio_meta
            if am.duration:
                mins, secs = divmod(int(am.duration), 60)
                text.append(f'Duration: {mins}:{secs:02d}')
            if am.bitrate:
                text.append(f'Bitrate: {am.bitrate:,} bps')
            if am.sample_rate:
                text.append(f'Sample rate: {am.sample_rate:,} Hz')
            if am.channels:
                text.append(f'Channels: {am.channels}')
            if am.tags:
                text.append('Tags:')
                for key, value in list(am.tags.items())[:8]:
                    text.append(f'  • {key}: {value}')
        label = QLabel('\n'.join(text))
        label.setWordWrap(True)
        label.setStyleSheet(f'background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;')
        layout.addWidget(label)
        return widget

    def _video_preview(self, info: FileInfo) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        text = ['Video preview available.']
        if info.video_meta:
            vm = info.video_meta
            if vm.duration:
                mins, secs = divmod(int(vm.duration), 60)
                text.append(f'Duration: {mins}:{secs:02d}')
            if vm.width and vm.height:
                text.append(f'Resolution: {vm.width}×{vm.height}')
            if vm.bitrate:
                text.append(f'Bitrate: {vm.bitrate:,} bps')
            if vm.codec:
                text.append(f'Codec: {vm.codec}')
        label = QLabel('\n'.join(text))
        label.setWordWrap(True)
        label.setStyleSheet(f'background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;')
        layout.addWidget(label)
        return widget

    def _generic_preview(self, info: FileInfo) -> QWidget:
        label = QLabel('No rich preview available for this file type. Use the Overview and Advanced tabs for more metadata.')
        label.setWordWrap(True)
        label.setStyleSheet(f'background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px;')
        return label

    def _populate_metadata(self, info: FileInfo) -> None:
        self._meta_tree.clear()
        self._add_meta('Name', info.name)
        self._add_meta('Kind', info.kind)
        self._add_meta('MIME Type', info.mime_type)
        self._add_meta('Size', f"{info.size_human} ({info.size:,} bytes)")
        if info.detected_type:
            self._add_meta('Detected Type', info.detected_type + ('  ⚠ extension mismatch' if info.extension_mismatch else ''))
        if info.image_meta:
            self._add_meta('Dimensions', f"{info.image_meta.width} × {info.image_meta.height} px")
            self._add_meta('Color Mode', info.image_meta.mode)
        if info.audio_meta and info.audio_meta.duration:
            mins, secs = divmod(int(info.audio_meta.duration), 60)
            self._add_meta('Duration', f"{mins}:{secs:02d}")
        if info.document_meta:
            self._add_meta('Document Type', info.document_meta.doc_type or 'Document')
            if info.document_meta.title:
                self._add_meta('Title', info.document_meta.title)
            if info.document_meta.author:
                self._add_meta('Author', info.document_meta.author)
            if info.document_meta.pages is not None:
                self._add_meta('Pages', str(info.document_meta.pages))
        if info.video_meta:
            if info.video_meta.codec:
                self._add_meta('Video Codec', info.video_meta.codec)
            if info.video_meta.width and info.video_meta.height:
                self._add_meta('Resolution', f'{info.video_meta.width}×{info.video_meta.height}')
        if info.windows_ads:
            self._add_meta('Windows ADS count', str(len(info.windows_ads)))
            for name, size in info.windows_ads.items():
                self._add_meta(f'ADS: {name}', f'{size} bytes')

    def _add_meta(self, key: str, value: str) -> None:
        item = QTreeWidgetItem([key, value])
        self._meta_tree.addTopLevelItem(item)

    def _export_metadata(self):
        if not self._info:
            return
        default = os.path.join(os.path.dirname(self._info.path), f"{self._info.name}.metadata.json")
        path, _ = QFileDialog.getSaveFileName(self, 'Export Metadata Report', default, filter='JSON Files (*.json)')
        if not path:
            return
        import json
        from dataclasses import asdict
        # Everything FileForge knows about the file, including nested metadata
        report = asdict(self._info)
        report['created'] = self._info.created_str
        report['modified'] = self._info.modified_str
        report['accessed'] = self._info.accessed_str
        report['created_epoch'] = self._info.created
        report['modified_epoch'] = self._info.modified
        report['accessed_epoch'] = self._info.accessed
        hashes = get_cached_hashes(self._info.path)
        for algo, digest in hashes.items():
            report[algo] = digest
        report = {k: v for k, v in report.items() if v not in (None, '', {}, [])}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str, ensure_ascii=False)
            self._banner.show_message('Metadata exported successfully.', 'success')
        except Exception as e:
            self._banner.show_message(str(e), 'error')


def _human(n: int) -> str:
    from modules.file_info import human_size
    return human_size(n)
