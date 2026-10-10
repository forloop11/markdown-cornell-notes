"""Tests for app/pipeline.py, run against an isolated project (see
conftest.py). render() needs the full pandoc/TeX Live toolchain, so its
test skips itself where those aren't installed (e.g. CI); topic_slug()
only needs Python.
"""
import os
import shutil

import pytest

from pipeline import HEADER_FIELDS, NEW_NOTE, REPO_ROOT, Pipeline, PipelineError, rewrite_links
from simple_yaml import parse_yaml


def blank():
    return {field: "" for field in HEADER_FIELDS}


@pytest.fixture
def p(project):
    return Pipeline(project)


def test_project_initialized_is_true_once_md_and_yaml_exist(p, project):
    assert p.project_initialized()
    (project / "md").rmdir()
    assert not p.project_initialized()


def test_yaml_path_for_pairs_md_stem_with_yaml_stem(p, project):
    assert p.yaml_path_for("weekly-sync.md") == project / "yaml" / "weekly-sync.yaml"


def test_read_header_with_no_paired_yaml_returns_every_field_blank(p):
    assert p.read_header("does-not-exist.md") == blank()


def test_write_header_then_read_header_round_trips(p):
    fields = {
        "topic": "Weekly Sync",
        "date": "2026-08-23",
        "attendees": "Lily, Amber",
        "time": "10:00--10:30 EDT",
        "timezone": "America/Detroit",
        "location": "Zoom",
    }
    p.write_header("notes.md", fields)
    assert p.read_header("notes.md") == fields


def test_write_header_escapes_quotes_and_backslashes(p):
    fields = {**blank(), "topic": 'Say "hi" \\ok', "location": "C:\\path"}
    p.write_header("notes.md", fields)
    assert p.read_header("notes.md") == fields
    # simple_yaml.py is what `make build` reads headers with.
    assert parse_yaml(p.yaml_path_for("notes.md"))["topic"] == 'Say "hi" \\ok'


def test_create_list_read_delete_a_markdown_file_and_its_paired_yaml(p):
    created = p.create_markdown_file("My Notes!")
    assert created == "My-Notes.md"
    assert created in p.list_markdown_files()
    assert p.read_markdown_file(created) == NEW_NOTE
    assert p.read_header(created) == blank()

    # A second file, so deleting the first isn't blocked by the last-file guard.
    p.create_markdown_file("other")
    p.delete_markdown_file(created)
    assert created not in p.list_markdown_files()
    assert not p.yaml_path_for(created).exists()


def test_create_markdown_file_refuses_duplicates_and_blank_names(p):
    p.create_markdown_file("dup")
    with pytest.raises(PipelineError):
        p.create_markdown_file("dup")
    with pytest.raises(PipelineError):
        p.create_markdown_file("   ")


def test_create_markdown_file_drops_directory_parts_and_slugifies_the_rest(p):
    assert p.create_markdown_file("a/b?c*d") == "b-c-d.md"
    assert p.create_markdown_file("notes.md") == "notes.md"


def test_delete_markdown_file_refuses_the_last_file_and_unknown_names(p):
    only = p.create_markdown_file("only")
    with pytest.raises(PipelineError):
        p.delete_markdown_file(only)
    with pytest.raises(PipelineError):
        p.delete_markdown_file("nope.md")


def test_write_markdown_file_then_read_markdown_file_round_trips(p):
    p.create_markdown_file("notes")
    p.write_markdown_file("notes.md", "hello world\n")
    assert p.read_markdown_file("notes.md") == "hello world\n"


@pytest.mark.parametrize("name", ["../yaml/notes.yaml", "..", "missing.md", "notes.txt"])
def test_read_and_write_markdown_file_refuse_names_outside_md(p, project, name):
    p.create_markdown_file("notes")
    (project / "md" / "notes.txt").write_text("x")
    with pytest.raises(PipelineError):
        p.read_markdown_file(name)
    with pytest.raises(PipelineError):
        p.write_markdown_file(name, "overwritten")
    assert (project / "yaml" / "notes.yaml").read_text() != "overwritten"


def test_topic_slug_joins_slugified_topic_date_location(p):
    p.write_header("notes.md", {**blank(), "topic": "Weekly Sync", "date": "2026-08-23", "location": "Zoom"})
    assert p.topic_slug(p.yaml_path_for("notes.md")) == "Weekly-Sync_2026-08-23_Zoom"


def test_topic_slug_falls_back_to_cornell_notes_when_all_fields_are_blank(p):
    p.write_header("notes.md", blank())
    assert p.topic_slug(p.yaml_path_for("notes.md")) == "cornell-notes"


def test_init_project_scaffolds_the_same_files_as_make_init(tmp_path):
    p = Pipeline(tmp_path / "fresh")
    p.project_root.mkdir()
    assert not p.project_initialized()
    p.init_project()
    assert p.project_initialized()
    for file in ["md/notes.md", "yaml/notes.yaml", "settings/page.yaml", "assets/tux.jpg"]:
        assert (p.project_root / file).is_file(), file
    assert (p.project_root / "pdf").is_dir()


def test_init_project_refuses_a_directory_that_already_has_project_folders(p):
    with pytest.raises(PipelineError):
        p.init_project()


def test_init_project_refuses_the_source_tree_itself():
    with pytest.raises(PipelineError, match="source tree"):
        Pipeline(REPO_ROOT).init_project()


def test_child_env_prepends_path_dirs_to_the_existing_path_key(project):
    p = Pipeline(project, tools={"path_dirs": ["/opt/a", "/opt/b"]})
    env = p.child_env()
    keys = [k for k in env if k.upper() == "PATH"]
    assert len(keys) == 1
    assert env[keys[0]].startswith(os.pathsep.join(["/opt/a", "/opt/b"]) + os.pathsep)
    assert env["PYTHONUTF8"] == "1"


@pytest.mark.skipif(
    not (shutil.which("pdflatex") and shutil.which("pandoc")), reason="needs pdflatex and pandoc"
)
def test_render_with_direct_build_produces_the_pdf_and_cleans_up(tmp_path):
    p = Pipeline(tmp_path / "direct", tools={"direct_build": True})
    p.project_root.mkdir()
    p.init_project()
    success, log, pdf_path = p.render("notes.md", "build/app-test")
    assert success, log
    assert pdf_path == p.pdf_dir / f"{p.topic_slug(p.yaml_path_for('notes.md'))}.pdf"
    assert [f.name for f in p.pdf_dir.iterdir()] == [pdf_path.name]


def test_asset_folders_create_rename_nest_delete_with_contents(p):
    p.create_asset_folder("diagrams")
    assert p.list_asset_dir() == (["diagrams"], [])
    with pytest.raises(PipelineError):
        p.create_asset_folder("diagrams")

    p.create_asset_folder("flowcharts", "diagrams")
    assert p.list_asset_folder_paths() == ["", "diagrams", "diagrams/flowcharts"]

    assert p.rename_asset_folder("diagrams", "new name!") == "new-name"
    assert p.list_asset_dir()[0] == ["new-name"]

    p.save_asset("flow.png", b"png", "new-name")
    p.delete_asset_folder("new-name")
    assert p.list_asset_dir()[0] == []


def test_asset_files_save_list_refuse_duplicates_move_delete(p):
    p.save_asset("tux.jpg", b"one")
    assert p.list_asset_files() == ["tux.jpg"]
    with pytest.raises(PipelineError):
        p.save_asset("tux.jpg", b"two")

    p.create_asset_folder("dest")
    p.save_asset("tux.jpg", b"two", "dest")
    with pytest.raises(PipelineError):
        p.move_asset("tux.jpg", "", "dest")
    p.delete_asset("tux.jpg", "dest")
    p.move_asset("tux.jpg", "", "dest")
    assert p.list_asset_files() == ["dest/tux.jpg"]

    with pytest.raises(PipelineError):
        p.delete_asset("nope.jpg")


def test_save_asset_drops_directory_parts_from_the_file_name(p, project):
    assert p.save_asset("../../etc/passwd", b"data") == "passwd"
    assert (project / "assets" / "passwd").exists()
    assert not (project / "etc").exists()


def test_a_subdir_outside_assets_is_refused(p):
    with pytest.raises(PipelineError):
        p.create_asset_folder("evil", "../../../../etc")


def test_a_symlinked_folder_leading_outside_assets_is_refused(p, project):
    (project / "outside").mkdir()
    (project / "assets" / "link").symlink_to(project / "outside")
    with pytest.raises(PipelineError):
        p.save_asset("x.txt", b"x", "link")


@pytest.mark.parametrize("name", ["..", ".", "", "../outside", "sub/file.jpg", "..\\outside"])
def test_an_asset_entry_name_cant_escape_its_folder(p, project, name):
    # Deleting folder ".." would otherwise remove the whole project.
    (project / "outside").mkdir()
    for call in (
        lambda: p.delete_asset(name),
        lambda: p.delete_asset_folder(name),
        lambda: p.rename_asset_folder(name, "renamed"),
        lambda: p.move_asset(name, "", ""),
    ):
        with pytest.raises(PipelineError):
            call()
    assert (project / "outside").exists()
    assert (project / "md").exists()


@pytest.mark.skipif(
    not (shutil.which("pdflatex") and shutil.which("pandoc")), reason="needs pdflatex and pandoc"
)
def test_render_with_an_image_that_has_no_explicit_size(tmp_path):
    # As the assets explorer's "Copy Markdown Link" writes it.
    p = Pipeline(tmp_path / "image", tools={"direct_build": True})
    p.project_root.mkdir()
    p.init_project()
    p.write_markdown_file("notes.md", "# Picture\n\n![tux](assets/tux.jpg)\n\nInline ![tux](assets/tux.jpg) too.\n")
    success, log, pdf_path = p.render("notes.md", "build/app-test")
    assert success, log[-2000:]
    assert pdf_path.is_file()


def test_rename_markdown_file_moves_the_note_and_its_header_together(p, project):
    p.create_markdown_file("draft")
    p.write_markdown_file("draft.md", "# Draft\n")
    p.write_header("draft.md", {**blank(), "topic": "Kickoff"})
    assert p.rename_markdown_file("draft.md", "Kickoff Notes!") == "Kickoff-Notes.md"
    assert p.list_markdown_files() == ["Kickoff-Notes.md"]
    assert p.read_markdown_file("Kickoff-Notes.md") == "# Draft\n"
    assert p.read_header("Kickoff-Notes.md")["topic"] == "Kickoff"
    assert not (project / "yaml" / "draft.yaml").exists()
    # Its own name again is no change, not a collision.
    assert p.rename_markdown_file("Kickoff-Notes.md", "Kickoff-Notes") == "Kickoff-Notes.md"


def test_rename_markdown_file_refuses_a_taken_name_a_blank_one_and_unknown_files(p, project):
    p.create_markdown_file("one")
    p.create_markdown_file("two")
    for call in (
        lambda: p.rename_markdown_file("one.md", "two"),
        lambda: p.rename_markdown_file("one.md", "  "),
        lambda: p.rename_markdown_file("missing.md", "three"),
        lambda: p.rename_markdown_file("../yaml/one.yaml", "three"),
    ):
        with pytest.raises(PipelineError):
            call()
    # A stray header in the way is a collision too: it isn't overwritten.
    (project / "yaml" / "three.yaml").write_text('topic: "keep me"\n')
    with pytest.raises(PipelineError):
        p.rename_markdown_file("one.md", "three")
    assert p.list_markdown_files() == ["one.md", "two.md"]
    assert "keep me" in (project / "yaml" / "three.yaml").read_text()


def test_rename_asset_renames_a_file_in_place(p, project):
    p.create_asset_folder("pics")
    p.save_asset("old name.png", b"png", "pics")
    assert p.rename_asset("old-name.png", "New Name.png", "pics") == "New-Name.png"
    assert p.list_asset_files() == ["pics/New-Name.png"]
    p.save_asset("other.png", b"x", "pics")
    for call in (
        lambda: p.rename_asset("other.png", "New-Name.png", "pics"),  # taken
        lambda: p.rename_asset("nope.png", "x.png", "pics"),
        lambda: p.rename_asset("pics", "album"),  # a folder, not a file
        lambda: p.rename_asset("../md/notes.md", "x.md"),
        lambda: p.rename_asset("other.png", "   ", "pics"),
    ):
        with pytest.raises(PipelineError):
            call()
    assert p.list_asset_files() == ["pics/New-Name.png", "pics/other.png"]


def test_a_new_note_starts_from_a_template_showing_the_format(p):
    name = p.create_markdown_file("fresh")
    text = p.read_markdown_file(name)
    assert text == NEW_NOTE
    assert text.startswith("# New notes\n")
    assert "\n^1 " in text and "\n^^1 " in text


def test_deletions_go_to_the_trash_when_there_is_one(project, tmp_path):
    bin_ = tmp_path / "trash"
    bin_.mkdir()
    trashed = []

    def trash(path):
        trashed.append(path)
        shutil.move(path, bin_ / (str(len(trashed)) + "-" + path.rsplit("/", 1)[-1]))
        return True

    p = Pipeline(project, trash=trash)
    p.create_markdown_file("keep")
    p.create_markdown_file("gone")
    p.save_asset("pic.png", b"png")
    p.create_asset_folder("album")
    p.save_asset("inside.png", b"png", "album")

    p.delete_markdown_file("gone.md")
    p.delete_asset("pic.png")
    p.delete_asset_folder("album")
    assert p.list_markdown_files() == ["keep.md"] and p.list_asset_files() == []
    # Everything deleted is in the trash, recoverable: the note, its header,
    # the file, and the folder with what was in it.
    assert sorted(f.name.split("-", 1)[1] for f in bin_.iterdir()) == ["album", "gone.md", "gone.yaml", "pic.png"]
    assert (next(f for f in bin_.iterdir() if f.name.endswith("album")) / "inside.png").is_file()


@pytest.mark.parametrize("trash", [lambda path: False, lambda path: (_ for _ in ()).throw(OSError("no trash here"))])
def test_deletions_fall_back_to_permanent_where_the_trash_cant_take_them(project, trash):
    p = Pipeline(project, trash=trash)
    p.create_markdown_file("keep")
    p.create_markdown_file("gone")
    p.create_asset_folder("album")
    p.save_asset("inside.png", b"png", "album")
    p.delete_markdown_file("gone.md")
    p.delete_asset_folder("album")
    assert p.list_markdown_files() == ["keep.md"]
    assert not (project / "yaml" / "gone.yaml").exists() and not (project / "assets" / "album").exists()


def test_rewrite_links_repoints_links_to_a_renamed_asset_and_nothing_else():
    text = (
        "![flow](assets/diagrams/flow.png) and [the same](assets/diagrams/flow.png).\n"
        "Sized: ![f](assets/diagrams/flow.png){width=50%} and anchored [x](assets/diagrams/flow.png#top)\n"
        "Others: ![o](assets/diagrams/flow.png.bak) ![p](assets/flow.png) [web](https://e.com/assets/diagrams/flow.png)\n"
        "Prose mentioning assets/diagrams/flow.png stays as it is.\n"
    )
    out, count = rewrite_links(text, "diagrams/flow.png", "diagrams/pipeline.png")
    assert count == 4
    assert out.count("](assets/diagrams/pipeline.png") == 4
    assert "![o](assets/diagrams/flow.png.bak) ![p](assets/flow.png) [web](https://e.com/assets/diagrams/flow.png)" in out
    assert "Prose mentioning assets/diagrams/flow.png stays as it is." in out
    assert rewrite_links("no links here", "a.png", "b.png") == ("no links here", 0)


def test_rewrite_links_follows_a_renamed_or_moved_folder_and_bracketed_paths():
    text = "![a](assets/pics/a.png) ![b](assets/pics/sub/b.png) ![c](assets/pics2/c.png) ![d](<assets/pics/my photo.png>)"
    out, count = rewrite_links(text, "pics", "album/2026", folder=True)
    assert count == 3
    assert out == (
        "![a](assets/album/2026/a.png) ![b](assets/album/2026/sub/b.png) ![c](assets/pics2/c.png) "
        "![d](<assets/album/2026/my photo.png>)"
    )
    # A file moved between folders is a rename of its whole path.
    assert rewrite_links("![a](assets/a.png)", "a.png", "pics/a.png") == ("![a](assets/pics/a.png)", 1)


def test_rewrite_asset_links_updates_every_note_but_the_ones_skipped(p):
    for name in ("one", "two", "three"):
        p.create_markdown_file(name)
    p.write_markdown_file("one.md", "![x](assets/old.png) ![y](assets/old.png)\n")
    p.write_markdown_file("two.md", "![x](assets/old.png)\n")
    p.write_markdown_file("three.md", "nothing\n")
    assert p.asset_link_counts("old.png", "new.png") == {"one.md": 2, "two.md": 1}
    assert p.rewrite_asset_links("old.png", "new.png", skip=["two.md"]) == 2
    assert p.read_markdown_file("one.md") == "![x](assets/new.png) ![y](assets/new.png)\n"
    assert p.read_markdown_file("two.md") == "![x](assets/old.png)\n"
