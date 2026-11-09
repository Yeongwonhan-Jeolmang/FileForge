"""
theme.py — Centralised design tokens and QSS stylesheet for FileForge.
Pre-imported with Florian van den Bersselaar design

Two palettes ship: "Dark" (the original amber-on-charcoal look) and "Light".
The palette is chosen once, at import time, from the user's saved settings,
because every module copies these tokens into its own inline styles when it
is imported. Changing the theme therefore takes effect after a restart.
"""

from __future__ import annotations
import os
import tempfile

# ── Palettes ───────────────────────────────────────────────────────────────
_DARK = dict(
    BG_DARKEST="#0d0f12",
    BG_DARK="#13161b",
    BG_MID="#1b1f27",
    BG_PANEL="#20252f",
    BG_CARD="#232935",
    BG_HOVER="#2c3345",
    BG_SELECTED="#2f3850",
    ACCENT="#f5a623",  # amber
    ACCENT_HOVER="#f7b84a",
    ACCENT_DARK="#c47f0a",
    ACCENT_DIM="#7a5010",
    ON_ACCENT="#0d0f12",  # text drawn on top of the accent colour
    TEXT_PRIMARY="#e8eaf0",
    TEXT_SECONDARY="#8a90a0",
    TEXT_MUTED="#5a6278",
    TEXT_ACCENT="#f5a623",
    BORDER="#2a3040",
    BORDER_FOCUS="#f5a623",
    SUCCESS="#4caf82",
    WARNING="#f5a623",
    ERROR="#e05c5c",
    INFO="#5b9cf6",
    PURPLE="#9d8cff",
    HEX_BG="#0b0d10",
    HEX_FG="#a0ffb0",
    HEX_OFFSET="#5b9cf6",
)

_LIGHT = dict(
    BG_DARKEST="#e7eaf0",
    BG_DARK="#f3f5f8",
    BG_MID="#eceff4",
    BG_PANEL="#ffffff",
    BG_CARD="#ffffff",
    BG_HOVER="#e4e9f1",
    BG_SELECTED="#fbe7c2",
    ACCENT="#c97d00",
    ACCENT_HOVER="#dd8c06",
    ACCENT_DARK="#a06200",
    ACCENT_DIM="#efcf91",
    ON_ACCENT="#ffffff",
    TEXT_PRIMARY="#1d2330",
    TEXT_SECONDARY="#566074",
    TEXT_MUTED="#8a93a6",
    TEXT_ACCENT="#c97d00",
    BORDER="#d6dbe4",
    BORDER_FOCUS="#c97d00",
    SUCCESS="#1f9d63",
    WARNING="#c77c02",
    ERROR="#d64545",
    INFO="#2f6fdc",
    PURPLE="#6b5bd6",
    HEX_BG="#fbfcfd",
    HEX_FG="#1f6f43",
    HEX_OFFSET="#2f6fdc",
)

PALETTES = {"Dark": _DARK, "Light": _LIGHT}
THEME_NAMES = ["Dark", "Light"]
DEFAULT_FONT_PX = 13


def _saved_theme_name() -> str:
    """Read the theme from QSettings without requiring a QApplication."""
    try:
        from PyQt5.QtCore import QSettings

        name = QSettings("FileForge", "FileForge").value("theme", "Dark")
    except Exception:
        name = "Dark"
    # "Default" was the placeholder name used by older versions → Dark
    return name if name in PALETTES else "Dark"


THEME_NAME = os.environ.get("FILEFORGE_THEME") or _saved_theme_name()
if THEME_NAME not in PALETTES:
    THEME_NAME = "Dark"
_P = PALETTES[THEME_NAME]
IS_DARK = THEME_NAME == "Dark"

# ── Exported tokens (module-level names kept for backwards compatibility) ─
BG_DARKEST = _P["BG_DARKEST"]
BG_DARK = _P["BG_DARK"]
BG_MID = _P["BG_MID"]
BG_PANEL = _P["BG_PANEL"]
BG_CARD = _P["BG_CARD"]
BG_HOVER = _P["BG_HOVER"]
BG_SELECTED = _P["BG_SELECTED"]

ACCENT = _P["ACCENT"]
ACCENT_HOVER = _P["ACCENT_HOVER"]
ACCENT_DARK = _P["ACCENT_DARK"]
ACCENT_DIM = _P["ACCENT_DIM"]
ON_ACCENT = _P["ON_ACCENT"]

TEXT_PRIMARY = _P["TEXT_PRIMARY"]
TEXT_SECONDARY = _P["TEXT_SECONDARY"]
TEXT_MUTED = _P["TEXT_MUTED"]
TEXT_ACCENT = _P["TEXT_ACCENT"]

BORDER = _P["BORDER"]
BORDER_FOCUS = _P["BORDER_FOCUS"]

SUCCESS = _P["SUCCESS"]
WARNING = _P["WARNING"]
ERROR = _P["ERROR"]
INFO = _P["INFO"]
PURPLE = _P["PURPLE"]

HEX_BG = _P["HEX_BG"]
HEX_FG = _P["HEX_FG"]
HEX_OFFSET = _P["HEX_OFFSET"]

FONT_MONO = "'JetBrains Mono', 'Cascadia Mono', 'Consolas', 'SF Mono', 'Menlo', 'DejaVu Sans Mono', 'Courier New', monospace"


def rgba(hex_color: str, alpha: float) -> str:
    """
    '#rrggbb' + alpha (0–1) → 'rgba(r, g, b, a)'.

    Qt reads 8-digit hex as #AARRGGBB, not CSS-style #RRGGBBAA, so appending an
    alpha byte to a colour string silently produces the wrong colour. Use this.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {int(round(alpha * 255))})"


def entropy_color(entropy: float) -> str:
    """Colour for an entropy value in bits/byte (0–8)."""
    if entropy < 3.0:
        return SUCCESS
    if entropy < 6.0:
        return INFO
    if entropy < 7.2:
        return WARNING
    return ERROR


# ── Vector assets for QSS (check marks, arrows) ────────────────────────────
# QSS can only load images from files, so tiny SVGs are written once into the
# temp directory, coloured for the active palette.


def _write_assets() -> dict[str, str]:
    folder = os.path.join(
        tempfile.gettempdir(), f"fileforge-assets-{THEME_NAME.lower()}"
    )
    svgs = {
        "check": f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        f'<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="{ON_ACCENT}" stroke-width="2.2" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "radio": f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        f'<circle cx="8" cy="8" r="3.2" fill="{ON_ACCENT}"/></svg>',
        "down": f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">'
        f'<path d="M2 3.5l3 3 3-3" fill="none" stroke="{TEXT_SECONDARY}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "up": f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">'
        f'<path d="M2 6.5l3-3 3 3" fill="none" stroke="{TEXT_SECONDARY}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "branch_closed": f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">'
        f'<path d="M3.5 2l3 3-3 3" fill="none" stroke="{TEXT_MUTED}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "branch_open": f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">'
        f'<path d="M2 3.5l3 3 3-3" fill="none" stroke="{ACCENT}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
    }
    paths = {}
    try:
        os.makedirs(folder, exist_ok=True)
        for name, content in svgs.items():
            path = os.path.join(folder, f"{name}.svg")
            if (
                not os.path.exists(path)
                or open(path, encoding="utf-8").read() != content
            ):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            paths[name] = path.replace("\\", "/")
    except OSError:
        pass
    return paths


_ASSETS = _write_assets()


def _img(name: str) -> str:
    path = _ASSETS.get(name)
    return f"image: url({path});" if path else ""


# ── Full QSS stylesheet ────────────────────────────────────────────────────
def build_stylesheet(font_px: int = DEFAULT_FONT_PX) -> str:
    small = max(9, font_px - 2)
    tiny = max(9, font_px - 3)
    return f"""
/* ── Global ── */
QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: {FONT_MONO};
    font-size: {font_px}px;
    border: none;
    outline: none;
}}

QMainWindow, QDialog {{
    background-color: {BG_DARK};
}}

/* ── Cards (QFrame#card) ──
   Styled by object name so the rule does NOT cascade into child QLabels
   (QLabel inherits QFrame, so a plain "QFrame {{ border }}" rule boxes every label). */
QFrame#card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#card QLabel, QFrame#card QCheckBox, QFrame#card QRadioButton {{
    background: transparent;
}}
QFrame#heroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {rgba(ACCENT, 0.10)}, stop:0.55 {BG_CARD}, stop:1 {BG_CARD});
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#heroCard QLabel {{ background: transparent; }}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BG_HOVER};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_DIM};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BG_HOVER};
    border-radius: 3px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT_DIM};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollArea {{ background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ── Splitter ── */
QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}
QSplitter::handle:hover {{
    background: {ACCENT_DIM};
}}

/* ── Tab bar ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG_PANEL};
    border-radius: 6px;
    top: -1px;
}}
QTabWidget[documentMode="true"]::pane {{
    border: none;
    border-top: 1px solid {BORDER};
    background: {BG_DARK};
    border-radius: 0;
}}
QTabBar {{
    background: transparent;
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_SECONDARY};
    padding: 9px 16px;
    min-width: 72px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
    font-size: {small + 1}px;
    letter-spacing: 0.5px;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_PRIMARY};
    border-bottom: 2px solid {BORDER};
}}
QTabBar::tab:disabled {{
    color: {TEXT_MUTED};
}}
QTabBar QToolButton {{
    background: {BG_MID};
    border: 1px solid {BORDER};
    border-radius: 3px;
}}

/* ── Tree / List ── */
QTreeWidget, QListWidget, QTreeView, QListView, QTableView, QTableWidget {{
    background: {BG_PANEL};
    alternate-background-color: {BG_CARD if not IS_DARK else BG_MID};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {BG_SELECTED};
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}
QTreeWidget::item, QListWidget::item, QTreeView::item, QListView::item {{
    padding: 4px 6px;
    border-radius: 3px;
}}
QTreeWidget::item:hover, QListWidget::item:hover, QTreeView::item:hover, QListView::item:hover {{
    background: {BG_HOVER};
}}
QTreeWidget::item:selected, QListWidget::item:selected, QTreeView::item:selected, QListView::item:selected {{
    background: {BG_SELECTED};
    color: {ACCENT};
}}
QTreeView::branch {{ background: transparent; }}
QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {{ {_img("branch_closed")} }}
QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings {{ {_img("branch_open")} }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {BG_MID};
    color: {TEXT_SECONDARY};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    font-size: {tiny}px;
    letter-spacing: 1px;
}}
QHeaderView::section:first {{ border-top-left-radius: 6px; }}
QTableCornerButton::section {{ background: {BG_MID}; border: none; }}

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit {{
    background: {BG_DARKEST if IS_DARK else BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 10px;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_PRIMARY};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QDateTimeEdit:hover {{
    border: 1px solid {BG_HOVER if IS_DARK else TEXT_MUTED};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:read-only {{
    background: {BG_MID};
    color: {TEXT_SECONDARY};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled, QDateTimeEdit:disabled, QComboBox:disabled {{
    background: {BG_MID};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
    background: transparent;
    width: 18px;
    border: none;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QDateTimeEdit::up-arrow {{ {_img("up")} width: 10px; height: 10px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QDateTimeEdit::down-arrow {{ {_img("down")} width: 10px; height: 10px; }}
QDateTimeEdit::drop-down {{
    width: 22px;
    border: none;
}}
QCalendarWidget QWidget {{ alternate-background-color: {BG_MID}; }}
QCalendarWidget QToolButton {{
    color: {TEXT_PRIMARY};
    background: transparent;
    padding: 4px 8px;
    border-radius: 4px;
}}
QCalendarWidget QToolButton:hover {{ background: {BG_HOVER}; color: {ACCENT}; }}
QCalendarWidget QAbstractItemView:enabled {{
    background: {BG_PANEL};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}

/* ── ComboBox ── */
QComboBox {{
    background: {BG_DARKEST if IS_DARK else BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 10px;
    min-width: 80px;
}}
QComboBox:hover {{ border: 1px solid {BG_HOVER if IS_DARK else TEXT_MUTED}; }}
QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{
    width: 24px;
    border: none;
    background: transparent;
}}
QComboBox::down-arrow {{ {_img("down")} width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {BG_SELECTED};
    selection-color: {ACCENT};
    padding: 4px;
}}

/* ── Buttons ── */
QPushButton {{
    background: {BG_CARD if IS_DARK else BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 16px;
    font-size: {small + 1}px;
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
QPushButton:focus {{
    border-color: {ACCENT_DIM};
}}
QPushButton#primary {{
    background: {ACCENT};
    color: {ON_ACCENT};
    border: 1px solid {ACCENT};
    font-weight: bold;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
    color: {ON_ACCENT};
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
QPushButton#ghost {{
    background: transparent;
    border: 1px solid transparent;
    color: {TEXT_SECONDARY};
    padding: 5px 10px;
}}
QPushButton#ghost:hover {{
    background: {BG_HOVER};
    color: {ACCENT};
}}
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#danger:disabled {{
    background: {BG_MID};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px;
    color: {TEXT_SECONDARY};
}}
QToolButton:hover {{
    background: {BG_HOVER};
    color: {ACCENT};
}}

/* ── Check / Radio ── */
QCheckBox, QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    background: transparent;
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {TEXT_MUTED}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {TEXT_MUTED if IS_DARK else BORDER};
    border-radius: 4px;
    background: {BG_DARKEST if IS_DARK else BG_PANEL};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    {_img("check")}
}}
QRadioButton::indicator {{ border-radius: 9px; }}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    {_img("radio")}
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {BG_MID};
    border-color: {BORDER};
}}

/* ── Labels ── */
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}
QLabel:disabled {{ color: {TEXT_MUTED}; }}
QLabel#heading {{
    font-size: {font_px + 5}px;
    font-weight: bold;
    color: {ACCENT};
    letter-spacing: 2px;
}}
QLabel#subheading {{
    font-size: {tiny}px;
    color: {TEXT_MUTED};
    letter-spacing: 1px;
}}
QLabel#sectionLabel {{
    font-size: {tiny}px;
    font-weight: bold;
    color: {TEXT_SECONDARY};
    letter-spacing: 1.5px;
}}
QLabel#value {{
    color: {TEXT_PRIMARY};
    font-size: {small + 1}px;
}}
QLabel#muted {{ color: {TEXT_MUTED}; font-size: {small}px; }}
QLabel#success {{ color: {SUCCESS}; }}
QLabel#error   {{ color: {ERROR};   }}
QLabel#warning {{ color: {WARNING}; }}

/* ── Group box ── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 18px;
    padding: 14px 10px 10px 10px;
    color: {TEXT_SECONDARY};
    font-size: {tiny}px;
    letter-spacing: 1px;
    background: {BG_CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {ACCENT};
    background: transparent;
}}
QGroupBox QLabel, QGroupBox QCheckBox {{ background: transparent; }}

/* ── Progress bar ── */
QProgressBar {{
    background: {BG_MID};
    border: 1px solid {BORDER};
    border-radius: 4px;
    min-height: 6px;
    text-align: center;
    color: {TEXT_PRIMARY};
    font-size: {tiny}px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}

/* ── Status bar ── */
QStatusBar {{
    background: {BG_DARKEST};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: {tiny + 1}px;
}}
QStatusBar QLabel {{ color: {TEXT_SECONDARY}; padding: 0 4px; }}
QStatusBar::item {{ border: none; }}

/* ── Menu ── */
QMenuBar {{
    background: {BG_DARKEST};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {BG_HOVER};
    color: {ACCENT};
}}
QMenu {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 28px 6px 14px;
    border-radius: 4px;
    background: transparent;
}}
QMenu::item:selected {{
    background: {BG_SELECTED};
    color: {ACCENT};
}}
QMenu::item:disabled {{ color: {TEXT_MUTED}; }}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 6px;
}}

/* ── Tool tips ── */
QToolTip {{
    background: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {ACCENT_DIM};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: {tiny + 1}px;
}}

/* ── Frames ── */
QFrame[frameShape="4"],   /* HLine */
QFrame[frameShape="5"] {{ /* VLine */
    background: {BORDER};
    max-height: 1px;
}}

/* ── Sidebar ── */
QWidget#sidebar {{ background: {BG_DARKEST}; }}
QWidget#sidebar QTabWidget::pane {{ border: none; background: {BG_DARKEST}; }}
QWidget#sidebar QListWidget, QWidget#sidebar QTreeWidget {{
    background: {BG_DARKEST};
    border: none;
    border-radius: 0;
}}
QFrame#sidebarHeader, QFrame#sidebarFooter, QFrame#sidebarSearch {{
    background: {BG_MID};
}}
QFrame#sidebarHeader {{ border-bottom: 1px solid {BORDER}; }}
QFrame#sidebarSearch {{ border-bottom: 1px solid {BORDER}; }}
QFrame#sidebarFooter {{ border-top: 1px solid {BORDER}; }}
"""


STYLESHEET = build_stylesheet()
