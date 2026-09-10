import pytest

import pipeline


def test_project_initialized(project):
    assert pipeline.project_initialized()


def test_project_not_initialized(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "MD_DIR", tmp_path / "md")
    monkeypatch.setattr(pipeline, "YAML_DIR", tmp_path / "yaml")
    assert not pipeline.project_initialized()


def test_yaml_path_for(project):
    assert pipeline.yaml_path_for("weekly-sync.md") == project / "yaml" / "weekly-sync.yaml"


def test_read_header_missing_file_returns_blank_fields(project):
    fields = pipeline.read_header("does-not-exist.md")
    assert fields == {name: "" for name in pipeline.HEADER_FIELDS}


def test_write_read_header_round_trip(project):
    fields = {
        "topic": "Weekly Sync",
        "date": "2026-08-23",
        "attendees": "Lily, Amber",
        "time": "10:00--10:30 EDT",
        "timezone": "America/Detroit",
        "location": "Zoom",
    }
    pipeline.write_header("notes.md", fields)
    assert pipeline.read_header("notes.md") == fields


def test_write_read_header_round_trip_special_chars(project):
    # The exact class of bug this guards against: write_header escapes
    # `"` and `\` for the yaml file, and simple_yaml.strip_quotes must
    # unescape them back to the original on read.
    fields = {name: "" for name in pipeline.HEADER_FIELDS}
    fields["topic"] = 'Say "hi" \\ok'
    fields["location"] = "C:\\path"
    pipeline.write_header("notes.md", fields)
    assert pipeline.read_header("notes.md") == fields


def test_create_list_read_delete_markdown_file(project):
    created = pipeline.create_markdown_file("My Notes!")
    assert created == "My-Notes.md"
    assert created in pipeline.list_markdown_files()
    assert pipeline.read_markdown_file(created) == "# New notes\n"
    assert pipeline.read_header(created) == {name: "" for name in pipeline.HEADER_FIELDS}

    # A second file, so deleting the first isn't blocked by the
    # last-file guard below.
    pipeline.create_markdown_file("other")
    pipeline.delete_markdown_file(created)
    assert created not in pipeline.list_markdown_files()
    assert not pipeline.yaml_path_for(created).exists()


def test_create_markdown_file_duplicate_raises(project):
    pipeline.create_markdown_file("dup")
    with pytest.raises(pipeline.PipelineError):
        pipeline.create_markdown_file("dup")


def test_create_markdown_file_empty_name_raises(project):
    with pytest.raises(pipeline.PipelineError):
        pipeline.create_markdown_file("   ")


def test_create_markdown_file_sanitizes_unsafe_characters(project):
    # Path(name).stem drops any directory component first (like
    # _sanitize_name's Path(name).name), so "a/" here is discarded rather
    # than folded into the filename -- only "b?c*d" gets slugified.
    created = pipeline.create_markdown_file("a/b?c*d")
    assert created == "b-c-d.md"


def test_delete_last_markdown_file_raises(project):
    only = pipeline.create_markdown_file("only")
    with pytest.raises(pipeline.PipelineError):
        pipeline.delete_markdown_file(only)


def test_delete_markdown_file_not_found_raises(project):
    with pytest.raises(pipeline.PipelineError):
        pipeline.delete_markdown_file("nope.md")


def test_write_markdown_file_round_trip(project):
    pipeline.create_markdown_file("notes")
    pipeline.write_markdown_file("notes.md", "hello world\n")
    assert pipeline.read_markdown_file("notes.md") == "hello world\n"


def test_topic_slug(project):
    pipeline.write_header(
        "notes.md",
        {
            "topic": "Weekly Sync",
            "date": "2026-08-23",
            "attendees": "",
            "time": "",
            "timezone": "",
            "location": "Zoom",
        },
    )
    slug = pipeline.topic_slug(pipeline.yaml_path_for("notes.md"))
    assert slug == "Weekly-Sync_2026-08-23_Zoom"


def test_topic_slug_all_blank_fields_falls_back(project):
    pipeline.write_header("notes.md", {name: "" for name in pipeline.HEADER_FIELDS})
    slug = pipeline.topic_slug(pipeline.yaml_path_for("notes.md"))
    assert slug == "cornell-notes"


class TestAssetFolders:
    def test_create_and_list(self, project):
        pipeline.create_asset_folder("diagrams")
        folders, files = pipeline.list_asset_dir()
        assert folders == ["diagrams"]
        assert files == []

    def test_create_duplicate_raises(self, project):
        pipeline.create_asset_folder("diagrams")
        with pytest.raises(pipeline.PipelineError):
            pipeline.create_asset_folder("diagrams")

    def test_rename(self, project):
        pipeline.create_asset_folder("old-name")
        renamed = pipeline.rename_asset_folder("old-name", "new name!")
        assert renamed == "new-name"
        folders, _ = pipeline.list_asset_dir()
        assert folders == ["new-name"]

    def test_delete_removes_contents(self, project):
        pipeline.create_asset_folder("diagrams")
        pipeline.save_asset("flow.png", b"fake-png-bytes", "diagrams")
        pipeline.delete_asset_folder("diagrams")
        folders, _ = pipeline.list_asset_dir()
        assert folders == []

    def test_nested_folder_paths(self, project):
        pipeline.create_asset_folder("diagrams")
        pipeline.create_asset_folder("flowcharts", "diagrams")
        assert pipeline.list_asset_folder_paths() == ["", "diagrams", "diagrams/flowcharts"]


class TestAssetFiles:
    def test_save_list_delete(self, project):
        pipeline.save_asset("tux.jpg", b"fake-jpg-bytes")
        assert pipeline.list_asset_files() == ["tux.jpg"]
        pipeline.delete_asset("tux.jpg")
        assert pipeline.list_asset_files() == []

    def test_save_duplicate_raises(self, project):
        pipeline.save_asset("tux.jpg", b"one")
        with pytest.raises(pipeline.PipelineError):
            pipeline.save_asset("tux.jpg", b"two")

    def test_delete_missing_raises(self, project):
        with pytest.raises(pipeline.PipelineError):
            pipeline.delete_asset("nope.jpg")

    def test_save_sanitizes_path_traversal_in_filename(self, project):
        # Path(name).name in _sanitize_name drops any directory components,
        # so a browser- or hand-crafted "../../etc/passwd"-style name can't
        # escape assets/.
        saved = pipeline.save_asset("../../etc/passwd", b"data")
        assert saved == "passwd"
        assert (pipeline.ASSETS_DIR / "passwd").exists()
        assert not (pipeline.ASSETS_DIR.parent / "etc").exists()

    def test_move_asset_between_folders(self, project):
        pipeline.create_asset_folder("dest")
        pipeline.save_asset("tux.jpg", b"data")
        pipeline.move_asset("tux.jpg", "", "dest")
        assert pipeline.list_asset_files() == ["dest/tux.jpg"]

    def test_move_asset_to_existing_name_raises(self, project):
        pipeline.create_asset_folder("dest")
        pipeline.save_asset("tux.jpg", b"one")
        pipeline.save_asset("tux.jpg", b"two", "dest")
        with pytest.raises(pipeline.PipelineError):
            pipeline.move_asset("tux.jpg", "", "dest")

    def test_resolve_asset_dir_rejects_escaping_subdir(self, project):
        # _resolve_asset_dir is what every asset function above routes
        # through -- covering it once here via a folder operation that
        # takes an arbitrary subdir guards all of them.
        with pytest.raises(pipeline.PipelineError):
            pipeline.create_asset_folder("evil", "../../../../etc")
