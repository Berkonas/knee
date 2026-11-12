"""Visual identity: cool mineral greys, deep spruce ink, one teal accent; evidence colours carry meaning."""

INK = "#1C2B2A"
MUTED = "#5E6E6B"
BG = "#EEF1F0"
SURFACE = "#FFFFFF"
LINE = "#D5DCDA"
ACCENT = "#1F6F66"
ACCENT_DARK = "#17534C"
SIDEBAR = "#17302D"
WARN = "#B26B0E"
ERROR = "#B3261E"

EVIDENCE_COLORS = {  # background, text
    "measured": ("#DDEFE2", "#1E5B32"),
    "video": ("#DCE8F5", "#1F4E7A"),
    "model": ("#D9EEEB", "#17534C"),
    "scenario": ("#F7E9D2", "#7A4A08"),
    "input": ("#ECECEC", "#3A3A3A"),
    "unavailable": ("#EFEFEF", "#7A7A7A"),
}

QSS = f"""
* {{ font-size: 13px; color: {INK}; }}
QMainWindow, QWidget#page {{ background: {BG}; }}
QWidget#sidebar {{ background: {SIDEBAR}; }}
QLabel#appTitle {{ color: #FFFFFF; font-size: 16px; font-weight: 600; padding: 18px 16px 2px 16px; }}
QLabel#appSubtitle {{ color: #9FB9B4; font-size: 11px; padding: 0 16px 14px 16px; }}
QListWidget#nav {{ background: transparent; border: none; outline: 0; padding: 4px 8px; }}
QListWidget#nav::item {{ color: #C9D8D5; padding: 9px 10px; border-radius: 6px; margin: 1px 0; }}
QListWidget#nav::item:hover {{ background: #21423E; }}
QListWidget#nav::item:selected {{ background: #2B5852; color: #FFFFFF; }}
QLabel#projectBadge {{ color: #9FB9B4; font-size: 11px; padding: 10px 16px 16px 16px; }}
QLabel#pageTitle {{ font-size: 20px; font-weight: 600; padding: 2px 0 0 0; }}
QLabel#pageHint {{ color: {MUTED}; padding-bottom: 6px; }}
QLabel#sectionTitle {{ font-size: 14px; font-weight: 600; padding-top: 4px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#warn {{ color: {WARN}; }}
QLabel#error {{ color: {ERROR}; }}
QFrame#panel {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px; }}
QGroupBox {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px; margin-top: 14px; padding: 10px 8px 8px 8px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {INK}; }}
QPushButton {{ background: {SURFACE}; border: 1px solid #B9C4C1; border-radius: 6px; padding: 6px 12px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: #E3EBE9; }}
QPushButton:disabled {{ color: #9AA6A3; border-color: {LINE}; background: #F5F7F6; }}
QPushButton#primary {{ background: {ACCENT}; color: #FFFFFF; border: 1px solid {ACCENT}; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#primary:disabled {{ background: #9DB9B5; border-color: #9DB9B5; }}
QPushButton:checked {{ background: #D9EEEB; border-color: {ACCENT}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{ background: {SURFACE}; border: 1px solid #C3CDCA; border-radius: 5px; padding: 4px 6px; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QTableView, QTableWidget {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 6px; gridline-color: #E6EBEA; selection-background-color: #D9EEEB; selection-color: {INK}; alternate-background-color: #F7F9F8; }}
QHeaderView::section {{ background: #F2F5F4; border: none; border-bottom: 1px solid {LINE}; padding: 6px; font-weight: 600; color: {MUTED}; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 6px; background: {SURFACE}; top: -1px; }}
QTabBar::tab {{ padding: 7px 14px; color: {MUTED}; border: none; }}
QTabBar::tab:selected {{ color: {INK}; border-bottom: 2px solid {ACCENT}; font-weight: 600; }}
QSlider::groove:horizontal {{ height: 4px; background: #C9D3D1; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; margin: -6px 0; border-radius: 7px; }}
QProgressBar {{ border: 1px solid {LINE}; border-radius: 5px; background: {SURFACE}; text-align: center; height: 16px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {LINE}; color: {MUTED}; }}
QToolTip {{ background: {INK}; color: #FFFFFF; border: none; padding: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QTextBrowser {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 6px; padding: 10px; }}
"""
