"""The app's look: a light and a dark palette (whichever the desktop is
set to), applied as a Qt style sheet over the Fusion style, plus the
stroke icons its buttons use.
"""
from pathlib import Path

import shiboken6
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

_RESOURCES = Path(__file__).resolve().parent / "build-resources"

LIGHT = {
    "chevron": (_RESOURCES / "chevron-light.svg").as_posix(),
    "bg": "#f3f4f7",
    "surface": "#ffffff",
    "surface2": "#f6f7f9",
    "hover": "#eef0f4",
    "text": "#1b1f24",
    "muted": "#646d79",
    "border": "#dde1e7",
    "border_strong": "#c7cdd6",
    "primary": "#c2185b",
    "primary_hover": "#a8124d",
    "primary_text": "#ffffff",
    "primary_soft": "#f7e3ec",
    "danger": "#cf222e",
    "error_bg": "#ffebe9",
    "error_text": "#82071e",
    "warning_bg": "#fff4d6",
    "warning_text": "#7a5800",
    "success_bg": "#dcf5e4",
    "success_text": "#116329",
}

DARK = {
    "chevron": (_RESOURCES / "chevron-dark.svg").as_posix(),
    "bg": "#0f1115",
    "surface": "#171a21",
    "surface2": "#1d2129",
    "hover": "#242934",
    "text": "#e6e8ee",
    "muted": "#8b93a3",
    "border": "#2a2f3a",
    "border_strong": "#3a4150",
    "primary": "#ff4b8b",
    "primary_hover": "#ff6a9f",
    "primary_text": "#16090f",
    "primary_soft": "#3a1a28",
    "danger": "#f85149",
    "error_bg": "#3c1618",
    "error_text": "#ffa198",
    "warning_bg": "#352a08",
    "warning_text": "#e8c05a",
    "success_bg": "#11291e",
    "success_text": "#7ee2a8",
}

# Stroke icons, as 24x24 SVG path data.
ICONS = {
    "file": "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5",
    "folder": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    "trash": "M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3",
    "pencil": "M4 20h4L19 9l-4-4L4 16zM13 7l4 4",
    "copy": "M9 9h11v11H9zM5 15V4h11",
    "upload": "M12 16V4M7 9l5-5 5 5M5 20h14",
    "download": "M12 4v11M7 10l5 5 5-5M5 20h14",
    "plus": "M12 5v14M5 12h14",
    "move": "M5 12h14M13 6l6 6-6 6",
    "height": "M12 3v18M8 7l4-4 4 4M8 17l4 4 4-4",
    "lines": "M4 6h16M4 12h10M4 18h13",
    "play": "M7 4.5v15l12-7.5z",
    "chevron-right": "M9 6l6 6-6 6",
    "chevron-down": "M6 9l6 6 6-6",
    "close": "M6 6l12 12M18 6L6 18",
    "menu": "M4 6h16M4 12h16M4 18h16",
    "clock": "M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18zM12 7.5V12l3 2",
    "folder-plus": "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM12 11v5M9.5 13.5h5",
    # A Cornell page: header band, cue column, summary band.
    "logo": "M6.5 2.5h11a2.5 2.5 0 0 1 2.5 2.5v14a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 19V5a2.5 2.5 0 0 1 2.5-2.5zM4 7.5h16M14.5 7.5v9M4 16.5h16",
}

_colors = LIGHT
# (widget, icon name, color key, size) for every icon handed out by
# set_icon, so a light/dark switch can redraw them in the new colors.
_bound = []


def colors():
    """The palette in use (LIGHT or DARK)."""
    return _colors


def icon(name, color_key="text", size=16, fill=False):
    """ICONS[name] as a QIcon, stroked in the current palette's `color_key`."""
    color = _colors[color_key]
    paint = f'fill="{color}" stroke="{color}"' if fill else f'fill="none" stroke="{color}"'
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" {paint} stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"><path d="{ICONS[name]}"/></svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    ratio = QGuiApplication.primaryScreen().devicePixelRatio() if QGuiApplication.primaryScreen() else 1.0
    pixmap = QPixmap(QSize(size, size) * ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return QIcon(pixmap)


def set_icon(widget, name, color_key="text", size=16, fill=False):
    """Give `widget` (a button or label) ICONS[name], kept in step with the
    light/dark palette.
    """
    binding = (widget, name, color_key, size, fill)
    _bound[:] = [b for b in _bound if b[0] is not widget and shiboken6.isValid(b[0])]
    _bound.append(binding)
    _draw(binding)


def _draw(binding):
    widget, name, color_key, size, fill = binding
    drawn = icon(name, color_key, size, fill)
    if hasattr(widget, "setIcon"):
        widget.setIcon(drawn)
        widget.setIconSize(QSize(size, size))
    else:
        widget.setPixmap(drawn.pixmap(QSize(size, size)))


def _stylesheet(c):
    return f"""
QWidget {{ color: {c['text']}; font-size: 14px; }}
QMainWindow, #content, #scroll, #scroll > QWidget > QWidget {{ background: {c['bg']}; }}
QToolTip {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border_strong']}; padding: 4px 6px; }}
QMenuBar {{ background: {c['surface']}; border-bottom: 1px solid {c['border']}; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {c['hover']}; }}
QMenu {{ background: {c['surface']}; border: 1px solid {c['border_strong']}; padding: 4px; }}
QMenu::item {{ padding: 5px 22px; border-radius: 4px; }}
QMenu::item:disabled {{ color: {c['muted']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}

#appbar {{ background: {c['surface']}; border-bottom: 1px solid {c['border']}; }}
#brand {{ font-size: 15px; font-weight: 600; }}
#muted, #pane-tag, #summary-hint {{ color: {c['muted']}; }}
#pane-tag {{ font-size: 11px; font-weight: 600; }}
#caption, #card-title {{ font-weight: 600; }}
#field-label {{ color: {c['muted']}; font-size: 12px; font-weight: 600; }}
#mono, QPlainTextEdit {{ font-family: "DejaVu Sans Mono", Menlo, Consolas, monospace; font-size: 13px; }}

#card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; }}
#card-header {{ background: transparent; border: none; padding: 0; }}
#empty {{ background: {c['surface']}; border: 1px dashed {c['border_strong']}; border-radius: 8px; color: {c['muted']}; }}
#empty-title {{ font-size: 18px; font-weight: 600; color: {c['text']}; }}
#pdf-frame {{ border: 1px solid {c['border']}; }}
#editor-frame {{ border: 1px solid #44475a; }}

QLineEdit, QComboBox, QDateEdit, QPlainTextEdit {{
    background: {c['surface']}; border: 1px solid {c['border_strong']}; border-radius: 6px;
    padding: 5px 8px; selection-background-color: {c['primary']}; selection-color: {c['primary_text']};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border-color: {c['primary']}; }}
QLineEdit:read-only {{ background: {c['surface2']}; }}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{ color: {c['muted']}; background: {c['surface2']}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{c['chevron']}"); width: 12px; height: 12px; margin-right: 8px; }}
QComboBox QAbstractItemView, QAbstractItemView {{
    background: {c['surface']}; border: 1px solid {c['border_strong']}; outline: none;
    selection-background-color: {c['hover']}; selection-color: {c['text']};
}}
QCalendarWidget QWidget {{ background: {c['surface']}; alternate-background-color: {c['surface2']}; }}
QCalendarWidget QAbstractItemView {{ selection-background-color: {c['primary']}; selection-color: {c['primary_text']}; border: none; }}
QCalendarWidget QToolButton {{ background: transparent; border: none; padding: 4px 8px; }}
QCalendarWidget QToolButton:hover {{ background: {c['hover']}; }}

QPushButton, QToolButton {{
    background: {c['surface']}; border: 1px solid {c['border_strong']}; border-radius: 6px; padding: 5px 12px;
}}
QPushButton:hover, QToolButton:hover {{ background: {c['hover']}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {c['muted']}; background: {c['surface2']}; border-color: {c['border']}; }}
QPushButton[kind="primary"] {{ background: {c['primary']}; border-color: {c['primary']}; color: {c['primary_text']}; font-weight: 600; }}
QPushButton[kind="primary"]:hover {{ background: {c['primary_hover']}; border-color: {c['primary_hover']}; }}
QPushButton[kind="primary"]:disabled {{ background: {c['surface2']}; border-color: {c['border']}; color: {c['muted']}; }}
QPushButton[kind="danger"] {{ color: {c['danger']}; }}
QPushButton[kind="small"], QPushButton[kind="danger"] {{ padding: 3px 9px; font-size: 13px; }}
QPushButton[kind="link"], QToolButton[kind="link"] {{ background: transparent; border: none; padding: 2px 4px; color: {c['primary']}; }}
QPushButton[kind="link"]:hover, QToolButton[kind="link"]:hover {{ background: {c['hover']}; }}
QPushButton[kind="link"]:disabled {{ color: {c['text']}; background: transparent; }}
QToolButton[kind="icon"] {{ padding: 6px; }}
QToolButton[kind="plain"] {{ background: transparent; border: none; padding: 2px; }}

QLabel[kind="chip"] {{ border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 600; }}
QLabel[tone="ok"] {{ background: {c['success_bg']}; color: {c['success_text']}; }}
QLabel[tone="fail"] {{ background: {c['error_bg']}; color: {c['error_text']}; }}
QLabel[tone="warn"] {{ background: {c['warning_bg']}; color: {c['warning_text']}; }}
QLabel[kind="save-status"] {{ color: {c['muted']}; font-size: 12px; }}
QLabel[tone="failed"] {{ color: {c['danger']}; }}
QFrame[kind="msg"] {{ border-radius: 6px; }}
QFrame[tone="error"] {{ background: {c['error_bg']}; }}
QFrame[tone="error"] QLabel {{ color: {c['error_text']}; }}
QFrame[tone="warning"] {{ background: {c['warning_bg']}; }}
QFrame[tone="warning"] QLabel {{ color: {c['warning_text']}; }}
#error-text {{ color: {c['danger']}; }}

QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {c['border_strong']}; border-radius: 3px; background: {c['surface']}; }}
QCheckBox::indicator:checked {{ background: {c['primary']}; border-color: {c['primary']}; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['border_strong']}; border-radius: 4px; min-height: 28px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {c['border_strong']}; border-radius: 4px; min-width: 28px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}

#time-picker {{ background: {c['surface']}; border: 1px solid {c['border_strong']}; border-radius: 8px; }}
#time-picker QListWidget {{ border: 1px solid {c['border']}; border-radius: 6px; padding: 2px; }}
#time-picker QListWidget::item {{ padding: 4px 8px; border-radius: 4px; }}
#time-picker QListWidget::item:hover {{ background: {c['hover']}; }}
#time-picker QListWidget::item:selected {{ background: {c['primary']}; color: {c['primary_text']}; }}
#explorer {{ background: {c['surface']}; border-right: 1px solid {c['border']}; }}
#explorer-head {{ border-bottom: 1px solid {c['border']}; }}
#explorer-head QToolButton {{ padding: 4px; }}
#explorer-hint {{ color: {c['muted']}; font-size: 12px; padding: 8px 14px; border-top: 1px solid {c['border']}; }}
QTreeView {{ background: {c['surface']}; border: none; outline: none; padding: 4px; }}
QTreeView::item {{ padding: 3px 2px; border-radius: 4px; }}
QTreeView::item:hover {{ background: {c['hover']}; }}
QTreeView::item:selected {{ background: {c['primary_soft']}; color: {c['text']}; }}
QToolButton[kind="icon"]:checked {{ background: {c['primary_soft']}; border-color: {c['primary']}; }}
"""


def _palette(c):
    palette = QPalette()
    roles = QPalette.ColorRole
    for role, key in (
        (roles.Window, "bg"),
        (roles.WindowText, "text"),
        (roles.Base, "surface"),
        (roles.AlternateBase, "surface2"),
        (roles.Text, "text"),
        (roles.Button, "surface"),
        (roles.ButtonText, "text"),
        (roles.ToolTipBase, "surface"),
        (roles.ToolTipText, "text"),
        (roles.PlaceholderText, "muted"),
        (roles.Highlight, "primary"),
        (roles.HighlightedText, "primary_text"),
        (roles.Link, "primary"),
    ):
        palette.setColor(role, QColor(c[key]))
    return palette


MODES = ("system", "light", "dark")
_mode = "system"


def mode():
    """Which appearance is selected: "system", "light", or "dark"."""
    return _mode


def _restyle(*_):
    global _colors
    app = QApplication.instance()
    system_dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    _colors = DARK if _mode == "dark" or (_mode == "system" and system_dark) else LIGHT
    app.setPalette(_palette(_colors))
    app.setStyleSheet(_stylesheet(_colors))
    # Widgets that have been destroyed since (a closed window's) drop out.
    _bound[:] = [binding for binding in _bound if shiboken6.isValid(binding[0])]
    for binding in _bound:
        _draw(binding)


def set_mode(new_mode):
    """Switch to the light or dark palette, or ("system") back to
    following the desktop's setting.
    """
    global _mode
    _mode = new_mode if new_mode in MODES else "system"
    # Qt's own pieces (file dialogs, title bars where it draws them) follow
    # this; "system" hands the choice back to the desktop.
    scheme = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(_mode, Qt.ColorScheme.Unknown)
    QApplication.instance().styleHints().setColorScheme(scheme)
    _restyle()


def apply(app, mode="system"):
    """Style `app` in `mode` (see set_mode), and again whenever the
    desktop's light/dark setting changes.
    """
    QApplication.setStyle("Fusion")
    app.styleHints().colorSchemeChanged.connect(_restyle)
    set_mode(mode)


def repolish(widget):
    """Re-apply the style sheet to `widget` after one of the dynamic
    properties its rules match on (kind, tone) has changed.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)
