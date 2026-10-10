"""The editor's window: an app bar (file picker, status, Render) over a
scrolling page of the Details form, the editor and PDF preview side by
side, with the assets explorer down the left.

Everything persistent lives on disk, written through api.py; this file
only holds the open file's in-progress form state.
"""
import json
import shutil
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QDate, QFile, QSettings, QStandardPaths, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import header_form
import sync
import theme
from api import Api
from assets_explorer import AssetsExplorer
from pipeline import REPO_ROOT, PipelineError, rewrite_links
from webviews import EditorView, PdfView, WebAction
from widgets import (
    Card,
    Chip,
    ChoiceField,
    FindField,
    MessageBar,
    NameDialog,
    TimeField,
    WrapBar,
    button,
    field,
    icon_button,
    label,
    mini_button,
    set_tone,
)

APP_NAME = "Markdown Cornell Notes"
PROJECT_URL = "https://github.com/forloop11/markdown-cornell-notes"
DOCS_URL = f"{PROJECT_URL}#documentation"


def app_version():
    """The app's version, from package.json next to this file ("" if it
    can't be read).
    """
    try:
        return json.loads((REPO_ROOT / "app" / "package.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return ""

AUTOSAVE_MS = 500
# How long a closing window (or one switching projects) waits for the
# editor to report its final text before going ahead anyway, so a hung
# page can't keep the window open.
FLUSH_TIMEOUT_MS = 3000
EDITOR_ZOOM_STEPS = [0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0]
DATE_FORMAT = "yyyy-MM-dd"
MAX_RECENT = 8  # how many project folders File > Open Recent remembers
# How long the cursor rests on a line before the preview scrolls to it, so
# arrowing through the notes doesn't drag the PDF along line by line.
SYNC_MS = 300
# With View > Auto-Render on: how long after the last keystroke the PDF is
# rebuilt. Long enough not to build half-typed words, short enough to feel
# live.
AUTO_RENDER_MS = 1500

SHORTCUTS = [
    ("Notes", [
        ("Ctrl+R", "Render the PDF"),
        ("Ctrl+F", "Find and replace in the editor"),
        ("Ctrl+Z / Ctrl+Shift+Z", "Undo / redo"),
        ("Tab", "Indent by two spaces"),
        ("/ at the start of a word", "Insert formatting: /bold, /table, /cue, /summary, …"),
        ("](", "Suggest files from assets/ for a link or image"),
    ]),
    ("Files and projects", [
        ("Ctrl+Shift+N", "New project"),
        ("Ctrl+O", "Open a project folder"),
        ("Ctrl+I", "Import a Markdown file"),
        ("Ctrl+E / Ctrl+Shift+E", "Export the note as Markdown / LaTeX"),
        ("Ctrl+P", "Open the PDF in the system's viewer (to print)"),
        ("Ctrl+Q", "Quit"),
    ]),
    ("View", [
        ("Ctrl+B", "Show or hide the assets explorer"),
        ("Ctrl++ / Ctrl+- / Ctrl+0", "Editor text larger / smaller / normal"),
        ("F11", "Full screen"),
    ]),
    ("Assets explorer", [
        ("Double-click a file", "Copy a Markdown link to it"),
        ("Ctrl+C", "Copy links to the selected files"),
        ("F2", "Rename the selected file or folder"),
    ]),
    ("PDF preview", [
        ("Double-click text", "Go to that line in the editor"),
        ("Enter / Shift+Enter in its search box", "Next / previous match"),
    ]),
]  # fmt: skip


def move_to_trash(path):
    """Move the file or folder at `path` to the system's trash; whether it went."""
    result = QFile.moveToTrash(path)
    # (PySide hands back the file's new place along with the verdict.)
    return bool(result[0] if isinstance(result, tuple) else result)
# The least height the editor and PDF preview are given; see _build_panes.
MIN_PANE_HEIGHT = 260


def snapshot(header, markdown):
    """A comparable record of a file's content, for "did anything change
    since the last save/render?".
    """
    return tuple(header.get(name) or "" for name in header_form.FORM_FIELDS), markdown


class RenderThread(QThread):
    """Runs one Api.render_file off the GUI thread; `result` holds its
    return value once finished.
    """

    def __init__(self, parent, api, filename, header, markdown):
        super().__init__(parent)
        self.api = api
        self.filename = filename
        self.header = header
        self.markdown = markdown
        self.result = None

    def run(self):
        try:
            self.result = self.api.render_file(self.filename, self.header, self.markdown)
        except PipelineError as err:
            self.result = {"ok": False, "saved": False, "log": str(err), "pdf": None}
        except Exception:  # noqa: BLE001 (shown in the build log rather than lost with the thread)
            self.result = {"ok": False, "saved": False, "log": traceback.format_exc(), "pdf": None}


class MainWindow(QMainWindow):
    # How deletions are made recoverable (None: they're permanent).
    trash = staticmethod(move_to_trash)
    # Whether renaming or moving an asset asks before rewriting the notes'
    # links to it (off: it just does).
    ask_before_updating_links = True

    def __init__(self, project_root, packaged=False, api_options=None, scaffold_if_missing=False):
        super().__init__()
        self.packaged = packaged
        self.api_options = api_options or {}
        self.settings = QSettings()
        self.api = None

        self.files = []
        self.selected = None
        self.header = None  # the selected file's header form values (header_form.FORM_FIELDS)
        self.last_saved = {}  # filename -> snapshot() of its last successful save
        self.rendered = {}  # filename -> snapshot() at its last successful render
        self.pdf = None  # Api.pdf_info of the PDF in the preview pane
        self.build_ok = None
        self.build_log = ""
        self.render_thread = None
        self._filling = False  # header widgets are being filled, not edited
        self._load_token = 0
        self._autosave_warning = None
        self._close_ready = False
        self._render_automatic = False
        self._auto_attempted = None  # the last content auto-render tried to build

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(AUTOSAVE_MS)
        self._save_timer.timeout.connect(self.save_now)

        self.setMinimumSize(900, 600)
        screen = self.screen().availableGeometry()
        self.resize(min(1600, screen.width()), min(1000, screen.height()))

        self.explorer_shown = self.settings.value("showExplorer", True, type=bool)
        # Whether the preview follows the editor's cursor (View menu).
        self.sync_preview = self.settings.value("syncPreview", True, type=bool)
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(SYNC_MS)
        self._sync_timer.timeout.connect(self._sync_preview_to_cursor)
        self._cursor_line = 1
        # Whether the PDF is rebuilt as the notes are typed (View menu).
        self.auto_render = self.settings.value("autoRender", False, type=bool)
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(AUTO_RENDER_MS)
        self._auto_timer.timeout.connect(self._auto_render_now)
        self._build_ui()
        self._build_menu()
        QApplication.instance().styleHints().colorSchemeChanged.connect(lambda *_: self._palette_changed())
        self.open_project(project_root, scaffold_if_missing=scaffold_if_missing)

    # --- Layout ---------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_appbar())

        self.explorer = AssetsExplorer()
        self.explorer.failed.connect(self.show_message)
        # The tree shows changes itself; the editor's path completion
        # needs telling.
        self.explorer.changed.connect(self._assets_changed)
        self.explorer.moved.connect(lambda changes: self.update_asset_links(changes, self.ask_before_updating_links))

        scroll = QScrollArea()
        scroll.setObjectName("scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("content")
        scroll.setWidget(content)

        self.body = QSplitter(Qt.Orientation.Horizontal)
        self.body.setObjectName("body")
        self.body.setHandleWidth(1)
        self.body.setChildrenCollapsible(False)
        self.body.addWidget(self.explorer)
        self.body.addWidget(scroll)
        self.body.setStretchFactor(0, 0)
        self.body.setStretchFactor(1, 1)
        self.body.setSizes([260, 1340])
        outer.addWidget(self.body, 1)

        page = QVBoxLayout(content)
        page.setContentsMargins(24, 16, 24, 32)
        page.setSpacing(14)

        self.messages = QVBoxLayout()
        self.messages.setSpacing(6)
        page.addLayout(self.messages)

        self.build_log_view = QPlainTextEdit()
        self.build_log_view.setReadOnly(True)
        self.build_log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.build_log_view.setFixedHeight(220)
        self.build_log_card = Card("Build log", self.build_log_view)
        page.addWidget(self.build_log_card)

        self.no_project = self._build_no_project()
        page.addWidget(self.no_project)
        self.no_files = self._empty_state(
            "No notes yet", "There are no markdown files in md/. Create one with the + button above."
        )
        page.addWidget(self.no_files)

        self.details_card = Card("Details", self._build_header_form())
        page.addWidget(self.details_card)
        # The panes take whatever height the window has left over...
        page.addWidget(self._build_panes(), 1)

        # ...and when they're hidden (no project, no files), this does.
        page.addStretch(0)

    def _build_appbar(self):
        def group(*widgets):
            box = QWidget()
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            for widget in widgets:
                row.addWidget(widget)
            return box

        # The hamburger: shows and hides the assets explorer down the left.
        self.explorer_button = icon_button("menu", "Show or hide the assets explorer (Ctrl+B)", color="danger")
        self.explorer_button.setCheckable(True)
        self.explorer_button.clicked.connect(lambda on: self.set_explorer_shown(on))

        logo = QLabel()
        theme.set_icon(logo, "logo", "primary", 24)
        brand = label("Cornell Notes", "brand")

        self.file_select = QComboBox()
        self.file_select.setMinimumWidth(200)
        self.file_select.setToolTip("Markdown file")
        self.file_select.setAccessibleName("Markdown file")
        self.file_select.activated.connect(lambda _: self.select_file(self.file_select.currentText()))
        self.new_file_button = icon_button("plus", "New file", self.create_file)
        self.rename_file_button = icon_button("pencil", "Rename file", self.rename_file)
        self.delete_file_button = icon_button("trash", "Delete file", self.delete_file)
        self.file_controls = group(
            self.file_select, self.new_file_button, self.rename_file_button, self.delete_file_button
        )

        self.save_status = QLabel()
        self.save_status.setProperty("kind", "save-status")
        self.stale_chip = Chip("⚠ Preview out of date", "warn", "The header or markdown changed since the last render")
        self.build_chip = Chip()

        self.download_button = button("Download PDF", icon="download", on_click=self.download_pdf)
        self.render_button = button("Render", "primary", icon="play", on_click=self.render_pdf)
        self.render_button.setToolTip("Build the PDF (Ctrl+R)")
        self.actions = group(self.download_button, self.render_button)

        left = group(self.explorer_button, logo, brand, self.file_controls)
        left.layout().setSpacing(10)
        right = group(self.save_status, self.stale_chip, self.build_chip, self.actions)
        right.layout().setSpacing(8)
        bar = WrapBar(left, right)
        bar.setObjectName("appbar")
        return bar

    def _empty_state(self, title, text, *widgets):
        box = QFrame()
        box.setObjectName("empty")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(24, 36, 24, 36)
        layout.setSpacing(10)
        heading = label(title, "empty-title")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        body = label(text, selectable=True)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)
        box.body = body
        for widget in widgets:
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignCenter)
        return box

    def _build_no_project(self):
        buttons = QWidget()
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 6, 0, 0)
        row.addWidget(button("Set up project here", "primary", on_click=self.init_project))
        row.addWidget(button("Open another folder…", on_click=self.choose_project))
        self.init_error = label("", "error-text")
        self.init_error.hide()
        return self._empty_state("No project here", "", buttons, self.init_error)

    def _build_header_form(self):
        form = QWidget()
        grid = QGridLayout(form)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        for column in range(6):
            grid.setColumnStretch(column, 1)

        def line(name, placeholder):
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            edit.textEdited.connect(lambda text: self._header_edited(name, text))
            return edit

        self.topic = line("topic", "What is this about?")
        self.location = line("location", "Room, call, or venue")
        self.attendees = line("attendees", "Comma-separated names")
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat(DATE_FORMAT)
        self.date.dateChanged.connect(lambda d: self._header_edited("date", d.toString(DATE_FORMAT)))
        self.start = TimeField()
        self.start.changed.connect(lambda value: self._header_edited("start", value))
        self.end = TimeField()
        self.end.changed.connect(lambda value: self._header_edited("end", value))
        self.timezone = ChoiceField(header_form.TZ_OPTIONS, "(none)")
        self.timezone.changed.connect(lambda value: self._header_edited("timezone", value))

        grid.addWidget(field("Topic", self.topic), 0, 0, 1, 3)
        grid.addWidget(field("Date", self.date), 0, 3)
        grid.addWidget(field("Start", self.start), 0, 4)
        grid.addWidget(field("End", self.end), 0, 5)
        grid.addWidget(field("Location", self.location), 1, 0, 1, 2)
        grid.addWidget(field("Timezone", self.timezone), 1, 2)
        grid.addWidget(field("Attendees", self.attendees), 1, 3, 1, 3)
        return form

    def _pane(self, icon, tag, body, controls=()):
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        # A fixed height, so the two panes' bodies line up exactly.
        head_row = QWidget()
        head_row.setFixedHeight(28)
        head = QHBoxLayout(head_row)
        head.setContentsMargins(2, 0, 2, 0)
        head.setSpacing(8)
        mark = QLabel()
        theme.set_icon(mark, icon, "muted")
        caption = label("", "caption")
        head.addWidget(mark)
        head.addWidget(caption, 1)
        for control in controls:
            head.addWidget(control)
        head.addWidget(label(tag, "pane-tag"))
        layout.addWidget(head_row)
        layout.addWidget(body, 1)
        return pane, caption

    def _framed(self, widget, name):
        frame = QFrame()
        frame.setObjectName(name)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(widget)
        return frame

    def _build_panes(self):
        self.editor = EditorView()
        self.editor.edited.connect(self._editor_edited)
        self.editor.blurred.connect(self.save_now)
        zoom = self.settings.value("editorZoom", 1.0, type=float)
        self.editor.setZoomFactor(zoom if zoom in EDITOR_ZOOM_STEPS else 1.0)
        self.editor_frame = self._framed(self.editor, "editor-frame")
        editor_pane, self.editor_caption = self._pane("lines", "MARKDOWN", self.editor_frame)

        self.pdf_view = PdfView()
        self.pdf_view.state_changed.connect(self._pdf_state_changed)
        self.pdf_view.text_activated.connect(self._pdf_text_activated)
        self.editor.cursor_moved.connect(self._cursor_moved)
        # The preview's own controls, in its header: which page of how
        # many and the zoom, then zoom out/in and the two fits.
        self.pdf_status = label("", "pdf-status")
        self.pdf_controls = QWidget()
        controls = QHBoxLayout(self.pdf_controls)
        controls.setContentsMargins(0, 0, 6, 0)
        controls.setSpacing(3)
        controls.addWidget(self.pdf_status)
        controls.addSpacing(4)
        controls.addWidget(mini_button("minus", "Zoom out", self.pdf_view.zoom_out))
        controls.addWidget(mini_button("plus", "Zoom in", self.pdf_view.zoom_in))
        controls.addWidget(mini_button("fit-page", "Fit the whole page", self.pdf_view.fit_page))
        controls.addWidget(mini_button("fit-width", "Fit the page's width", self.pdf_view.fit_width))
        self.pdf_find_button = mini_button("search", "Find in the PDF", self._toggle_pdf_find)
        self.pdf_find_button.setCheckable(True)
        controls.addWidget(self.pdf_find_button)
        self.pdf_find = FindField()
        self.pdf_find.setPlaceholderText("Find in PDF")
        self.pdf_find.setAccessibleName("Find in PDF")
        self.pdf_find.setFixedWidth(150)
        self.pdf_find.setClearButtonEnabled(True)
        self.pdf_find.textChanged.connect(lambda text: self.pdf_view.find(text))
        self.pdf_find.step.connect(lambda backwards: self.pdf_view.find(self.pdf_find.text(), backwards))
        self.pdf_find.closed.connect(lambda: self._toggle_pdf_find(False))
        self.pdf_find.hide()
        controls.addWidget(self.pdf_find)
        self.pdf_find_count = label("", "pdf-status")
        self.pdf_find_count.hide()
        controls.addWidget(self.pdf_find_count)
        self.pdf_view.find_changed.connect(self._pdf_find_changed)
        controls.addWidget(
            mini_button("external", "Open in your PDF viewer — to print it, for instance (Ctrl+P)", self.open_pdf_externally)
        )
        self.pdf_controls.hide()
        self.pdf_stack = QStackedWidget()
        placeholder = label("No PDF yet — click Render to build one.", "empty")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pdf_stack.addWidget(placeholder)
        self.pdf_stack.addWidget(self._framed(self.pdf_view, "pdf-frame"))
        pdf_pane, self.pdf_caption = self._pane("file", "PDF PREVIEW", self.pdf_stack, [self.pdf_controls])
        self.pdf_caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.panes = QSplitter(Qt.Orientation.Horizontal)
        self.panes.setChildrenCollapsible(False)
        self.panes.setHandleWidth(14)
        self.panes.addWidget(editor_pane)
        self.panes.addWidget(pdf_pane)
        self.panes.setSizes([1000, 1000])
        # The editor and preview grow and shrink with the window. Below
        # this height they stop shrinking and the page scrolls instead, so
        # a small window (or an open build log) never squeezes them to
        # nothing.
        for pane in (self.editor_frame, self.pdf_stack):
            pane.setMinimumHeight(MIN_PANE_HEIGHT)
            pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return self.panes

    def _build_menu(self):
        bar = self.menuBar()

        def action(menu, text, slot, shortcut=None):
            item = QAction(text, self)
            if shortcut:
                item.setShortcut(QKeySequence(shortcut))
            item.triggered.connect(lambda: slot())
            menu.addAction(item)
            return item

        file_menu = bar.addMenu("&File")
        action(file_menu, "&New Project…", self.new_project, "Ctrl+Shift+N")
        action(file_menu, "&Open Project Folder…", self.choose_project, QKeySequence.StandardKey.Open)
        self.recent_menu = file_menu.addMenu("Open &Recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        action(file_menu, "&Show Project Folder", self.show_project_folder)
        file_menu.addSeparator()
        action(file_menu, "Rena&me Note…", self.rename_file)
        action(file_menu, "&Import Markdown File…", self.import_markdown, "Ctrl+I")
        self.export_actions = [
            action(file_menu, "Export &Markdown…", self.export_markdown, "Ctrl+E"),
            action(file_menu, "Export &LaTeX…", self.export_tex, "Ctrl+Shift+E"),
        ]
        file_menu.addSeparator()
        action(file_menu, "&Render PDF", self.render_pdf, "Ctrl+R")
        action(file_menu, "&Download PDF…", self.download_pdf)
        action(file_menu, "Open PDF in System &Viewer (to Print)", self.open_pdf_externally, QKeySequence.StandardKey.Print)
        file_menu.addSeparator()
        quit_item = action(file_menu, "&Quit", self.close, QKeySequence.StandardKey.Quit)
        quit_item.setMenuRole(QAction.MenuRole.QuitRole)

        edit_menu = bar.addMenu("&Edit")
        for text, name, shortcut in (
            ("&Undo", "undo", QKeySequence.StandardKey.Undo),
            ("&Redo", "redo", QKeySequence.StandardKey.Redo),
            (None, None, None),
            ("Cu&t", "cut", QKeySequence.StandardKey.Cut),
            ("&Copy", "copy", QKeySequence.StandardKey.Copy),
            ("&Paste", "paste", QKeySequence.StandardKey.Paste),
            ("Select &All", "selectAll", QKeySequence.StandardKey.SelectAll),
        ):
            if text is None:
                edit_menu.addSeparator()
                continue
            item = action(edit_menu, text, lambda n=name: self._edit(n), shortcut)
            # The focused widget handles these keys itself; the menu is
            # for the mouse (and for showing what the keys are).
            item.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)

        edit_menu.addSeparator()
        action(edit_menu, "&Find and Replace…", self.editor.open_search, QKeySequence.StandardKey.Find)

        view_menu = bar.addMenu("&View")
        # Light, dark, or whichever the desktop is set to. (The editor pane
        # keeps its own dark theme either way.)
        appearance = view_menu.addMenu("&Appearance")
        group = QActionGroup(self)
        self.appearance_actions = {}
        for text, mode in (("&System", "system"), ("&Light", "light"), ("&Dark", "dark")):
            item = action(appearance, text, lambda m=mode: self.set_appearance(m))
            item.setCheckable(True)
            item.setChecked(mode == theme.mode())
            group.addAction(item)
            self.appearance_actions[mode] = item
        view_menu.addSeparator()
        action(view_menu, "Zoom Editor &In", lambda: self._zoom_editor(1), QKeySequence.StandardKey.ZoomIn)
        action(view_menu, "Zoom Editor &Out", lambda: self._zoom_editor(-1), QKeySequence.StandardKey.ZoomOut)
        action(view_menu, "&Actual Size", lambda: self._zoom_editor(0), "Ctrl+0")
        view_menu.addSeparator()
        self.explorer_action = action(view_menu, "Assets &Explorer", lambda: self.set_explorer_shown(not self.explorer_shown), "Ctrl+B")
        self.explorer_action.setCheckable(True)
        self.auto_render_action = action(view_menu, "Auto-&Render as You Type", self._toggle_auto_render)
        self.auto_render_action.setCheckable(True)
        self.auto_render_action.setChecked(self.auto_render)
        self.sync_action = action(view_menu, "&Sync Preview with Editor", self._toggle_sync)
        self.sync_action.setCheckable(True)
        self.sync_action.setChecked(self.sync_preview)
        action(view_menu, "&Full Screen", self._toggle_full_screen, QKeySequence.StandardKey.FullScreen)

        help_menu = bar.addMenu("&Help")
        action(help_menu, "&Keyboard Shortcuts", self.show_shortcuts, "F1")
        action(help_menu, "&Documentation", lambda: QDesktopServices.openUrl(QUrl(DOCS_URL)))
        help_menu.addSeparator()
        about = action(help_menu, "&About Markdown Cornell Notes", self.show_about)
        about.setMenuRole(QAction.MenuRole.AboutRole)

    # --- Menu actions ---------------------------------------------------------

    def show_shortcuts(self):
        """Help > Keyboard Shortcuts: everything the keyboard (and a
        double-click) does, in one place.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        layout = QVBoxLayout(dialog)
        layout.setSpacing(4)
        mac = sys.platform == "darwin"
        for section, entries in SHORTCUTS:
            heading = label(section, "card-title")
            heading.setContentsMargins(0, 8, 0, 2)
            layout.addWidget(heading)
            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(3)
            grid.setColumnMinimumWidth(0, 260)
            for row, (keys, what) in enumerate(entries):
                grid.addWidget(label(keys.replace("Ctrl", "⌘") if mac else keys, "mono"), row, 0)
                grid.addWidget(label(what), row, 1)
            layout.addLayout(grid)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addSpacing(8)
        layout.addWidget(buttons)
        dialog.exec()

    def show_about(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> {app_version()}<br><br>"
            "Cornell-style meeting notes from Markdown, with a PDF preview.<br><br>"
            f'<a href="{PROJECT_URL}">{PROJECT_URL}</a><br><br>'
            "MIT licensed. Built with Qt (PySide6), CodeMirror, and PDF.js; PDFs are made with pandoc and LaTeX.",
        )

    _WEB_ACTIONS = {
        "undo": WebAction.Undo,
        "redo": WebAction.Redo,
        "cut": WebAction.Cut,
        "copy": WebAction.Copy,
        "paste": WebAction.Paste,
        "selectAll": WebAction.SelectAll,
    }

    def _edit(self, name):
        """Edit menu: apply `name` (undo, copy, ...) to whatever has focus."""
        widget = QApplication.focusWidget()
        for view in (self.editor, self.pdf_view):
            if widget is not None and (widget is view or view.isAncestorOf(widget)):
                view.triggerPageAction(self._WEB_ACTIONS[name])
                return
        if isinstance(widget, QComboBox) and widget.isEditable():
            widget = widget.lineEdit()
        method = getattr(widget, name, None)
        if callable(method):
            method()

    def _zoom_editor(self, direction):
        current = min(EDITOR_ZOOM_STEPS, key=lambda step: abs(step - self.editor.zoomFactor()))
        index = EDITOR_ZOOM_STEPS.index(current) + direction if direction else EDITOR_ZOOM_STEPS.index(1.0)
        zoom = EDITOR_ZOOM_STEPS[max(0, min(index, len(EDITOR_ZOOM_STEPS) - 1))]
        self.editor.setZoomFactor(zoom)
        self.settings.setValue("editorZoom", zoom)

    def set_appearance(self, mode):
        """View > Appearance: switch between light, dark, and the
        desktop's own setting, and remember the choice.
        """
        theme.set_mode(mode)
        self.settings.setValue("appearance", theme.mode())
        self.appearance_actions[theme.mode()].setChecked(True)
        self._palette_changed()

    def _palette_changed(self):
        # Icons drawn once, in the old palette's colors.
        self.explorer.refresh_icons()

    def set_explorer_shown(self, shown):
        """Expand or collapse the assets explorer (the hamburger button,
        View > Assets Explorer), and remember which.
        """
        self.explorer_shown = bool(shown)
        self.settings.setValue("showExplorer", self.explorer_shown)
        self._update_explorer()

    def _update_explorer(self):
        # There's nothing to explore until the project has been set up.
        usable = self.api is not None and self.api.initialized()
        self.explorer.setVisible(usable and self.explorer_shown)
        for control in (self.explorer_button, self.explorer_action):
            control.setChecked(self.explorer_shown)
            control.setEnabled(usable)

    def _toggle_full_screen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def show_project_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.api.project_root)))

    # --- Project --------------------------------------------------------------

    def open_project(self, project_root, scaffold_if_missing=False):
        """Point the window at `project_root`. The standalone builds
        scaffold their default folder on first run, so a fresh install
        opens straight onto the example notes rather than the "no project"
        screen.
        """
        if self.api:
            self.api.cleanup()
        project_root = Path(project_root)
        scaffold = scaffold_if_missing and not project_root.exists()
        if scaffold:
            project_root.mkdir(parents=True)
        self.api = Api(project_root, trash=self.trash, **self.api_options)
        if scaffold:
            self.api.init_project()
        if self.packaged:
            self.settings.setValue("projectRoot", str(self.api.project_root))
        # Most recent first, for File > Open Recent.
        root = str(self.api.project_root)
        self.settings.setValue("recentProjects", [root, *(p for p in self.recent_projects() if p != root)][:MAX_RECENT])
        # Showing the project folder tells two app windows (two projects) apart.
        self.setWindowTitle(f"{APP_NAME} — {self.api.project_root}")
        self._reset()

    def _reset(self):
        """Show the current project from scratch."""
        self._save_timer.stop()
        self.files = []
        self.selected = None
        self.header = None
        self.last_saved = {}
        self.rendered = {}
        self.pdf = None
        self.build_ok = None
        self.build_log = ""
        while self.messages.count():
            self.messages.takeAt(0).widget().dismiss()
        self._autosave_warning = None
        self._set_save_status(None)
        self.init_error.hide()
        self.explorer.set_api(self.api)
        self._update_explorer()

        initialized = self.api.initialized()
        self.no_project.setVisible(not initialized)
        self.no_project.body.setText(
            f"{self.api.project_root} isn't a notes project yet. Set one up here with the "
            "example notes to start from, or open a different folder."
        )
        for widget in (self.file_controls, self.actions):
            widget.setVisible(initialized)
        if not initialized:
            # Nothing else can work without md/ and yaml/ -- show only the
            # "set up a project" screen.
            for widget in (self.no_files, self.details_card, self.panes):
                widget.hide()
            self._update_status()
            return

        self._update_pdf()
        self._assets_changed()
        try:
            self._set_files(self.api.list_files())
        except (PipelineError, OSError) as err:
            self.show_message(str(err))
            return
        remembered = self.settings.value("selectedFile", "")
        if self.files:
            self.select_file(remembered if remembered in self.files else self.files[0])

    def init_project(self):
        """The "no project" screen's "Set up project here" button."""
        try:
            self.api.init_project()
        except (PipelineError, OSError) as err:
            self.init_error.setText(str(err))
            self.init_error.show()
            return
        self._reset()

    def choose_project(self):
        """File > Open Project Folder... (and the "no project" screen's
        button): pick a folder and switch to it.
        """
        folder = QFileDialog.getExistingDirectory(self, "Open Project Folder", str(self.api.project_root))
        if folder:
            self.switch_project(folder)

    def switch_project(self, folder):
        """Leave the current project for the one in `folder`, saving
        anything pending to the current one first.
        """
        self._flush(lambda: (self._wait_for_render(), self.open_project(folder)))

    def recent_projects(self):
        """The project folders opened lately, most recent first."""
        recent = self.settings.value("recentProjects", [])
        # (QSettings hands a one-item list back as a bare string.)
        return [recent] if isinstance(recent, str) else list(recent or [])

    def _fill_recent_menu(self):
        """File > Open Recent: the other projects opened lately that are
        still there.
        """
        self.recent_menu.clear()
        current = str(self.api.project_root)
        others = [p for p in self.recent_projects() if p != current and Path(p).is_dir()]
        for path in others:
            self.recent_menu.addAction(path, lambda p=path: self.switch_project(p))
        if not others:
            self.recent_menu.addAction("No other recent projects").setEnabled(False)
        self.recent_menu.addSeparator()
        clear = self.recent_menu.addAction("Clear List", lambda: self.settings.setValue("recentProjects", [current]))
        clear.setEnabled(bool(others))

    def new_project(self, folder=None):
        """File > New Project...: pick (or make) a folder anywhere, set up
        a notes project in it -- the same files `make init` creates, with
        the example notes to start from -- and switch to it.
        """
        if folder is None:
            folder = QFileDialog.getExistingDirectory(
                self, "New Project: choose or create a folder for it", str(self.api.project_root.parent)
            )
        if not folder:
            return
        # Set the new project up before leaving the current one, so a
        # folder that can't take one leaves everything as it was.
        try:
            candidate = Api(folder, trash=self.trash, **self.api_options)
            already_a_project = candidate.initialized()
            if not already_a_project:
                candidate.init_project()
        except (PipelineError, OSError) as err:
            self.show_message(f"Couldn't create a project in {folder}: {err}")
            return

        def switch():
            self._wait_for_render()
            self.open_project(folder)
            if already_a_project:
                self.show_message(f"{folder} already holds a notes project, so it was opened as it is.", "warning")

        # Save anything pending to the current project first.
        self._flush(switch)

    # --- Messages -------------------------------------------------------------

    def show_message(self, text, tone="error"):
        bar = MessageBar(text, tone)
        self.messages.addWidget(bar)
        return bar

    def _set_autosave_warning(self, text):
        """One persistent autosave warning rather than a new one per failed
        save -- saves retry on every edit, so a lasting failure
        (permissions, disk full) would otherwise stack up a message per
        keystroke.
        """
        if self._autosave_warning is not None:
            try:
                self._autosave_warning.dismiss()
            except RuntimeError:
                pass  # already dismissed by hand
        self._autosave_warning = self.show_message(text, "warning") if text else None

    def _set_save_status(self, kind):
        """The small "Saved" / "Saving…" indicator in the app bar."""
        self.save_status.setVisible(bool(kind))
        self.save_status.setText({"saved": "Saved", "pending": "Saving…", "failed": "Not saved"}.get(kind, ""))
        set_tone(self.save_status, kind)

    # --- Header form + autosave ----------------------------------------------

    def _fill_header(self):
        self._filling = True
        try:
            self.topic.setText(self.header["topic"])
            self.location.setText(self.header["location"])
            self.attendees.setText(self.header["attendees"])
            self.date.setDate(QDate.fromString(self.header["date"], DATE_FORMAT))
            self.start.set_value(self.header["start"])
            self.end.set_value(self.header["end"])
            self.timezone.set_value(self.header["timezone"])
        finally:
            self._filling = False
        self._update_header_summary()

    def _header_edited(self, name, value):
        if self._filling or self.header is None or self.header.get(name) == value:
            return
        self.header[name] = value
        self._update_header_summary()
        self.schedule_save()

    def _update_header_summary(self):
        """The one-line recap shown beside "Details" while that card is folded."""
        header = self.header or {}
        time = "–".join(filter(None, [header.get("start"), header.get("end")]))
        parts = [header.get("topic"), header.get("date"), time, header.get("location")]
        self.details_card.set_hint("  ·  ".join(filter(None, parts)))

    def _current_snapshot(self):
        return snapshot(self.header, self.editor.doc) if self.header is not None else None

    def _editor_edited(self):
        self.schedule_save()
        # Only the notes' text sets an automatic render off, not the
        # Details fields: the PDF is named after those, and rebuilding
        # while one is half-typed would leave a trail of half-named PDFs.
        if self.auto_render:
            self._auto_timer.start()

    # --- Auto-render ------------------------------------------------------------

    def _toggle_auto_render(self):
        self.auto_render = not self.auto_render
        self.settings.setValue("autoRender", self.auto_render)
        self.auto_render_action.setChecked(self.auto_render)
        if self.auto_render:
            self._auto_render_now()
        else:
            self._auto_timer.stop()

    def _auto_render_now(self):
        """Rebuild the PDF if the notes have changed since it was built
        (or since the last attempt, so a note that doesn't build isn't
        retried until it's edited).
        """
        if not self.auto_render or not self.selected or self.header is None:
            return
        if self.render_thread is not None:
            self._auto_timer.start()  # one is running: look again after it
            return
        snap = self._current_snapshot()
        if snap in (self.rendered.get(self.selected), self._auto_attempted):
            return
        self._auto_attempted = snap
        self.render_pdf(automatic=True)

    # --- Editor <-> preview sync ------------------------------------------------

    def _toggle_sync(self):
        self.sync_preview = not self.sync_preview
        self.settings.setValue("syncPreview", self.sync_preview)
        self.sync_action.setChecked(self.sync_preview)

    def _cursor_moved(self, line):
        self._cursor_line = line
        if self.sync_preview and self.pdf:
            self._sync_timer.start()

    def _sync_preview_to_cursor(self):
        """Scroll the preview to where the editor's cursor line is in the
        PDF, if its text can be found there (see sync.py).
        """
        if not (self.sync_preview and self.pdf and self.header is not None):
            return
        snippets, fraction = sync.snippets_for_line(self.editor.doc, self._cursor_line)
        self.pdf_view.reveal(snippets, fraction)

    def _pdf_text_activated(self, text, fraction):
        """Text double-clicked in the preview: put the editor's cursor on
        the line it came from.
        """
        line = sync.line_for_text(self.editor.doc, text, fraction)
        if line is not None:
            # (Not echoed back: the preview is already there.)
            self._cursor_line = line
            self.editor.go_to_line(line)
            self._sync_timer.stop()

    def _toggle_pdf_find(self, shown=None):
        """Show or hide the preview's search box."""
        shown = (not self.pdf_find.isVisible()) if shown is None else bool(shown)
        self.pdf_find_button.setChecked(shown)
        self.pdf_find.setVisible(shown)
        self.pdf_find_count.setVisible(shown)
        if shown:
            self.pdf_find.setFocus()
            self.pdf_find.selectAll()
            self.pdf_view.find(self.pdf_find.text())
        else:
            self.pdf_view.find("")

    def _pdf_find_changed(self, current, total):
        query = self.pdf_find.text()
        self.pdf_find_count.setText(f"{current} of {total}" if total else ("No matches" if query else ""))

    def open_pdf_externally(self):
        """Hand the PDF to the system's own viewer -- which is where
        printing, and anything else this preview doesn't do, is.
        """
        if not self.pdf:
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.pdf["path"])):
            self.show_message(f"Couldn't open {self.pdf['name']} in another program.")

    def update_asset_links(self, changes, ask=True):
        """After assets were renamed or moved (`changes`: [(old, new, is
        a folder)], paths relative to assets/): point the notes' links at
        their new places -- offering first, unless `ask` is off. Returns
        how many links were changed.
        """
        if not self.api.initialized():
            return 0

        def links_in(text):
            return sum(rewrite_links(text, old, new, folder)[1] for old, new, folder in changes)

        try:
            notes = {}
            for name in self.api.list_files():
                # The open note as it is in the editor, saved or not.
                text = self.editor.doc if name == self.selected else self.api.pipeline.read_markdown_file(name)
                if links_in(text):
                    notes[name] = links_in(text)
            total = sum(notes.values())
            if not total:
                return 0
            if ask:
                links = "1 link" if total == 1 else f"{total} links"
                where = "1 note" if len(notes) == 1 else f"{len(notes)} notes"
                box = QMessageBox(
                    QMessageBox.Icon.Question,
                    "Update links",
                    f"{links} in {where} still point at the old name. Update them?",
                    parent=self,
                )
                box.setInformativeText("\n".join(f"{name}: {count}" for name, count in sorted(notes.items())))
                update = box.addButton("Update Links", QMessageBox.ButtonRole.AcceptRole)
                box.addButton("Leave as They Are", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() is not update:
                    return 0
            for old, new, folder in changes:
                self.api.pipeline.rewrite_asset_links(old, new, folder, skip=[self.selected] if self.selected else [])
            if self.selected in notes:
                text = self.editor.doc
                for old, new, folder in changes:
                    text = rewrite_links(text, old, new, folder)[0]
                self.editor.replace_doc(text)  # undoable, and saved like any edit
            return total
        except (PipelineError, OSError) as err:
            self.show_message(str(err))
            return 0

    def _pdf_state_changed(self, pages, page, percent, scale):
        self.pdf_controls.setVisible(pages > 0)
        self.pdf_status.setText(f"{page} / {pages}   {percent}%" if pages else "")

    def schedule_save(self):
        self._save_timer.start()
        self._set_save_status("pending")
        self._update_status()

    def save_now(self):
        """Write the selected file's header + markdown to disk if either
        changed since the last save. Returns whether it's now saved.
        """
        self._save_timer.stop()
        file = self.selected
        if not file or self.header is None:
            return True
        snap = self._current_snapshot()
        if self.last_saved.get(file) == snap:
            self._set_save_status("saved")
            return True
        try:
            self.api.save_file(file, dict(self.header), self.editor.doc)
        except (PipelineError, OSError) as err:
            self._set_autosave_warning(str(err))
            self._set_save_status("failed")
            return False
        self.last_saved[file] = snap
        self._set_autosave_warning(None)
        self._set_save_status("saved")
        return True

    def _flush(self, then):
        """Get the editor's exact text, save, and call `then()` -- or go
        ahead after FLUSH_TIMEOUT_MS if the editor doesn't answer.
        """
        done = False

        def finish():
            nonlocal done
            if done:
                return
            done = True
            self.save_now()
            then()

        self.editor.fetch_doc(finish)
        QTimer.singleShot(FLUSH_TIMEOUT_MS, finish)

    # --- Files ----------------------------------------------------------------

    def select_file(self, name):
        self._load_token += 1
        token = self._load_token

        def load():
            if token != self._load_token:
                return  # superseded by a later selection
            self.selected = name
            self.header = None
            self.settings.setValue("selectedFile", name)
            self._update_file_controls()
            try:
                data = self.api.load_file(name)
            except (PipelineError, OSError) as err:
                self.show_message(str(err))
                return
            self.header = {f: data["header"].get(f) or "" for f in header_form.FORM_FIELDS}
            self._fill_header()
            self.editor.set_doc(data["markdown"])
            self.pdf = data["pdf"]
            self.editor_caption.setText(name)
            self._update_pdf()
            self._update_status()
            # Writes back any defaults filled in on load (e.g. today's date
            # for a new file, or a legacy "time" field migrated to
            # timezone/location).
            self.save_now()

        if self.selected and self.header is not None:
            self._flush(load)
        else:
            load()

    def _set_files(self, files):
        self.files = files
        self.file_select.clear()
        self.file_select.addItems(files)
        none = not files
        self.no_files.setVisible(none)
        self.details_card.setVisible(not none)
        self.panes.setVisible(not none)
        if none:
            self.selected = None
            self.header = None
            self._set_save_status(None)
        self._update_file_controls()

    def _update_file_controls(self):
        busy = self.render_thread is not None
        if self.selected:
            self.file_select.setCurrentText(self.selected)
        self.new_file_button.setEnabled(not busy)
        self.delete_file_button.setEnabled(not busy and bool(self.selected))
        self.rename_file_button.setEnabled(not busy and bool(self.selected))
        self.render_button.setEnabled(not busy and bool(self.selected))
        self.download_button.setEnabled(not busy and bool(self.pdf))
        for item in getattr(self, "export_actions", []):
            item.setEnabled(bool(self.selected))

    def create_file(self):
        dialog = NameDialog(self, "New markdown file", "File name", "Create", self.api.create_file, placeholder="my-notes")
        if not dialog.exec():
            return
        file, files = dialog.result_value
        self._set_files(files)
        self.select_file(file)

    def import_markdown(self, path=None):
        """File > Import Markdown File...: copy a markdown file from
        anywhere on the computer into the project as a new note, and open
        it. The original is left where it is.
        """
        if not self.api.initialized():
            return
        if path is None:
            documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
            path, _ = QFileDialog.getOpenFileName(
                self, "Import Markdown File", documents, "Markdown (*.md *.markdown *.txt);;All files (*)"
            )
        if not path:
            return
        try:
            file, files = self.api.import_markdown(path)
        except (PipelineError, OSError) as err:
            self.show_message(str(err))
            return
        self._set_files(files)
        self.select_file(file)

    def _export_target(self, title, name, file_filter):
        """Ask where to save an export called `name`, starting in Downloads."""
        downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        target, _ = QFileDialog.getSaveFileName(self, title, str(Path(downloads) / name), file_filter)
        return target

    def export_markdown(self, target=None):
        """File > Export Markdown...: save a copy of the open note's
        markdown, as it is in the editor right now, anywhere on the
        computer.
        """
        if not self.selected or self.header is None:
            return

        def export():
            path = target or self._export_target("Export Markdown", self.selected, "Markdown (*.md)")
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(self.editor.doc)
            except OSError as err:
                self.show_message(f"Couldn't export to {path}: {err}")

        self._flush(export)

    def export_tex(self, target=None):
        """File > Export LaTeX...: save the open note as one LaTeX file --
        the template with the note's header, content, cue, and summary
        written into it -- to compile or edit outside the app.
        """
        if not self.selected or self.header is None:
            return

        def export():
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                result = self.api.export_tex(self.selected, dict(self.header), self.editor.doc)
            except (PipelineError, OSError) as err:
                self.show_message(str(err))
                return
            finally:
                QApplication.restoreOverrideCursor()
            if not result["ok"]:
                # Same place a failed Render explains itself.
                self.build_ok = False
                self.build_log = result["log"]
                self._update_status()
                self.show_message("Couldn't generate the LaTeX; see the build log.")
                return
            path = target or self._export_target("Export LaTeX", result["name"], "LaTeX (*.tex)")
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(result["tex"])
            except OSError as err:
                self.show_message(f"Couldn't export to {path}: {err}")

        self._flush(export)

    def rename_file(self, new_name=None):
        """Rename the open note -- its markdown file and header together
        -- asking for the new name unless one is given. What's in the
        editor stays as it is.
        """
        name = self.selected
        if not name or self.header is None or self.render_thread is not None:
            return

        def rename():
            if new_name is None:
                dialog = NameDialog(
                    self, "Rename note", "New name", "Rename", lambda new: self.api.rename_file(name, new), text=Path(name).stem
                )
                if not dialog.exec():
                    return
                file, files = dialog.result_value
            else:
                try:
                    file, files = self.api.rename_file(name, new_name)
                except (PipelineError, OSError) as err:
                    self.show_message(str(err))
                    return
            # What's known about the note goes with it to its new name.
            for record in (self.last_saved, self.rendered):
                if name in record:
                    record[file] = record.pop(name)
            self.selected = file
            self.settings.setValue("selectedFile", file)
            self._set_files(files)
            self.editor_caption.setText(file)

        # Saved under the old name first, so the rename moves current text.
        self._flush(rename)

    def delete_file(self):
        name = self.selected
        if not name:
            return
        box = QMessageBox(QMessageBox.Icon.Warning, "Delete file", f"Move {name} to the trash?", parent=self)
        box.setInformativeText(
            "Its header (yaml) goes with it. PDFs already built from it are kept.\n"
            "Where the system has no trash for this location, it's deleted for good."
        )
        delete = box.addButton("Move to Trash", QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(box.addButton(QMessageBox.StandardButton.Cancel))
        box.exec()
        if box.clickedButton() is not delete:
            return
        # Drop any pending save for this file, so it can't land after the
        # delete and fail with "not found".
        self._save_timer.stop()
        try:
            files = self.api.delete_file(name)
        except (PipelineError, OSError) as err:
            self.show_message(str(err))
            return
        self.last_saved.pop(name, None)
        self.rendered.pop(name, None)
        self.selected = None
        self.header = None
        self._set_files(files)
        if files:
            self.select_file(files[0])

    # --- Render + status ------------------------------------------------------

    def render_pdf(self, automatic=False):
        """Build the open note's PDF. `automatic`: started by auto-render
        rather than the Render button, so a failure is reported quietly.
        """
        if not self.selected or self.header is None or self.render_thread is not None:
            return
        self._render_automatic = automatic
        self._save_timer.stop()
        self.render_button.setText("Rendering…")
        # Claimed before the editor answers, so a second click can't start
        # a second build.
        self.render_thread = False
        self._update_file_controls()

        def start():
            file, header, markdown = self.selected, dict(self.header), self.editor.doc
            self.render_thread = RenderThread(self, self.api, file, header, markdown)
            self.render_thread.finished.connect(self._render_finished)
            self.render_thread.start()

        self.editor.fetch_doc(start)

    def _render_finished(self):
        thread, self.render_thread = self.render_thread, None
        thread.deleteLater()
        self.render_button.setText("Render")
        if thread.api is not self.api:
            # The window moved to another project while this was building.
            self._update_file_controls()
            return
        result, file = thread.result, thread.filename
        snap = snapshot(thread.header, thread.markdown)
        if result["saved"]:
            self.last_saved[file] = snap
        self.build_ok = result["ok"]
        self.build_log = result["log"]
        # A build nobody asked for shouldn't push the notes down the
        # window when it fails mid-sentence: the log is there, folded.
        if not result["ok"]:
            self.build_log_card.set_expanded(not self._render_automatic)
        if result["ok"]:
            self.rendered[file] = snap
        if result["pdf"] and self.selected == file:
            self.pdf = result["pdf"]
        self._update_file_controls()
        self._update_pdf()
        self._update_status()
        if self.auto_render:
            self._auto_timer.start()  # typed on while it built?

    def _wait_for_render(self):
        """Let a build in flight finish (it's using the project's files)."""
        if self.render_thread:
            self.render_thread.wait()

    def _update_status(self):
        self.build_chip.setVisible(self.build_ok is not None)
        self.build_chip.setText("✓ Build succeeded" if self.build_ok else "✕ Build failed")
        set_tone(self.build_chip, "ok" if self.build_ok else "fail")

        self.build_log_card.setVisible(self.build_ok is False and bool(self.build_log))
        if self.build_log_view.toPlainText() != self.build_log:
            self.build_log_view.setPlainText(self.build_log)
            scrollbar = self.build_log_view.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        # The preview is stale whenever the header/markdown have changed
        # since this file's last successful render -- or it was never
        # rendered this session, and the PDF shown is just whatever was
        # already on disk.
        stale = bool(self.pdf and self.selected and self.rendered.get(self.selected) != self._current_snapshot())
        self.stale_chip.setVisible(stale)

    # --- Panes ------------------------------------------------------------------

    def _update_pdf(self):
        if self.pdf:
            self.pdf_caption.setText(self.pdf["name"])
            self.pdf_view.show_pdf(self.pdf["path"], self.pdf["version"])
            self.pdf_stack.setCurrentIndex(1)
        else:
            self.pdf_caption.setText("")
            self.pdf_stack.setCurrentIndex(0)
            self.pdf_view.clear()
        self._update_file_controls()

    def download_pdf(self):
        """A save dialog, then a copy out of pdf/."""
        if not self.pdf:
            return
        try:
            source = self.api.pdf_path(self.pdf["name"])
            downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
            target, _ = QFileDialog.getSaveFileName(
                self, "Download PDF", str(Path(downloads) / self.pdf["name"]), "PDF (*.pdf)"
            )
            if target:
                shutil.copyfile(source, target)
        except (PipelineError, OSError) as err:
            self.show_message(str(err))

    # --- Assets -----------------------------------------------------------------

    def _assets_changed(self):
        """Something under assets/ changed: the editor's link/image path
        completion and the explorer's file count follow.
        """
        if not self.api.initialized():
            return
        try:
            files = self.api.pipeline.list_asset_files()
        except OSError as err:
            self.show_message(str(err))
            return
        self.editor.set_assets(files)
        self.explorer.set_count(len(files))

    # --- Closing ----------------------------------------------------------------

    def closeEvent(self, event):
        # Closing waits for the editor to hand over anything typed since
        # its last report, and saves it.
        if self._close_ready:
            self._wait_for_render()
            self.api.cleanup()
            event.accept()
            return
        event.ignore()

        def close():
            self._close_ready = True
            self.close()

        self._flush(close)
