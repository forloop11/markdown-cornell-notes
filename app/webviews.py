"""The two panes Chromium (Qt WebEngine) draws: the markdown editor --
CodeMirror, in web/index.html -- and the PDF preview -- PDF.js, in
web/pdf.html. Everything else in the window is Qt widgets.

Both only ever show local files: navigation anywhere else is refused, and
http(s)/mailto links (e.g. clicked inside the PDF preview) open in the
system browser instead.
"""
import base64
import json
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMenu

WEB_DIR = Path(__file__).resolve().parent / "web"

EXTERNAL_SCHEMES = {"http", "https", "mailto"}
# What a local page may load in a frame of its own.
LOCAL_SCHEMES = {"file", "about", "blob", "data", "qrc"}

WebAction = QWebEnginePage.WebAction

def open_external(url):
    if url.scheme().lower() in EXTERNAL_SCHEMES:
        QDesktopServices.openUrl(url)


class LocalPage(QWebEnginePage):
    """A page that stays on local files. `home`, if given, is the only URL
    its main frame may show (so a file dropped on the editor can't replace
    it).
    """

    def __init__(self, parent, home=None):
        super().__init__(parent)
        self._home = home
        # target="_blank" links and window.open(): never a new window.
        self.newWindowRequested.connect(lambda request: open_external(request.requestedUrl()))

    def acceptNavigationRequest(self, url, _type, is_main_frame):
        scheme = url.scheme().lower()
        if scheme in EXTERNAL_SCHEMES:
            open_external(url)
            return False
        if is_main_frame and self._home is not None:
            return url.isLocalFile() and url.toLocalFile() == self._home.toLocalFile()
        return scheme in LOCAL_SCHEMES


class EditorBridge(QObject):
    """What web/bridge.js calls into (as `bridge`, over the QWebChannel)."""

    ready_ = Signal()
    changed = Signal(int, str)
    blurred_ = Signal()
    cursor = Signal(int, int)

    @Slot()
    def ready(self):
        self.ready_.emit()

    @Slot(int, str)
    def docChanged(self, generation, doc):  # noqa: N802 (named for the JS side)
        self.changed.emit(generation, doc)

    @Slot()
    def blurred(self):
        self.blurred_.emit()

    @Slot(int, int, int)
    def cursorMoved(self, generation, line, lines):  # noqa: N802 (named for the JS side)
        self.cursor.emit(generation, line)


class EditorView(QWebEngineView):
    """The markdown editor. `doc` mirrors the editor's text: the page
    reports every edit as it happens, and fetch_doc() asks for the text
    outright where it has to be exact (before a save that can't be redone
    -- switching files, rendering, closing).
    """

    edited = Signal()  # the user changed the text
    blurred = Signal()  # the editor lost focus
    cursor_moved = Signal(int)  # the cursor is on another line (1-based)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = ""
        # Counts set_doc() calls; see bridge.js for why edits carry it.
        self._generation = 0
        self._ready = False
        self._assets = []

        home = QUrl.fromLocalFile(str(WEB_DIR / "index.html"))
        page = LocalPage(self, home=home)
        page.setBackgroundColor(QColor("#282a36"))
        self.setPage(page)

        self._bridge = EditorBridge(self)
        self._bridge.ready_.connect(self._on_ready)
        self._bridge.changed.connect(self._on_changed)
        self._bridge.blurred_.connect(self.blurred)
        self._bridge.cursor.connect(lambda generation, line: generation == self._generation and self.cursor_moved.emit(line))
        channel = QWebChannel(self)
        channel.registerObject("bridge", self._bridge)
        page.setWebChannel(channel)
        page.load(home)

    def _run(self, call, *args, callback=None):
        script = f"{call}({', '.join(json.dumps(arg) for arg in args)})"
        if callback:
            self.page().runJavaScript(script, 0, callback)
        else:
            self.page().runJavaScript(script)

    def _on_ready(self):
        self._ready = True
        self._run("MCN.setDoc", self._generation, self.doc)
        self._run("CodeEditor.setAssets", self._assets)

    def _on_changed(self, generation, doc):
        if generation != self._generation or doc == self.doc:
            return
        self.doc = doc
        self.edited.emit()

    def set_doc(self, doc):
        """Replace the whole document (e.g. after switching files),
        resetting undo history. Not an edit: `edited` isn't emitted.
        """
        self._generation += 1
        self.doc = doc
        if self._ready:
            self._run("MCN.setDoc", self._generation, doc)

    def set_assets(self, files):
        """The files under assets/, for link/image path completion."""
        self._assets = list(files)
        if self._ready:
            self._run("CodeEditor.setAssets", self._assets)

    def replace_doc(self, doc):
        """Change the whole text as an edit of the user's would: undoable,
        and followed by `edited`.
        """
        if doc == self.doc:
            return
        self.doc = doc
        if self._ready:
            self._run("CodeEditor.replaceDoc", doc)
        self.edited.emit()

    def go_to_line(self, line):
        """Put the cursor on `line` (1-based), scrolled into the middle."""
        if self._ready:
            self.setFocus()
            self._run("CodeEditor.goToLine", line)

    def open_search(self):
        """Open the editor's find/replace panel, and put the keyboard in it."""
        self.setFocus()
        if self._ready:
            self._run("CodeEditor.openSearch")

    def fetch_doc(self, callback):
        """Call `callback()` once `doc` is certain to match the editor --
        including any keystroke whose report is still on its way.
        """
        if not self._ready:
            callback()
            return
        generation = self._generation

        def received(result):
            if isinstance(result, list) and len(result) == 2 and result[0] == generation == self._generation:
                if result[1] != self.doc:
                    self.doc = result[1]
                    self.edited.emit()
            callback()

        self._run("MCN.getDoc", callback=received)

    def contextMenuEvent(self, event):
        # Spelling suggestions for a misspelled word, then the usual
        # editing actions.
        request = self.lastContextMenuRequest()
        menu = QMenu(self)
        if request and request.misspelledWord():
            suggestions = request.spellCheckerSuggestions()
            for suggestion in suggestions:
                menu.addAction(suggestion, lambda s=suggestion: self.page().replaceMisspelledWord(s))
            if not suggestions:
                menu.addAction("No suggestions").setEnabled(False)
            menu.addSeparator()
        for action in (WebAction.Undo, WebAction.Redo, None, WebAction.Cut, WebAction.Copy, WebAction.Paste, WebAction.SelectAll):
            if action is None:
                menu.addSeparator()
            else:
                menu.addAction(self.pageAction(action))
        menu.popup(event.globalPos())


class PdfBridge(QObject):
    """What web/pdf_bridge.js calls into (as `bridge`, over the QWebChannel)."""

    ready_ = Signal()
    state = Signal(int, int, int, str)
    text = Signal(str, float)
    find = Signal(int, int)

    @Slot()
    def ready(self):
        self.ready_.emit()

    @Slot(int, int, int, str)
    def stateChanged(self, pages, page, percent, scale):  # noqa: N802 (named for the JS side)
        self.state.emit(pages, page, percent, scale)

    @Slot(str, float)
    def textActivated(self, text, fraction):  # noqa: N802
        self.text.emit(text, fraction)

    @Slot(int, int)
    def findChanged(self, current, total):  # noqa: N802
        self.find.emit(current, total)


class PdfView(QWebEngineView):
    """The PDF preview: PDF.js (web/pdf.html), which -- unlike a browser's
    built-in PDF viewer -- the app can drive. It keeps its zoom and place
    when the PDF it's showing is rebuilt, and can be scrolled to a piece
    of text.
    """

    # (pages, current page, zoom in percent, scale mode: "page-fit",
    # "page-width", or the zoom as a number) -- all 0/"" with nothing shown.
    state_changed = Signal(int, int, int, str)
    # Text in the PDF was double-clicked: (the text, normalized; how far
    # through the document it is, 0-1).
    text_activated = Signal(str, float)
    # A search (see find) is on match `current` of `total` (0, 0: none).
    find_changed = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pages = 0
        self.current_page = 0  # (not "page": that's the web page, page())
        self.percent = 0
        self.scale = ""
        self._ready = False
        self._shown = None  # (path, version) of the PDF on show
        self._pending = None  # the same, waiting for the page to be ready

        home = QUrl.fromLocalFile(str(WEB_DIR / "pdf.html"))
        page = LocalPage(self, home=home)
        page.setBackgroundColor(QColor("#2b2d31"))
        self.setPage(page)

        self._bridge = PdfBridge(self)
        self._bridge.ready_.connect(self._on_ready)
        self._bridge.state.connect(self._on_state)
        self._bridge.text.connect(self.text_activated)
        self._bridge.find.connect(self.find_changed)
        channel = QWebChannel(self)
        channel.registerObject("bridge", self._bridge)
        page.setWebChannel(channel)
        page.load(home)

    def _run(self, call, *args):
        self.page().runJavaScript(f"{call}({', '.join(json.dumps(arg) for arg in args)})")

    def _on_ready(self):
        self._ready = True
        if self._pending:
            self._load(*self._pending)

    def _on_state(self, pages, page, percent, scale):
        self.pages, self.current_page, self.percent, self.scale = pages, page, percent, scale
        self.state_changed.emit(pages, page, percent, scale)

    def _load(self, path, version):
        self._pending = None
        try:
            data = Path(path).read_bytes()
        except OSError:
            return  # gone since it was listed; the next render brings it back
        # Handed over as data rather than a URL: the page then needs no
        # access to files of its own. The file's name keys the view kept
        # across reloads (see PdfViewer.load in frontend_src/pdfviewer.js).
        self._run("PdfViewer.load", base64.b64encode(data).decode("ascii"), Path(path).name)

    def show_pdf(self, path, version):
        """Show the PDF at `path`; `version` (see Api.pdf_info) changes
        when it has been rebuilt, which reloads it -- keeping the zoom and
        scroll position if it's the same file as before.
        """
        if self._shown == (path, version):
            return
        self._shown = (path, version)
        if self._ready:
            self._load(path, version)
        else:
            self._pending = (path, version)

    def clear(self):
        self._pending = None
        if self._shown is not None:
            self._shown = None
            if self._ready:
                self._run("PdfViewer.clear")

    def zoom_in(self):
        self._run("PdfViewer.zoomIn")

    def zoom_out(self):
        self._run("PdfViewer.zoomOut")

    def fit_page(self):
        self._run("PdfViewer.setScale", "page-fit")

    def fit_width(self):
        self._run("PdfViewer.setScale", "page-width")

    def go_to_page(self, number):
        self._run("PdfViewer.goToPage", number)

    def find(self, query, backwards=False):
        """Search the PDF for `query`, highlighting its matches and
        scrolling to the first -- or, asked again, the next (`backwards`:
        the previous). "" clears the search.
        """
        if self._ready and self._shown:
            self._run("PdfViewer.find", query, backwards)

    def reveal(self, snippets, fraction):
        """Scroll to the first of `snippets` found in the PDF (see
        sync.snippets_for_line), marking its line.
        """
        if self._ready and self._shown and snippets:
            self._run("PdfViewer.reveal", snippets, fraction)

    def contextMenuEvent(self, event):
        request = self.lastContextMenuRequest()
        menu = QMenu(self)
        if request and request.selectedText():
            menu.addAction(self.pageAction(WebAction.Copy))
        if request and request.linkUrl().scheme().lower() in EXTERNAL_SCHEMES:
            link = request.linkUrl()
            menu.addAction("Open link in browser", lambda: open_external(link))
        if not menu.isEmpty():
            menu.popup(event.globalPos())
