"""Design system: one set of tokens per appearance (light / dark), one stylesheet generated from them.

Visual language: macOS-like neutral surfaces, 8 px spacing grid, 6-10 px corner radii, system font,
spruce-teal accent shared with the app icon. Evidence colours carry meaning and are kept in both modes.
"""

from __future__ import annotations

TOKENS = {
    "light": {
        "bg": "#F3F5F5", "surface": "#FFFFFF", "surface2": "#F7F9F9", "line": "#DADFDF", "line_strong": "#C2CAC9",
        "ink": "#1C2726", "muted": "#61706D", "faint": "#93A09D", "accent": "#1F6F66", "accent_hover": "#185A53",
        "accent_soft": "#DCEDEA", "sidebar": "#E9EDEC", "sidebar_sel": "#D3E3E0", "warn": "#9A5B0B",
        "error": "#B3261E", "video_bg": "#101716", "selection": "#CFE5E1",
    },
    "dark": {
        "bg": "#1B1F1F", "surface": "#242A29", "surface2": "#2B3231", "line": "#37403E", "line_strong": "#4A5553",
        "ink": "#E6ECEB", "muted": "#9AA8A5", "faint": "#6F7C79", "accent": "#4DB3A6", "accent_hover": "#63C4B7",
        "accent_soft": "#23403C", "sidebar": "#202625", "sidebar_sel": "#2F4542", "warn": "#E2A54A",
        "error": "#F2867E", "video_bg": "#0B0F0F", "selection": "#2F4542",
    },
}

EVIDENCE_COLORS = {  # background, text (readable on both themes)
    "measured": ("#DDEFE2", "#1E5B32"),
    "video": ("#DCE8F5", "#1F4E7A"),
    "model": ("#D9EEEB", "#17534C"),
    "scenario": ("#F7E9D2", "#7A4A08"),
    "input": ("#ECECEC", "#3A3A3A"),
    "unavailable": ("#E9ECEC", "#6B7471"),
}

_current = {"mode": "light"}

# Back-compat names used by some widgets
INK = TOKENS["light"]["ink"]
MUTED = TOKENS["light"]["muted"]
BG = TOKENS["light"]["bg"]
SURFACE = TOKENS["light"]["surface"]
LINE = TOKENS["light"]["line"]
ACCENT = TOKENS["light"]["accent"]
ACCENT_DARK = TOKENS["light"]["accent_hover"]
SIDEBAR = "#17302D"
WARN = TOKENS["light"]["warn"]
ERROR = TOKENS["light"]["error"]


def tok(name: str) -> str:
    return TOKENS[_current["mode"]][name]


def mode() -> str:
    return _current["mode"]


def build_qss(m: str) -> str:
    t = TOKENS[m]
    return f"""
* {{ color: {t['ink']}; }}
QWidget {{ font-size: 13px; }}
QMainWindow, QWidget#page, QWidget#workspace, QWidget#workspaceCenter, QWidget#inspector {{ background: {t['bg']}; }}
QWidget#browserPanel {{ background: {t['sidebar']}; border-right: 1px solid {t['line']}; }}
QStackedWidget {{ background: transparent; }}
QSplitter::handle {{ background: {t['bg']}; }}
QSplitter::handle:hover {{ background: {t['accent_soft']}; }}
QToolBar {{ background: {t['surface']}; border: none; border-bottom: 1px solid {t['line']}; padding: 4px 8px; spacing: 6px; }}
QStatusBar {{ background: {t['surface']}; border-top: 1px solid {t['line']}; color: {t['muted']}; }}
QMenuBar {{ background: {t['surface']}; }}
QMenu {{ background: {t['surface']}; border: 1px solid {t['line']}; padding: 4px; }}
QMenu::item {{ padding: 5px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {t['selection']}; }}
QLabel#pageTitle {{ font-size: 20px; font-weight: 600; }}
QLabel#pageHint, QLabel#muted {{ color: {t['muted']}; }}
QLabel#sectionTitle, QLabel#groupTitle {{ font-size: 13px; font-weight: 600; padding-top: 6px; }}
QLabel#cardTitle {{ font-size: 13px; font-weight: 600; }}
QLabel#warn {{ color: {t['warn']}; }}
QLabel#error {{ color: {t['error']}; }}
QLabel#value {{ font-size: 15px; font-weight: 600; }}
QLabel#bigValue {{ font-size: 22px; font-weight: 600; }}
QLabel#chip {{ background: {t['accent_soft']}; border-radius: 9px; padding: 2px 9px; font-size: 11px; }}
QLabel#chipWarn {{ background: #F7E9D2; color: #7A4A08; border-radius: 9px; padding: 2px 9px; font-size: 11px; }}
QFrame#card, QFrame#panel {{ background: {t['surface']}; border: 1px solid {t['line']}; border-radius: 10px; }}
QFrame#videoCard {{ background: {t['video_bg']}; border: 1px solid {t['line']}; border-radius: 10px; }}
QPushButton {{ background: {t['surface']}; border: 1px solid {t['line_strong']}; border-radius: 6px; padding: 5px 12px; min-height: 18px; }}
QPushButton:hover {{ border-color: {t['accent']}; }}
QPushButton:pressed {{ background: {t['surface2']}; }}
QPushButton:disabled {{ color: {t['faint']}; border-color: {t['line']}; background: {t['surface2']}; }}
QPushButton:checked {{ background: {t['accent_soft']}; border-color: {t['accent']}; }}
QPushButton#primary {{ background: {t['accent']}; color: #FFFFFF; border: 1px solid {t['accent']}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {t['accent_hover']}; }}
QPushButton#primary:disabled {{ background: {t['line_strong']}; border-color: {t['line_strong']}; color: {t['surface']}; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 4px 8px; }}
QToolButton:hover {{ background: {t['surface2']}; border-color: {t['line']}; }}
QToolButton:checked {{ background: {t['accent_soft']}; border-color: {t['accent']}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{ background: {t['surface']}; border: 1px solid {t['line_strong']}; border-radius: 6px; padding: 4px 6px; selection-background-color: {t['selection']}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 1px solid {t['accent']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; border: 1px solid {t['line']}; selection-background-color: {t['selection']}; }}
QCheckBox {{ spacing: 6px; }}
QTreeWidget, QTableView, QTableWidget, QListWidget {{ background: {t['surface']}; border: 1px solid {t['line']}; border-radius: 8px; alternate-background-color: {t['surface2']}; selection-background-color: {t['selection']}; selection-color: {t['ink']}; outline: 0; }}
QTreeWidget#browser {{ background: {t['sidebar']}; border: none; border-radius: 0; }}
QTreeWidget::item {{ padding: 3px 2px; }}
QHeaderView::section {{ background: {t['surface2']}; border: none; border-bottom: 1px solid {t['line']}; padding: 5px; font-weight: 600; color: {t['muted']}; }}
QTabWidget::pane {{ border: 1px solid {t['line']}; border-radius: 8px; background: {t['surface']}; top: -1px; }}
QTabBar::tab {{ padding: 6px 12px; color: {t['muted']}; border: none; background: transparent; }}
QTabBar::tab:selected {{ color: {t['ink']}; border-bottom: 2px solid {t['accent']}; font-weight: 600; }}
QSlider::groove:horizontal {{ height: 4px; background: {t['line_strong']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {t['surface']}; border: 1px solid {t['line_strong']}; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }}
QProgressBar {{ border: 1px solid {t['line']}; border-radius: 5px; background: {t['surface2']}; text-align: center; height: 14px; color: {t['ink']}; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 4px; }}
QToolTip {{ background: {t['ink']}; color: {t['surface']}; border: none; padding: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QTextBrowser {{ background: {t['surface']}; border: 1px solid {t['line']}; border-radius: 8px; padding: 10px; }}
QWidget#segmented {{ background: {t['surface2']}; border: 1px solid {t['line']}; border-radius: 8px; }}
QPushButton#segment {{ background: transparent; border: none; border-radius: 6px; padding: 4px 12px; color: {t['muted']}; }}
QPushButton#segment:checked {{ background: {t['surface']}; color: {t['ink']}; font-weight: 600; border: 1px solid {t['line']}; }}
QFrame#metricCard {{ background: {t['surface']}; border: 1px solid {t['line']}; border-radius: 10px; }}
QLabel#metricLabel {{ color: {t['muted']}; font-size: 12px; }}
QLabel#metricValue {{ font-size: 22px; font-weight: 600; }}
QLabel#metricValueNA {{ font-size: 16px; color: {t['faint']}; }}
QLabel#metricUnit, QLabel#metricRef, QLabel#metricNote {{ color: {t['muted']}; font-size: 11px; }}
QLabel#reportTitle {{ font-size: 17px; font-weight: 600; }}
QFrame#step {{ background: {t['surface']}; border: 1px solid {t['line']}; border-radius: 10px; }}
QPushButton#stepHeader {{ background: transparent; border: none; text-align: left; padding: 0; }}
QLabel#stepBadge {{ background: {t['surface2']}; border-radius: 12px; font-weight: 600; font-size: 12px; }}
QLabel#stepBadge[done="true"] {{ background: {t['accent']}; color: #FFFFFF; }}
QLabel#stepTitle {{ font-weight: 600; }}
QLabel#stepStatus {{ color: {t['muted']}; font-size: 12px; }}
QListWidget#nav {{ background: transparent; border: none; }}
"""


def apply_theme(app, m: str | None = None) -> str:
    """Apply light/dark. m=None follows the operating system setting (Qt 6.5+ colorScheme)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette

    if m is None:
        try:
            m = "dark" if app.styleHints().colorScheme() == Qt.ColorScheme.Dark else "light"
        except AttributeError:
            m = "light"
    _current["mode"] = m
    t = TOKENS[m]
    pal = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "bg"), (QPalette.ColorRole.Base, "surface"),
                      (QPalette.ColorRole.AlternateBase, "surface2"), (QPalette.ColorRole.Text, "ink"),
                      (QPalette.ColorRole.WindowText, "ink"), (QPalette.ColorRole.Button, "surface"),
                      (QPalette.ColorRole.ButtonText, "ink"), (QPalette.ColorRole.Highlight, "accent"),
                      (QPalette.ColorRole.ToolTipBase, "ink"), (QPalette.ColorRole.ToolTipText, "surface"),
                      (QPalette.ColorRole.PlaceholderText, "faint")):
        pal.setColor(role, QColor(t[key]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)
    app.setStyleSheet(build_qss(m))
    try:
        import pyqtgraph as pg
        pg.setConfigOptions(background=t["surface"], foreground=t["muted"], antialias=True)
    except ImportError:
        pass
    return m


QSS = build_qss("light")
