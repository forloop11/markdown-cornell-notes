"""The two panes Chromium (Qt WebEngine) draws: the markdown editor --
CodeMirror, in web/index.html -- and the PDF preview, in Chromium's
built-in PDF viewer. Everything else in the window is Qt widgets.

Both only ever show local files: navigation anywhere else is refused, and
http(s)/mailto links (e.g. clicked inside the PDF preview) open in the
system browser instead.
"""
import json
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMenu

WEB_DIR = Path(__file__).resolve().parent / "web"

EXTERNAL_SCHEMES = {"http", "https", "mailto"}
# What the PDF viewer itself loads besides the PDF: its own extension
# pages and the blobs/data URLs they use.
LOCAL_SCHEMES = {"file", "chrome-extension", "about", "blob", "data", "qrc"}

WebAction = QWebEnginePage.WebAction

# How the PDF preview opens (a PDF "open parameter"): view=Fit shows the
# whole page, view=FitH fits its width, zoom=100 its actual size.
PDF_VIEW = "view=Fit"


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

    @Slot()
    def ready(self):
        self.ready_.emit()

    @Slot(int, str)
    def docChanged(self, generation, doc):  # noqa: N802 (named for the JS side)
        self.changed.emit(generation, doc)

    @Slot()
    def blurred(self):
        self.blurred_.emit()


class EditorView(QWebEngineView):
    """The markdown editor. `doc` mirrors the editor's text: the page
    reports every edit as it happens, and fetch_doc() asks for the text
    outright where it has to be exact (before a save that can't be redone
    -- switching files, rendering, closing).
    """

    edited = Signal()  # the user changed the text
    blurred = Signal()  # the editor lost focus

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


class PdfView(QWebEngineView):
    """The PDF preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPage(LocalPage(self))
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        self._shown = None

    def show_pdf(self, path, version):
        """Show the PDF at `path`; `version` (see Api.pdf_info) changes
        when it has been rebuilt, which reloads it.
        """
        if self._shown == (path, version):
            return
        self._shown = (path, version)
        url = QUrl.fromLocalFile(path)
        # ?v= busts the cache after each re-render. PDF_VIEW fits the whole
        # page in the pane, so a page is seen at a glance however the
        # window is sized (the viewer's toolbar has fit-to-width and zoom
        # buttons for reading the small print). navpanes=0 starts with the page-thumbnail sidebar closed, while
        # keeping the toolbar, whose menu button can still open it.
        url.setQuery(f"v={version}")
        url.setFragment(f"{PDF_VIEW}&navpanes=0")
        self.load(url)

    def clear(self):
        if self._shown is not None:
            self._shown = None
            self.setUrl(QUrl("about:blank"))

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
