#!/usr/bin/env python3
"""Record the README's tutorial (assets/tutorial.gif): the editor app
itself, driven through a short session -- fill in the details, write
notes, render, add an image from the assets explorer -- with a caption
under each step and an outline around the control it's about.

Nothing is faked: it's the real window, on a throwaway project, drawn
without a display (Qt's "offscreen" platform) and grabbed frame by frame.
Run it again whenever the app's look changes:

    app/.venv/bin/python scripts/make_tutorial_gif.py

Needs what the app needs (PySide6; pandoc and TeX for the renders), plus
ffmpeg to assemble the frames.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Chromium's GPU process can't start without a real display.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUTPUT = ROOT / "assets" / "tutorial.gif"
WINDOW_SIZE = (1280, 900)
CAPTION_HEIGHT = 56
GIF_WIDTH = 960
ACCENT = QColor("#c2185b")

NOTES = [
    "# Agenda\n\n",
    "- Review the launch plan\n",
    "- Assign owners\n\n",
    "^1 Who owns the rollout?\n\n",
    "^^1 Launch moves to Friday.\n\n",
]


class Recorder:
    """Collects (frame, seconds on screen) and writes them out as a GIF."""

    def __init__(self, window, folder):
        self.window = window
        self.folder = Path(folder)
        self.frames = []
        self.caption = ""

    def shot(self, seconds, highlight=None):
        """Grab the window as it is now. `highlight` is a widget (or
        several) to outline.
        """
        QTest.qWait(120)
        grabbed = self.window.grab().toImage()
        frame = QImage(grabbed.width(), grabbed.height() + CAPTION_HEIGHT, QImage.Format.Format_RGB32)
        frame.fill(QColor("#1b1f24"))
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawImage(0, 0, grabbed)
        widgets = highlight if isinstance(highlight, (list, tuple)) else [highlight] if highlight else []
        painter.setPen(QPen(ACCENT, 3))
        for widget in widgets:
            box = QRect(widget.mapTo(self.window, QPoint(0, 0)), widget.size()).adjusted(-5, -5, 5, 5)
            painter.drawRoundedRect(QRectF(box), 8, 8)
        font = QFont(painter.font())
        font.setPixelSize(22)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            QRect(0, grabbed.height(), grabbed.width(), CAPTION_HEIGHT), Qt.AlignmentFlag.AlignCenter, self.caption
        )
        painter.end()
        path = self.folder / f"frame-{len(self.frames):03d}.png"
        frame.save(str(path))
        self.frames.append((path, seconds))

    def write(self, output):
        listing = self.folder / "frames.txt"
        lines = []
        for path, seconds in self.frames:
            lines += [f"file '{path}'", f"duration {seconds}"]
        # The concat demuxer needs the last frame named once more to honor its duration.
        lines.append(f"file '{self.frames[-1][0]}'")
        listing.write_text("\n".join(lines) + "\n")
        scale = f"scale={GIF_WIDTH}:-1:flags=lanczos"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                "-vf", f"{scale},split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                "-loop", "0", str(output),
            ],
            check=True,
        )  # fmt: skip


def wait_until(condition, what, timeout=120.0):
    waited = 0.0
    while not condition():
        if waited > timeout:
            raise SystemExit(f"Timed out waiting for {what}.")
        QTest.qWait(50)
        waited += 0.05


def type_in_editor(window, text):
    window.editor.page().runJavaScript(
        "document.querySelector('.cm-content').focus();"
        f"document.execCommand('insertText', false, {json.dumps(text)})"
    )
    expected = window.editor.doc + text
    wait_until(lambda: window.editor.doc == expected, "the editor")


def render(window, rec):
    window.build_ok = None
    window.render_pdf()
    QTest.qWait(150)
    rec.shot(0.9, window.render_button)
    wait_until(lambda: window.build_ok is not None, "the render")
    if not window.build_ok:
        raise SystemExit(f"The render failed:\n{window.build_log}")
    QTest.qWait(2500)  # the preview loading the new PDF


def diagram(path):
    """A small flow diagram to add as the tutorial's image."""
    image = QImage(900, 260, QImage.Format.Format_RGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont(painter.font())
    font.setPixelSize(30)
    painter.setFont(font)
    for i, label in enumerate(("Markdown", "LaTeX", "PDF")):
        box = QRectF(40 + i * 300, 80, 220, 100)
        painter.setPen(QPen(ACCENT, 4))
        painter.setBrush(QColor("#f7e3ec"))
        painter.drawRoundedRect(box, 14, 14)
        painter.setPen(QColor("#1b1f24"))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
        if i < 2:
            painter.setPen(QPen(QColor("#646d79"), 4))
            painter.drawLine(int(box.right()) + 12, 130, int(box.right()) + 68, 130)
            painter.drawLine(int(box.right()) + 52, 116, int(box.right()) + 68, 130)
            painter.drawLine(int(box.right()) + 52, 144, int(box.right()) + 68, 130)
    painter.end()
    image.save(str(path))


def record(window, rec, scratch):
    api, explorer = window.api, window.explorer

    rec.caption = "Markdown Cornell Notes: write on the left, see the PDF on the right"
    rec.shot(2.6)

    rec.caption = "1. Fill in the meeting details — they save as you type"
    window.topic.setFocus()
    for part in ("Weekly ", "Sync"):
        QTest.keyClicks(window.topic, part)
        rec.shot(0.35, window.topic)
    for field, text in ((window.start, "10:00"), (window.end, "10:30")):
        field.setText(text)
        field.editingFinished.emit()
    rec.shot(0.6, [window.start, window.end])
    window.timezone.lineEdit().setText("America/Los_Angeles")
    window.timezone.lineEdit().editingFinished.emit()
    window.location.setFocus()
    QTest.keyClicks(window.location, "Zoom")
    rec.shot(0.6, [window.location, window.timezone])
    window.attendees.setFocus()
    QTest.keyClicks(window.attendees, "Lily, Amber")
    rec.shot(1.4, window.attendees)

    rec.caption = "2. Write your notes in Markdown — ^1 adds a cue, ^^1 a summary"
    for chunk in NOTES:
        type_in_editor(window, chunk)
        rec.shot(0.7, window.editor_frame)
    rec.shot(1.2, window.editor_frame)

    rec.caption = "3. Click Render to build the Cornell-notes PDF"
    render(window, rec)
    rec.shot(3.0, window.pdf_stack)

    rec.caption = "4. Keep images in the assets explorer — drag files in, or use its buttons"
    rec.shot(1.4, explorer)
    api.create_asset_folder("", "diagrams")
    source = Path(scratch) / "pipeline.png"
    diagram(source)
    folder = api.pipeline.assets_dir / "diagrams"
    explorer.add_files([str(source)], str(folder))
    wait_until(lambda: explorer.model.index(str(folder / "pipeline.png")).isValid(), "the explorer")
    QTest.qWait(600)
    explorer.tree.expandAll()
    rec.shot(1.8, explorer)

    rec.caption = "5. Double-click a file to copy its link, then paste it into your notes"
    index = explorer.model.index(str(folder / "pipeline.png"))
    explorer.tree.setCurrentIndex(index)
    explorer.copy_link(str(folder / "pipeline.png"))
    rec.shot(1.8, explorer)
    type_in_editor(window, QApplication.clipboard().text() + "\n")
    rec.shot(1.8, window.editor_frame)

    rec.caption = "6. Render again: the image is in the PDF"
    render(window, rec)
    rec.shot(3.0, window.pdf_stack)

    rec.caption = "The hamburger hides the explorer; folding Details gives the panes more room"
    window.set_explorer_shown(False)
    window.details_card.set_expanded(False)
    QTest.qWait(500)
    rec.shot(2.4, window.explorer_button)

    rec.caption = "View > Appearance switches between light and dark"
    window.set_appearance("dark")
    QTest.qWait(500)
    rec.shot(2.4)

    rec.caption = "File menu: import Markdown, export Markdown or LaTeX, download the PDF"
    rec.shot(3.2)


def main():
    if not shutil.which("ffmpeg"):
        raise SystemExit("Needs ffmpeg to assemble the GIF.")
    QCoreApplication.setOrganizationName("markdown-cornell-notes-tutorial")
    QCoreApplication.setApplicationName("tutorial")
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv[:1])

    import theme
    from api import Api
    from window import MainWindow

    with tempfile.TemporaryDirectory(prefix="mcn-tutorial-") as scratch:
        # Its own settings, so the recording starts from the app's defaults
        # and leaves the user's alone.
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(Path(scratch) / "settings"))

        # A project with one empty note in it, and no example image.
        project = Path(scratch) / "Cornell Notes"
        project.mkdir()
        api = Api(project)
        api.init_project()
        api.create_file("weekly-sync")
        api.delete_file("notes.md")
        api.pipeline.write_markdown_file("weekly-sync.md", "")
        (project / "assets" / "tux.jpg").unlink()

        theme.apply(app, "light")
        window = MainWindow(project)
        window.resize(*WINDOW_SIZE)
        window.show()
        wait_until(lambda: window.editor._ready and window.header is not None, "the app to start")
        QTest.qWait(800)

        frames = Path(scratch) / "frames"
        frames.mkdir()
        rec = Recorder(window, frames)
        record(window, rec, scratch)
        rec.write(OUTPUT)

        window._close_ready = True
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    print(f"{OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB, {len(rec.frames)} frames)")


if __name__ == "__main__":
    main()
