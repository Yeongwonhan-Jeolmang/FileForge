"""
theme.py — Centralised design tokens and QSS stylesheet for FileForge.
Pre-imported with Florian van den Bersselaar design
"""

# ── Palette ────────────────────────────────────────────────────────────────
BG_DARKEST  = "#0d0f12"
BG_DARK     = "#13161b"
BG_MID      = "#1b1f27"
BG_PANEL    = "#20252f"
BG_CARD     = "#252b37"
BG_HOVER    = "#2c3345"
BG_SELECTED = "#2f3850"

ACCENT      = "#f5a623"   # amber
ACCENT_DARK = "#c47f0a"
ACCENT_DIM  = "#7a5010"

TEXT_PRIMARY   = "#e8eaf0"
TEXT_SECONDARY = "#8a90a0"
TEXT_MUTED     = "#505870"
TEXT_ACCENT    = "#f5a623"

BORDER      = "#2a3040"
BORDER_FOCUS= "#f5a623"

SUCCESS     = "#4caf82"
WARNING     = "#f5a623"
ERROR       = "#e05c5c"
INFO        = "#5b9cf6"

# ── Full QSS stylesheet ────────────────────────────────────────────────────
STYLESHEET = f"""
/* ── Global ── */
QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    border: none;
    outline: none;
}}

QMainWindow {{
    background-color: {BG_DARKEST};
}}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background: {BG_DARKEST};
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BG_HOVER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_DIM};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_DARKEST};
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {BG_HOVER};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT_DIM};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Splitter ── */
QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}

/* ── Tab bar ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG_PANEL};
    border-radius: 4px;
}}
QTabBar::tab {{
    background: {BG_MID};
    color: {TEXT_SECONDARY};
    padding: 8px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    font-size: 12px;
    letter-spacing: 0.5px;
}}
QTabBar::tab:selected {{
    background: {BG_PANEL};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

/* ── Tree / List ── */
QTreeWidget, QListWidget, QTreeView, QListView {{
    background: {BG_PANEL};
    alternate-background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    selection-background-color: {BG_SELECTED};
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 4px 6px;
    border-radius: 2px;
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background: {BG_HOVER};
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {BG_SELECTED};
    color: {ACCENT};
}}
QHeaderView::section {{
    background: {BG_MID};
    color: {TEXT_SECONDARY};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:read-only {{
    background: {BG_MID};
    color: {TEXT_SECONDARY};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
    background: {BG_MID};
    width: 16px;
    border-radius: 2px;
}}

/* ── ComboBox ── */
QComboBox {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    min-width: 80px;
}}
QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{
    width: 24px;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    background: {BG_MID};
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {BG_SELECTED};
    selection-color: {ACCENT};
}}

/* ── Buttons ── */
QPushButton {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 7px 16px;
    font-size: 12px;
    letter-spacing: 0.5px;
}}
QPushButton:hover {{
    background: {BG_HOVER};
    border-color: {ACCENT_DIM};
    color: {ACCENT};
}}
QPushButton:pressed {{
    background: {ACCENT_DIM};
    border-color: {ACCENT};
}}
QPushButton#primary {{
    background: {ACCENT};
    color: {BG_DARKEST};
    border: none;
    font-weight: bold;
}}
QPushButton#primary:hover {{
    background: #f7b84a;
    color: {BG_DARKEST};
}}
QPushButton#primary:pressed {{
    background: {ACCENT_DARK};
}}
QPushButton#danger {{
    background: transparent;
    color: {ERROR};
    border: 1px solid {ERROR};
}}
QPushButton#danger:hover {{
    background: {ERROR};
    color: white;
}}
QPushButton:disabled {{
    background: {BG_MID};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

/* ── Check / Radio ── */
QCheckBox, QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background: {BG_CARD};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QRadioButton::indicator {{ border-radius: 8px; }}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Labels ── */
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}
QLabel#heading {{
    font-size: 18px;
    font-weight: bold;
    color: {ACCENT};
    letter-spacing: 2px;
}}
QLabel#subheading {{
    font-size: 11px;
    color: {TEXT_MUTED};
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QLabel#value {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#success {{ color: {SUCCESS}; }}
QLabel#error   {{ color: {ERROR};   }}
QLabel#warning {{ color: {WARNING}; }}

/* ── Group box ── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    margin-top: 16px;
    padding-top: 8px;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {ACCENT};
    background: {BG_DARK};
}}

/* ── Progress bar ── */
QProgressBar {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}

/* ── Status bar ── */
QStatusBar {{
    background: {BG_DARKEST};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: 11px;
}}

/* ── Menu ── */
QMenuBar {{
    background: {BG_DARKEST};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px;
}}
QMenuBar::item:selected {{
    background: {BG_HOVER};
    color: {ACCENT};
    border-radius: 3px;
}}
QMenu {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background: {BG_SELECTED};
    color: {ACCENT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 0;
}}

/* ── Tool tips ── */
QToolTip {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {ACCENT_DIM};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* ── Frames ── */
QFrame[frameShape="4"],   /* HLine */
QFrame[frameShape="5"] {{ /* VLine */
    background: {BORDER};
    max-height: 1px;
}}
"""