"""Tests for app/api.py -- the operations the editor window runs -- against
an isolated project (see conftest.py). Rendering itself needs the full
pandoc/TeX Live toolchain, so it's only covered up to the point where it
would start the build.
"""
import re
import shutil

import pytest

from api import Api
from pipeline import PipelineError

HEADER = {
    "topic": "Weekly Sync",
    "location": "Zoom",
    "date": "2026-08-23",
    "start": "10:00",
    "end": "10:30",
    "timezone": "America/Detroit",
    "tz_hint": "",
    "attendees": "Lily",
}


@pytest.fixture
def api(project):
    api = Api(project)
    api.pipeline.create_markdown_file("notes")
    return api


def test_an_uninitialized_directory_reports_not_initialized(project):
    (project / "md").rmdir()
    api = Api(project)
    assert not api.initialized()
    assert api.project_root == project


def test_save_file_writes_the_composed_header_and_markdown_and_load_file_reads_them_back(api, project):
    api.save_file("notes.md", HEADER, "# Hi\n")
    assert api.pipeline.read_header("notes.md")["time"] == "10:00--10:30 EDT"
    assert (project / "md" / "notes.md").read_text(encoding="utf-8") == "# Hi\n"

    data = api.load_file("notes.md")
    assert data["markdown"] == "# Hi\n"
    # tz_hint is re-parsed from "time" on load; it's only ever used when no
    # real timezone is picked, so it doesn't change what gets saved.
    assert data["header"] == {**HEADER, "tz_hint": "EDT"}
    assert data["pdf"] is None


def test_markdown_line_endings_survive_a_save_and_load(api):
    api.save_file("notes.md", HEADER, "one\r\ntwo\n")
    assert api.load_file("notes.md")["markdown"] == "one\r\ntwo\n"


def test_create_file_sanitizes_and_delete_file_removes(api):
    assert api.create_file("Team Sync!") == ("Team-Sync.md", ["Team-Sync.md", "notes.md"])
    assert api.delete_file("Team-Sync.md") == ["notes.md"]


def test_deleting_the_last_file_is_refused(api):
    with pytest.raises(PipelineError, match="last remaining"):
        api.delete_file("notes.md")


@pytest.mark.parametrize("name", ["missing.md", "../yaml/notes.yaml"])
def test_a_filename_outside_mds_own_list_is_refused_not_read_or_written(api, name):
    with pytest.raises(PipelineError):
        api.load_file(name)
    with pytest.raises(PipelineError):
        api.save_file(name, HEADER, "x")
    with pytest.raises(PipelineError):
        api.render_file(name, HEADER, "x")


def test_render_file_saves_first_then_skips_the_build_when_topic_and_date_are_blank(api):
    result = api.render_file("notes.md", {**HEADER, "topic": "", "date": ""}, "x")
    assert result["ok"] is False
    assert result["saved"] is True
    assert "topic and date" in result["log"]
    assert api.pipeline.read_markdown_file("notes.md") == "x"


def test_render_file_builds_in_this_windows_own_build_directory(api, project, monkeypatch):
    pdf = project / "pdf" / "out.pdf"
    calls = []

    def fake_render(filename, builddir):
        calls.append((filename, builddir))
        pdf.write_text("%PDF-1.4")
        return True, "log", pdf

    monkeypatch.setattr(api.pipeline, "render", fake_render)
    result = api.render_file("notes.md", HEADER, "x")
    assert len(calls) == 1
    assert calls[0][0] == "notes.md"
    assert re.fullmatch(r"build/app-[0-9a-f]{32}", calls[0][1])
    assert result["ok"] is True
    assert result["pdf"]["name"] == "out.pdf"
    assert result["pdf"]["path"] == str(pdf)
    assert api.pdf_path("out.pdf") == pdf


@pytest.mark.parametrize("name", ["../md/notes.md", "missing.pdf", "notes.md", 5])
def test_pdf_path_only_names_files_directly_inside_pdf(api, name):
    with pytest.raises(PipelineError):
        api.pdf_path(name)


def test_stale_build_dirs_are_pruned_on_startup_and_cleanup_removes_this_windows_own(project):
    stale = project / "build" / "app-old"
    keep = project / "build" / "example"
    stale.mkdir(parents=True)
    keep.mkdir()
    api = Api(project)
    assert not stale.exists()
    assert keep.exists()

    own = project / api.build_dir
    own.mkdir(parents=True)
    api.cleanup()
    assert not own.exists()


def test_asset_lifecycle_add_folder_create_rename_move_delete(api, project, tmp_path):
    source = tmp_path / "tux.png"
    source.write_bytes(b"png")
    data = api.add_assets("", [source])
    assert data["errors"] == []
    assert data["files"] == [
        {"name": "tux.png", "path": str(project / "assets" / "tux.png"), "size": 3, "image": True}
    ]

    api.create_asset_folder("", "img")
    data = api.rename_asset_folder("", "img", "pics")
    assert data["folders"] == ["pics"]

    data = api.move_assets("", ["tux.png"], "pics")
    assert data["errors"] == []
    assert data["all_files"] == ["pics/tux.png"]

    data = api.delete_asset("pics", "tux.png")
    assert data["files"] == []
    data = api.delete_asset_folder("", "pics")
    assert data["folders"] == []


def test_add_and_move_report_per_file_errors_without_failing_the_rest(api, tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_bytes(b"1")
    b.write_bytes(b"3")
    api.add_assets("", [a])
    data = api.add_assets("", [a, b, tmp_path / "gone.txt"])
    assert len(data["errors"]) == 2
    assert data["all_files"] == ["a.txt", "b.txt"]

    data = api.move_assets("", ["a.txt", "nope.txt"], "")
    assert len(data["errors"]) == 2


def test_deleting_folder_dotdot_is_refused_and_leaves_the_project_alone(api, project):
    with pytest.raises(PipelineError):
        api.delete_asset_folder("", "..")
    assert (project / "md").exists()


def test_wrong_typed_content_is_refused_with_a_pipeline_error(api):
    with pytest.raises(PipelineError, match="header object"):
        api.save_file("notes.md", [], "x")
    with pytest.raises(PipelineError, match="'markdown'"):
        api.save_file("notes.md", HEADER, None)


def test_import_markdown_copies_a_file_in_as_a_new_note(api, project, tmp_path):
    source = tmp_path / "Meeting Notes (draft).md"
    source.write_bytes("\ufeff# Hello\r\nwörld\n".encode("utf-8"))
    file, files = api.import_markdown(source)
    assert file == "Meeting-Notes-draft.md"
    assert files == ["Meeting-Notes-draft.md", "notes.md"]
    # The text as it was -- line endings included, byte-order mark dropped.
    assert api.pipeline.read_markdown_file(file) == "# Hello\r\nwörld\n"
    assert api.pipeline.read_header(file)["topic"] == ""
    assert source.exists()

    # The same name again doesn't overwrite the first import.
    source.write_text("second", encoding="utf-8")
    assert api.import_markdown(source)[0] == "Meeting-Notes-draft-2.md"
    assert api.import_markdown(source)[0] == "Meeting-Notes-draft-3.md"
    assert api.pipeline.read_markdown_file("Meeting-Notes-draft.md").startswith("# Hello")


def test_import_markdown_refuses_what_it_cant_read_as_text(api, tmp_path):
    binary = tmp_path / "photo.md"
    binary.write_bytes(b"\xff\xfe\x00\x80")
    with pytest.raises(PipelineError, match="UTF-8"):
        api.import_markdown(binary)
    with pytest.raises(PipelineError, match="Couldn't read"):
        api.import_markdown(tmp_path / "missing.md")
    assert api.list_files() == ["notes.md"]


@pytest.mark.skipif(not shutil.which("pandoc"), reason="needs pandoc")
def test_export_tex_inlines_every_generated_fragment_into_the_template(tmp_path):
    api = Api(tmp_path / "fresh")
    api.project_root.mkdir()
    api.init_project()
    data = api.load_file("notes.md")
    result = api.export_tex("notes.md", data["header"], data["markdown"])
    assert result["ok"], result["log"]
    assert result["name"] == "Example-Meeting_2026-08-25_Teams.tex"
    tex = result["tex"]
    assert "\\cnBuildDir/" not in tex.split("\\providecommand{\\cnBuildDir}")[1]
    assert "Example Meeting" in tex  # the header fragment
    assert "Welcome to the jungle" in tex  # the content fragment
    assert tex.rstrip().endswith("\\end{document}")


@pytest.mark.skipif(not (shutil.which("pandoc") and shutil.which("pdflatex")), reason="needs pandoc and pdflatex")
def test_exported_tex_compiles_on_its_own_from_the_project_folder(tmp_path):
    import subprocess

    api = Api(tmp_path / "fresh")
    api.project_root.mkdir()
    api.init_project()
    data = api.load_file("notes.md")
    tex = api.export_tex("notes.md", data["header"], data["markdown"])["tex"]
    (api.project_root / "exported.tex").write_text(tex, encoding="utf-8")
    api.cleanup()  # nothing generated left behind for it to lean on
    for _ in range(2):
        run = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "exported.tex"],
            cwd=api.project_root, capture_output=True, text=True, errors="replace",
        )
        assert run.returncode == 0, run.stdout[-2000:]
    assert (api.project_root / "exported.pdf").stat().st_size > 10_000
