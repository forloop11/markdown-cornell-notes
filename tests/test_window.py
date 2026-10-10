"""Tests for the editor window itself (app/window.py), driven headless:
a real MainWindow over an isolated project, with Qt's "offscreen" platform
standing in for a display. Skipped where PySide6 isn't installed (it's only
needed for the app -- see app/requirements.txt).
"""
import json
import os
import shutil
import time

import pytest

pytest.importorskip("PySide6.QtWebEngineWidgets", reason="needs PySide6 (pip install -r app/requirements.txt)")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.environ["QT_QPA_PLATFORM"] == "offscreen":
    # Chromium's GPU process can't start without a real display.
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pipeline import Pipeline  # noqa: E402

HAVE_TEX = bool(shutil.which("pdflatex") and shutil.which("pandoc") and shutil.which("make"))


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    # Keeps the tests' remembered file/pane height out of the user's own settings.
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("settings"))
    )
    QCoreApplication.setOrganizationName("markdown-cornell-notes-tests")
    QCoreApplication.setApplicationName("tests")
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    import theme

    app = QApplication.instance() or QApplication([])
    theme.apply(app)
    yield app
    # Web pages have to be gone before Qt tears down the profile they use.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def wait_until(condition, timeout=10.0, what="condition"):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        QTest.qWait(20)


@pytest.fixture
def scaffolded(tmp_path):
    """A project with the example notes, as `make init` leaves it."""
    root = tmp_path / "notes"
    root.mkdir()
    Pipeline(root).init_project()
    return root


@pytest.fixture
def window(qapp, scaffolded):
    from window import MainWindow

    QSettings().clear()
    win = MainWindow(scaffolded)
    win.resize(1400, 900)
    win.show()
    wait_until(lambda: win.editor._ready and win.header is not None, what="the editor page")
    yield win
    win._close_ready = True
    win.close()
    win.deleteLater()


def type_in_editor(win, text):
    """Insert `text` at the start of the document, as typing would."""
    win.editor.page().runJavaScript(
        "document.querySelector('.cm-content').focus();"
        f"document.execCommand('insertText', false, {json.dumps(text)})"
    )


def test_opens_the_project_on_its_first_file(window, scaffolded):
    assert window.selected == "notes.md"
    assert window.editor.doc == (scaffolded / "md" / "notes.md").read_text(encoding="utf-8")
    assert window.topic.text() == "Example Meeting"
    assert window.date.date().toString("yyyy-MM-dd") == "2026-08-25"
    assert window.start.value() == "10:00"
    assert window.timezone.value() == "America/Detroit"
    assert str(scaffolded) in window.windowTitle()
    assert not window.no_project.isVisible()
    assert window.explorer._title.text() == "ASSETS (1)"
    assert window.editor._assets == ["tux.jpg"]


def test_typing_in_the_editor_is_autosaved(window, scaffolded):
    type_in_editor(window, "TYPED ")
    md = scaffolded / "md" / "notes.md"
    wait_until(lambda: md.read_text(encoding="utf-8").startswith("TYPED "), what="the autosave")
    assert window.editor.doc.startswith("TYPED ")
    assert window.save_status.text() == "Saved"


def test_editing_a_header_field_is_autosaved_into_the_yaml(window, scaffolded):
    window.topic.setFocus()
    window.topic.selectAll()
    QTest.keyClicks(window.topic, "Planning")
    window.start.setText("9:05")
    window.start.editingFinished.emit()
    assert window.start.value() == "09:05"
    yaml = scaffolded / "yaml" / "notes.yaml"
    wait_until(lambda: 'topic: "Planning"' in yaml.read_text(encoding="utf-8"), what="the autosave")
    assert 'time: "09:05--10:30 EDT"' in yaml.read_text(encoding="utf-8")


def test_text_that_isnt_a_time_or_zone_snaps_back(window):
    window.end.setText("later")
    window.end.editingFinished.emit()
    assert window.end.value() == "10:30"
    assert window.end.text() == "10:30"

    window.timezone.lineEdit().setText("Mars/Base")
    window.timezone.lineEdit().editingFinished.emit()
    assert window.timezone.value() == "America/Detroit"

    window.timezone.lineEdit().setText("")
    window.timezone.lineEdit().editingFinished.emit()
    assert window.header["timezone"] == ""


def test_switching_files_right_after_typing_saves_to_the_right_file(window, scaffolded):
    file, files = window.api.create_file("second")
    window._set_files(files)
    original = (scaffolded / "md" / "notes.md").read_text(encoding="utf-8")

    type_in_editor(window, "LAST WORDS ")
    window.select_file(file)  # before the keystroke has been reported
    wait_until(lambda: window.selected == file and window.header is not None, what="the second file")
    wait_until(lambda: window.editor.doc == "# New notes\n", what="the second file's text")

    assert (scaffolded / "md" / "notes.md").read_text(encoding="utf-8") == "LAST WORDS " + original
    QTest.qWait(700)  # past the autosave delay: nothing late may land in the new file
    assert (scaffolded / "md" / "second.md").read_text(encoding="utf-8") == "# New notes\n"
    assert window.file_select.currentText() == file


def test_closing_right_after_typing_saves_first(qapp, scaffolded):
    from window import MainWindow

    win = MainWindow(scaffolded)
    win.show()
    wait_until(lambda: win.editor._ready and win.header is not None, what="the editor page")
    type_in_editor(win, "BYE ")
    win.close()
    wait_until(lambda: not win.isVisible(), what="the window to close")
    assert (scaffolded / "md" / "notes.md").read_text(encoding="utf-8").startswith("BYE ")
    assert not (scaffolded / win.api.build_dir).exists()
    win.deleteLater()


def test_a_folder_that_isnt_a_project_offers_to_set_one_up(qapp, tmp_path):
    from window import MainWindow

    win = MainWindow(tmp_path)
    win.show()
    assert win.no_project.isVisible()
    assert not win.panes.isVisible()
    assert not win.file_controls.isVisible()

    win.init_project()
    wait_until(lambda: win.header is not None, what="the example notes")
    assert not win.no_project.isVisible()
    assert win.panes.isVisible()
    assert win.selected == "notes.md"
    win._close_ready = True
    win.close()
    win.deleteLater()


@pytest.mark.skipif(not HAVE_TEX, reason="needs pdflatex, pandoc, and make")
def test_render_builds_the_pdf_and_shows_it(window, scaffolded):
    window.render_pdf()
    assert not window.render_button.isEnabled()
    wait_until(lambda: window.build_ok is not None, timeout=120, what="the build")
    assert window.build_ok, window.build_log
    assert window.pdf["name"] == "Example-Meeting_2026-08-25_Teams.pdf"
    assert (scaffolded / "pdf" / window.pdf["name"]).is_file()
    assert window.pdf_stack.currentIndex() == 1
    assert window.build_chip.text() == "✓ Build succeeded"
    assert not window.stale_chip.isVisible()
    assert window.render_button.isEnabled()

    type_in_editor(window, "more ")
    wait_until(window.stale_chip.isVisible, what="the out-of-date chip")


def test_render_with_a_blank_topic_fails_with_the_reason_in_the_build_log(window):
    window.topic.setFocus()
    window.topic.selectAll()
    QTest.keyClick(window.topic, Qt.Key.Key_Delete)
    window.render_pdf()
    wait_until(lambda: window.build_ok is not None, what="the render to be refused")
    assert window.build_ok is False
    assert window.build_log_card.isVisible()
    assert "topic field(s) empty" in window.build_log_view.toPlainText()


def test_time_picker_sets_changes_and_clears_a_time(window, scaffolded):
    field = window.end
    field.open_picker()
    picker = field.picker()
    assert picker.isVisible()
    # It opens on the field's time, offering every hour and every five minutes.
    assert (picker.hours.currentRow(), picker.minutes.currentItem().text()) == (10, "30")
    assert picker.hours.count() == 24
    assert [picker.minutes.item(i).text() for i in range(picker.minutes.count())] == [f"{m:02d}" for m in range(0, 60, 5)]

    picker.pick(hour=14)
    assert field.value() == "14:30"
    picker.pick(minute=45)
    assert field.text() == "14:45"
    assert window.header["end"] == "14:45"
    yaml = scaffolded / "yaml" / "notes.yaml"
    wait_until(lambda: "10:00--14:45" in yaml.read_text(encoding="utf-8"), what="the autosave")

    # A typed time between the steps still opens the picker sensibly.
    field.setText("16:22")
    field.editingFinished.emit()
    field.open_picker()
    assert (picker.hours.currentRow(), picker.minutes.currentItem().text()) == (16, "20")

    picker.picked.emit("")  # the Clear button
    assert field.value() == "" and window.header["end"] == ""

    # With no time yet, a minute alone still makes a time.
    field.open_picker()
    picker.pick(minute=30)
    assert field.value() == "09:30"
    picker.close()


def test_view_appearance_switches_between_light_and_dark_and_is_remembered(window):
    import theme

    assert window.appearance_actions["system"].isChecked()
    window.appearance_actions["dark"].trigger()
    assert theme.colors() is theme.DARK
    assert theme.DARK["bg"] in window.styleSheet() + QApplication.instance().styleSheet()
    assert window.appearance_actions["dark"].isChecked()
    assert QSettings().value("appearance") == "dark"

    window.appearance_actions["light"].trigger()
    assert theme.colors() is theme.LIGHT
    assert not window.appearance_actions["dark"].isChecked()
    assert QSettings().value("appearance") == "light"

    window.appearance_actions["system"].trigger()
    assert theme.mode() == "system"


def explorer_names(win, folder=None):
    model = win.explorer.model
    parent = model.index(str(folder or win.api.pipeline.assets_dir))
    return sorted(model.index(row, 0, parent).data() for row in range(model.rowCount(parent)))


def test_hamburger_collapses_and_expands_the_assets_explorer(window):
    assert window.explorer.isVisible()
    assert window.explorer_button.isChecked()
    window.explorer_button.click()
    assert not window.explorer.isVisible()
    assert not window.explorer_action.isChecked()
    assert QSettings().value("showExplorer", type=bool) is False
    window.explorer_action.trigger()
    assert window.explorer.isVisible()
    assert window.explorer_button.isChecked()


def test_assets_explorer_lists_assets_and_follows_changes(window, scaffolded, tmp_path):
    wait_until(lambda: explorer_names(window) == ["tux.jpg"], what="the explorer to list assets/")

    # A change made outside the app shows up in the tree...
    figures = scaffolded / "assets" / "figures"
    figures.mkdir()
    wait_until(lambda: explorer_names(window) == ["figures", "tux.jpg"], what="the new folder")

    # ...and one made in the tree reaches the editor's completions and the count.
    source = tmp_path / "chart.png"
    source.write_bytes(b"png")
    window.explorer.add_files([str(source)], str(figures))
    assert (figures / "chart.png").is_file()
    wait_until(lambda: window.editor._assets == ["figures/chart.png", "tux.jpg"], what="the editor to catch up")
    assert window.explorer._title.text() == "ASSETS (2)"

    window.explorer.add_files([str(source)], str(figures))  # already there: reported, not raised
    assert window.messages.count() == 1


def test_assets_explorer_drops_move_files_inside_assets_and_copy_files_from_outside(window, scaffolded, tmp_path):
    assets = scaffolded / "assets"
    window.api.create_asset_folder("", "pics")
    outside = tmp_path / "photo.jpg"
    outside.write_bytes(b"jpg")

    window.explorer.drop([str(assets / "tux.jpg"), str(outside)], str(assets / "pics"))
    assert sorted(p.name for p in (assets / "pics").iterdir()) == ["photo.jpg", "tux.jpg"]
    assert not (assets / "tux.jpg").exists()
    assert outside.exists()  # copied in, not moved

    window.explorer.drop([str(assets / "pics")], str(assets))  # a folder: refused, with a message
    assert window.messages.count() == 1
    assert (assets / "pics").is_dir()


def test_assets_explorer_copies_the_path_a_note_would_link_to(window, scaffolded):
    assets = scaffolded / "assets"
    window.explorer.copy_path(str(assets / "tux.jpg"))
    assert QApplication.clipboard().text() == "assets/tux.jpg"

    # A link ready to paste into the editor: an embed for an image...
    window.explorer.copy_link(str(assets / "tux.jpg"))
    assert QApplication.clipboard().text() == "![tux](assets/tux.jpg)"
    # ...a plain link for anything else, wherever it is under assets/.
    (assets / "docs").mkdir()
    (assets / "docs" / "handout.pdf").write_bytes(b"pdf")
    assert window.explorer.markdown_link(str(assets / "docs" / "handout.pdf")) == "[handout](assets/docs/handout.pdf)"
    assert window.explorer.markdown_link(str(assets / "docs")) == "[docs](assets/docs)"
    # A name from outside the app that Markdown would otherwise split.
    (assets / "my chart (v2).PNG").write_bytes(b"png")
    assert window.explorer.markdown_link(str(assets / "my chart (v2).PNG")) == "![my chart (v2)](<assets/my chart (v2).PNG>)"
    assert window.explorer.subdir(str(scaffolded / "assets")) == ""
    assert window.explorer.target_dir() == str(scaffolded / "assets")


def test_no_assets_explorer_until_the_project_is_set_up(qapp, tmp_path):
    from window import MainWindow

    win = MainWindow(tmp_path)
    win.show()
    assert not win.explorer.isVisible()
    assert not win.explorer_button.isEnabled()
    win.init_project()
    assert win.explorer.isVisible()
    win._close_ready = True
    win.close()
    win.deleteLater()


def test_file_menu_imports_a_markdown_file_and_exports_the_open_note(window, scaffolded, tmp_path):
    source = tmp_path / "From Elsewhere.md"
    source.write_text("# Imported\n\nbody\n", encoding="utf-8")
    window.import_markdown(str(source))
    wait_until(lambda: window.selected == "From-Elsewhere.md" and window.header is not None, what="the imported note")
    wait_until(lambda: window.editor.doc == "# Imported\n\nbody\n", what="the imported text")
    assert window.file_select.currentText() == "From-Elsewhere.md"
    assert (scaffolded / "yaml" / "From-Elsewhere.yaml").is_file()

    # Export takes what's in the editor, even if it was typed a moment ago.
    type_in_editor(window, "EDITED ")
    out = tmp_path / "out" / "copy.md"
    out.parent.mkdir()
    window.export_markdown(str(out))
    wait_until(out.exists, what="the exported markdown")
    assert out.read_text(encoding="utf-8") == "EDITED # Imported\n\nbody\n"

    window.import_markdown(str(tmp_path / "nope.md"))
    assert window.messages.count() == 1


@pytest.mark.skipif(not shutil.which("pandoc"), reason="needs pandoc")
def test_file_menu_exports_the_open_note_as_latex(window, tmp_path):
    out = tmp_path / "notes.tex"
    window.export_tex(str(out))
    wait_until(out.exists, what="the exported LaTeX")
    tex = out.read_text(encoding="utf-8")
    assert tex.startswith("% notes.md, exported from Markdown Cornell Notes")
    assert "\\documentclass" in tex and "Welcome to the jungle" in tex


def test_editor_and_preview_fill_the_window_and_follow_its_size(window):
    from window import MIN_PANE_HEIGHT

    def settle(width, height):
        window.resize(width, height)
        QTest.qWait(150)
        return window.editor_frame.height()

    tall = settle(1400, 1000)
    short = settle(1400, 760)
    assert tall - short == 240  # every pixel of window height goes to the panes
    assert window.pdf_stack.height() == window.editor_frame.height()

    # Nothing left over under them, and nothing to scroll.
    scroll = window.body.widget(1)
    assert scroll.verticalScrollBar().maximum() == 0
    bottom = window.panes.mapTo(scroll.widget(), window.panes.rect().bottomLeft()).y()
    assert scroll.widget().height() - bottom < 60

    # Folding Details away hands its height to the panes.
    window.details_card.set_expanded(False)
    QTest.qWait(150)
    assert window.editor_frame.height() > short + 80

    # Too short a window: the panes hold their minimum and the page scrolls.
    window.details_card.set_expanded(True)
    assert settle(1400, 600) == MIN_PANE_HEIGHT
    assert scroll.verticalScrollBar().maximum() > 0


def test_file_new_project_sets_one_up_in_the_chosen_folder_and_switches_to_it(window, scaffolded, tmp_path):
    type_in_editor(window, "KEEP ")  # unsaved work in the project being left
    fresh = tmp_path / "Team Notes"
    fresh.mkdir()
    window.new_project(str(fresh))
    wait_until(lambda: window.api.project_root == fresh and window.header is not None, what="the new project")

    for file in ("md/notes.md", "yaml/notes.yaml", "settings/page.yaml", "assets/tux.jpg"):
        assert (fresh / file).is_file(), file
    assert (fresh / "pdf").is_dir()
    assert window.selected == "notes.md"
    assert str(fresh) in window.windowTitle()
    assert window.messages.count() == 0
    wait_until(lambda: explorer_names(window) == ["tux.jpg"], what="the explorer to follow")
    # The project that was open got its last edit before the switch.
    assert (scaffolded / "md" / "notes.md").read_text(encoding="utf-8").startswith("KEEP ")


def test_file_new_project_never_overwrites_what_a_folder_already_holds(window, scaffolded, tmp_path):
    # A folder with something in the way: refused, and the window stays put.
    taken = tmp_path / "taken"
    (taken / "assets").mkdir(parents=True)
    (taken / "assets" / "mine.txt").write_text("precious")
    window.new_project(str(taken))
    QTest.qWait(200)
    assert window.api.project_root == scaffolded
    assert window.messages.count() == 1
    assert not (taken / "md").exists()
    assert (taken / "assets" / "mine.txt").read_text() == "precious"

    # An existing project: opened as it is, with a note saying so.
    other = tmp_path / "other"
    other.mkdir()
    Pipeline(other).init_project()
    (other / "md" / "notes.md").write_text("# Mine\n", encoding="utf-8")
    window.new_project(str(other))
    wait_until(lambda: window.api.project_root == other and window.header is not None, what="the existing project")
    assert window.editor.doc == "# Mine\n"
    assert window.messages.count() == 1


def test_renaming_the_open_note_keeps_whats_in_the_editor(window, scaffolded):
    type_in_editor(window, "FRESH ")  # not saved yet when the rename starts
    window.rename_file("Kickoff Meeting")
    wait_until(lambda: window.selected == "Kickoff-Meeting.md", what="the rename")
    assert window.files == ["Kickoff-Meeting.md"]
    assert window.file_select.currentText() == "Kickoff-Meeting.md"
    assert window.editor_caption.text() == "Kickoff-Meeting.md"
    assert not (scaffolded / "md" / "notes.md").exists()
    assert (scaffolded / "yaml" / "Kickoff-Meeting.yaml").is_file()
    assert (scaffolded / "md" / "Kickoff-Meeting.md").read_text(encoding="utf-8").startswith("FRESH ")
    assert window.editor.doc.startswith("FRESH ") and window.topic.text() == "Example Meeting"

    # Later edits land in the renamed file (typing carries on after "FRESH ").
    type_in_editor(window, "MORE ")
    wait_until(
        lambda: (scaffolded / "md" / "Kickoff-Meeting.md").read_text(encoding="utf-8").startswith("FRESH MORE "),
        what="the autosave",
    )
    assert QSettings().value("selectedFile") == "Kickoff-Meeting.md"

    window.api.create_file("taken")
    window.rename_file("taken")
    wait_until(lambda: window.messages.count() == 1, what="the refusal")
    assert window.selected == "Kickoff-Meeting.md"


def test_assets_explorer_renames_files_as_well_as_folders(window, scaffolded):
    assets = scaffolded / "assets"
    window.explorer.rename(str(assets / "tux.jpg"), "Penguin Photo.jpg")
    assert (assets / "Penguin-Photo.jpg").is_file() and not (assets / "tux.jpg").exists()
    wait_until(lambda: window.editor._assets == ["Penguin-Photo.jpg"], what="the editor's completions")

    window.api.create_asset_folder("", "pics")
    window.explorer.rename(str(assets / "pics"), "album")
    assert (assets / "album").is_dir()

    window.explorer.rename(str(assets / "Penguin-Photo.jpg"), "album")  # taken: reported
    assert window.messages.count() == 1


def test_open_recent_lists_the_other_projects_opened_lately(window, scaffolded, tmp_path):
    def entries():
        window._fill_recent_menu()
        return [a.text() for a in window.recent_menu.actions() if not a.isSeparator()]

    assert entries() == ["No other recent projects", "Clear List"]

    second = tmp_path / "second"
    second.mkdir()
    window.new_project(str(second))
    wait_until(lambda: window.api.project_root == second and window.header is not None, what="the second project")
    assert entries() == [str(scaffolded), "Clear List"]

    # Picking it switches back, and the list reorders around the current one.
    window.recent_menu.actions()[0].trigger()
    wait_until(lambda: window.api.project_root == scaffolded and window.header is not None, what="the switch back")
    assert entries() == [str(second), "Clear List"]
    assert window.recent_projects() == [str(scaffolded), str(second)]

    # A folder that has since gone isn't offered.
    shutil.rmtree(second)
    assert entries() == ["No other recent projects", "Clear List"]


def test_find_and_replace_panel_opens_in_the_editor(window):
    window.editor.open_search()
    found = []
    window.editor.page().runJavaScript(
        "JSON.stringify([!!document.querySelector('.cm-search'), !!document.querySelector('.cm-search [name=replace]')])",
        0,
        found.append,
    )
    wait_until(lambda: found, what="the editor to answer")
    assert found[0] == "[true,true]"
