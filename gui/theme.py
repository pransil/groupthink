"""
theme.py — Light/dark theme system.

THEME is a module-level singleton. Widgets that need to re-style on theme
change should connect to THEME.changed signal.

Usage:
    from groupthink.gui.theme import THEME

    THEME.apply(app)               # call once at startup
    THEME.toggle()                 # flip light ↔ dark
    THEME.changed.connect(fn)      # fn() called on every toggle
    c = THEME.c                    # current ThemeColors instance
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QTabWidget


# ── Color tokens ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ThemeColors:
    name:          str
    bg:            str   # main window background
    surface:       str   # card / panel surface
    surface2:      str   # slightly elevated surface
    sidebar:       str   # sidebar background
    border:        str   # dividers, borders
    text:          str   # primary text
    subtext:       str   # secondary / muted text
    accent:        str   # action colour (buttons, links)
    accent_text:   str   # text on accent background
    accent_hover:  str
    button:        str   # neutral button fill
    button_hover:  str
    input_bg:      str   # text input background
    code_bg:       str   # code block background
    tab_bar:       str   # tab bar background
    tab_selected:  str   # selected tab background
    table_header:  str
    table_alt:     str   # alternating row shade


DARK = ThemeColors(
    name         = "dark",
    bg           = "#1c1c1e",
    surface      = "#2c2c2e",
    surface2     = "#3a3a3c",
    sidebar      = "#232325",
    border       = "#48484a",
    text         = "#f5f5f7",
    subtext      = "#aeaeb2",
    accent       = "#0a84ff",
    accent_text  = "#ffffff",
    accent_hover = "#409cff",
    button       = "#3a3a3c",
    button_hover = "#4a4a4c",
    input_bg     = "#2c2c2e",
    code_bg      = "#3a3a3c",
    tab_bar      = "#1c1c1e",
    tab_selected = "#3a3a3c",
    table_header = "#2c2c2e",
    table_alt    = "#242426",
)

LIGHT = ThemeColors(
    name         = "light",
    bg           = "#f2f2f7",
    surface      = "#ffffff",
    surface2     = "#f5f5f5",
    sidebar      = "#e8e8ed",
    border       = "#d1d1d6",
    text         = "#1c1c1e",
    subtext      = "#6c6c70",
    accent       = "#007aff",
    accent_text  = "#ffffff",
    accent_hover = "#0066d6",
    button       = "#e5e5ea",
    button_hover = "#d1d1d6",
    input_bg     = "#ffffff",
    code_bg      = "#f3f3f3",
    tab_bar      = "#e8e8ed",
    tab_selected = "#ffffff",
    table_header = "#f0f0f5",
    table_alt    = "#fafafa",
)


# ── Stylesheet generator ──────────────────────────────────────────────────────

def qt_stylesheet(c: ThemeColors) -> str:
    return f"""
/* ── Base ──────────────────────────────────────────── */
QMainWindow, QDialog {{
    background: {c.bg};
}}
QWidget {{
    color: {c.text};
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

/* ── Labels ─────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {c.text};
}}

/* ── Buttons ─────────────────────────────────────────── */
QPushButton {{
    background-color: {c.button};
    color: {c.text};
    border: 1px solid {c.border};
    border-radius: 7px;
    padding: 5px 16px;
    font-size: 13px;
    font-weight: 500;
    outline: none;
}}
QPushButton:hover   {{ background-color: {c.button_hover}; }}
QPushButton:pressed {{ background-color: {c.border}; }}
QPushButton:disabled {{ color: {c.subtext}; background-color: {c.surface}; border-color: {c.surface2}; }}

QPushButton[accent="true"] {{
    background-color: {c.accent};
    color: {c.accent_text};
    border: none;
    font-weight: 600;
}}
QPushButton[accent="true"]:hover   {{ background-color: {c.accent_hover}; }}
QPushButton[accent="true"]:pressed {{ background-color: {c.accent}; }}
QPushButton[accent="true"]:disabled {{ background-color: {c.surface2}; color: {c.subtext}; }}

/* ── Text inputs ─────────────────────────────────────── */
QPlainTextEdit, QTextEdit, QLineEdit {{
    background: {c.input_bg};
    color: {c.text};
    border: 1px solid {c.border};
    border-radius: 7px;
    padding: 6px 8px;
    selection-background-color: {c.accent};
    selection-color: {c.accent_text};
}}
QPlainTextEdit:focus, QTextEdit:focus, QLineEdit:focus {{
    border-color: {c.accent};
}}

/* ── List widget ─────────────────────────────────────── */
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    padding: 7px 10px 7px 22px;
    border-radius: 6px;
    color: {c.text};
}}
QListWidget::item:selected {{
    background: transparent;
    color: {c.text};
    font-weight: 600;
    padding-left: 6px;
}}
QListWidget::item:hover:!selected {{
    background: {c.surface2};
}}

/* ── Tab widget ──────────────────────────────────────── */
QTabWidget {{
    background: {c.tab_bar};
}}
QTabWidget::pane {{
    border: 1px solid {c.border};
    border-radius: 0 8px 8px 8px;
    background: {c.surface};
    top: -1px;
}}
QTabBar {{
    background: {c.tab_bar};
}}
QTabBar::tab {{
    background: {c.tab_bar};
    color: {c.subtext};
    border: 1px solid {c.border};
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    padding: 6px 18px;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 500;
    min-width: 90px;
}}
QTabBar::tab:selected {{
    background: {c.tab_selected};
    color: {c.text};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: {c.surface2};
    color: {c.text};
}}

/* ── Combo box ───────────────────────────────────────── */
QComboBox {{
    background: {c.button};
    color: {c.text};
    border: 1px solid {c.border};
    border-radius: 7px;
    padding: 4px 10px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
    selection-background-color: {c.accent};
    selection-color: {c.accent_text};
}}

/* ── Progress bar ────────────────────────────────────── */
QProgressBar {{
    background: {c.surface2};
    border: none;
    border-radius: 2px;
    height: 4px;
}}
QProgressBar::chunk {{
    background: {c.accent};
    border-radius: 2px;
}}

/* ── Scroll bars ─────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c.border};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {c.border};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Status bar ──────────────────────────────────────── */
QStatusBar {{
    background: {c.sidebar};
    color: {c.subtext};
    font-size: 11px;
    border-top: 1px solid {c.border};
}}

/* ── Splitter ────────────────────────────────────────── */
QSplitter::handle {{
    background: {c.border};
    width: 1px;
    height: 1px;
}}

/* ── Named regions ───────────────────────────────────── */
QWidget#sidebar {{
    background: {c.sidebar};
    border-right: 1px solid {c.border};
}}
QWidget#header {{
    background: {c.surface};
    border-bottom: 1px solid {c.border};
}}
QLabel#app-title {{
    font-size: 15px;
    font-weight: 700;
    color: {c.text};
    letter-spacing: -0.3px;
}}
QLabel#section-header {{
    font-size: 11px;
    font-weight: 600;
    color: {c.subtext};
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
"""


def markdown_css(c: ThemeColors) -> str:
    """CSS injected into every Markdown HTML document."""
    return f"""
* {{ box-sizing: border-box; }}
body {{
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
    line-height: 1.7;
    color: {c.text};
    background: {c.surface};
    max-width: 900px;
    margin: 0 auto;
    padding: 20px 24px 48px;
}}
h1, h2, h3, h4, h5, h6 {{
    margin-top: 1.4em;
    margin-bottom: 0.5em;
    font-weight: 600;
    line-height: 1.3;
    color: {c.text};
}}
h1 {{ font-size: 1.55em; border-bottom: 1px solid {c.border}; padding-bottom: 8px; }}
h2 {{ font-size: 1.25em; border-bottom: 1px solid {c.border}; padding-bottom: 5px; }}
h3 {{ font-size: 1.1em; }}
h4 {{ font-size: 1.0em; color: {c.subtext}; }}
p  {{ margin: 0.7em 0; }}
ul, ol {{ padding-left: 1.6em; margin: 0.5em 0; }}
li {{ margin: 0.3em 0; }}
strong {{ font-weight: 600; color: {c.text}; }}
em {{ font-style: italic; }}
a {{ color: {c.accent}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
hr {{ border: none; border-top: 1px solid {c.border}; margin: 1.8em 0; }}
blockquote {{
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 3px solid {c.accent};
    color: {c.subtext};
    background: {c.surface2};
    border-radius: 0 6px 6px 0;
}}
code {{
    font-family: "Menlo", "Monaco", "SF Mono", monospace;
    font-size: 0.875em;
    background: {c.code_bg};
    color: {c.text};
    padding: 2px 6px;
    border-radius: 4px;
}}
pre {{
    background: {c.code_bg};
    border: 1px solid {c.border};
    border-radius: 8px;
    padding: 14px 16px;
    overflow-x: auto;
    font-size: 0.875em;
    line-height: 1.55;
}}
pre code {{ background: none; padding: 0; border-radius: 0; }}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 1.2em 0;
    font-size: 0.93em;
}}
th {{
    background: {c.table_header};
    font-weight: 600;
    text-align: left;
    padding: 9px 14px;
    border: 1px solid {c.border};
    color: {c.text};
}}
td {{
    padding: 8px 14px;
    border: 1px solid {c.border};
    vertical-align: top;
    color: {c.text};
}}
tr:nth-child(even) td {{ background: {c.table_alt}; }}
"""


def _get_theme_colors() -> ThemeColors:
    return THEME.c  # resolved at call time, after THEME is instantiated


def style_tab_widget(tab: QTabWidget, c: ThemeColors | None = None) -> None:
    """
    Apply tab-bar background directly via palette — bypasses macOS native painting
    which ignores the global stylesheet for QTabBar backgrounds.
    """
    if c is None:
        c = _get_theme_colors()
    bg = QColor(c.tab_bar)
    palette = tab.palette()
    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.Button, bg)
    tab.setAutoFillBackground(True)
    tab.setPalette(palette)
    bar = tab.tabBar()
    bar.setAutoFillBackground(True)
    bar.setPalette(palette)


# ── ThemeManager ──────────────────────────────────────────────────────────────

class ThemeManager(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._dark = True

    @property
    def is_dark(self) -> bool:
        return self._dark

    @property
    def c(self) -> ThemeColors:
        return DARK if self._dark else LIGHT

    def toggle(self):
        self._dark = not self._dark
        self.apply()
        self.changed.emit()

    def apply(self, app: QApplication = None):
        target = app or QApplication.instance()
        if target:
            target.setStyleSheet(qt_stylesheet(self.c))

    def bg_qcolor(self) -> QColor:
        return QColor(self.c.surface)


THEME = ThemeManager()
