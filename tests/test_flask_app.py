"""Tests for app/flask_app.py's JSON API, run against an isolated project
(see the `project` fixture in conftest.py). Rendering itself
(pipeline.render) needs the full pandoc/TeX Live toolchain, so it's only
covered up to the point where it would shell out to make.
"""
import io

import pytest

pytest.importorskip("flask")

import flask_app  # noqa: E402  (after importorskip on purpose)
import pipeline  # noqa: E402


@pytest.fixture
def client(project):
    pipeline.create_markdown_file("notes")
    app = flask_app.create_app()
    app.testing = True
    return app.test_client()


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


def test_index_page(client):
    """The page renders with its config (build id, timezone list) inline."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"America/Detroit" in response.data
    assert b'"buildId"' in response.data


def test_index_without_project(tmp_path, monkeypatch):
    """An uninitialized directory gets the "run init" page, not a crash."""
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "MD_DIR", tmp_path / "md")
    monkeypatch.setattr(pipeline, "YAML_DIR", tmp_path / "yaml")
    response = flask_app.create_app().test_client().get("/")
    assert response.status_code == 500
    assert b"No project found" in response.data


def test_save_and_load_file(client, project):
    """PUT writes the composed yaml header and markdown; GET reads them
    back as form values.
    """
    response = client.put("/api/files/notes.md", json={"header": HEADER, "markdown": "# Hi\n"})
    assert response.status_code == 200
    assert pipeline.read_header("notes.md")["time"] == "10:00--10:30 EDT"
    assert (project / "md" / "notes.md").read_text(encoding="utf-8") == "# Hi\n"

    data = client.get("/api/files/notes.md").get_json()
    assert data["markdown"] == "# Hi\n"
    # tz_hint is re-parsed from "time" on load; it's only ever used when
    # no real timezone is picked, so it doesn't change what gets saved.
    assert data["header"] == dict(HEADER, tz_hint="EDT")
    assert data["pdf"] is None


def test_create_and_delete_file(client):
    """POST creates a sanitized file; DELETE removes it."""
    response = client.post("/api/files", json={"name": "Team Sync!"})
    assert response.status_code == 201
    assert response.get_json() == {"file": "Team-Sync.md", "files": ["Team-Sync.md", "notes.md"]}
    assert client.delete("/api/files/Team-Sync.md").get_json() == {"files": ["notes.md"]}


def test_delete_last_file_is_refused(client):
    response = client.delete("/api/files/notes.md")
    assert response.status_code == 400
    assert "last remaining" in response.get_json()["error"]


def test_unknown_file_is_404ish(client):
    """Any filename outside md/'s own list is refused, not read/written."""
    for path in ("/api/files/missing.md", "/api/files/..%2Fyaml%2Fnotes.yaml"):
        assert client.get(path).status_code in (400, 404)
        assert client.put(path, json={"header": HEADER, "markdown": "x"}).status_code in (400, 404)


def test_render_requires_topic_and_date(client):
    """Render saves first, then skips the build when topic/date are blank."""
    header = dict(HEADER, topic="", date="")
    response = client.post(
        "/api/files/notes.md/render", json={"header": header, "markdown": "x", "build_id": "a" * 32}
    )
    data = response.get_json()
    assert data["ok"] is False
    assert data["saved"] is True
    assert "topic and date" in data["log"]


def test_render_rejects_bad_build_id(client):
    """build_id becomes part of a directory name, so it must be hex only."""
    response = client.post(
        "/api/files/notes.md/render", json={"header": HEADER, "markdown": "x", "build_id": "../../etc"}
    )
    assert response.status_code == 400


def test_render_runs_pipeline(client, monkeypatch, project):
    """A valid render builds in this tab's own build/app-<id> directory."""
    pdf = project / "pdf" / "out.pdf"
    calls = []

    def fake_render(filename, builddir):
        calls.append((filename, builddir))
        pdf.write_bytes(b"%PDF-1.4")
        return True, "log", pdf

    monkeypatch.setattr(pipeline, "render", fake_render)
    data = client.post(
        "/api/files/notes.md/render", json={"header": HEADER, "markdown": "x", "build_id": "b" * 32}
    ).get_json()
    assert calls == [("notes.md", f"build/app-{'b' * 32}")]
    assert data["ok"] is True
    assert data["pdf"]["name"] == "out.pdf"
    assert client.get("/pdf/out.pdf").data == b"%PDF-1.4"
    download = client.get("/pdf/out.pdf?download=1")
    assert "attachment" in download.headers["Content-Disposition"]


def test_stale_build_dirs_pruned_on_startup(project):
    """build/app-* left by a previous run is removed when the app starts."""
    pipeline.create_markdown_file("notes")
    stale = project / "build" / "app-old"
    stale.mkdir(parents=True)
    keep = project / "build" / "example"
    keep.mkdir()
    flask_app.create_app()
    assert not stale.exists()
    assert keep.exists()


def test_asset_lifecycle(client):
    """Upload, folder create/rename, move, and delete via the API."""
    data = client.post(
        "/api/assets/upload",
        data={"dir": "", "files": [(io.BytesIO(b"png"), "tux.png")]},
        content_type="multipart/form-data",
    ).get_json()
    assert data["errors"] == []
    assert data["files"] == [{"name": "tux.png", "size": 3, "image": True}]
    assert client.get("/asset-files/tux.png").data == b"png"

    client.post("/api/assets/folders", json={"dir": "", "name": "img"})
    data = client.patch("/api/assets/folders", json={"dir": "", "name": "img", "new_name": "pics"}).get_json()
    assert data["folders"] == ["pics"]

    data = client.post("/api/assets/move", json={"dir": "", "names": ["tux.png"], "dest": "pics"}).get_json()
    assert data["errors"] == []
    assert data["all_files"] == ["pics/tux.png"]

    data = client.delete("/api/assets/files", json={"dir": "pics", "name": "tux.png"}).get_json()
    assert data["files"] == []
    data = client.delete("/api/assets/folders", json={"dir": "", "name": "pics"}).get_json()
    assert data["folders"] == []


def test_asset_folder_delete_cannot_escape(client, project):
    """Deleting folder ".." must not remove the project directory."""
    response = client.delete("/api/assets/folders", json={"dir": "", "name": ".."})
    assert response.status_code == 400
    assert (project / "md").is_dir()


def test_non_string_fields_are_400(client):
    response = client.post("/api/assets/folders", json={"dir": 5, "name": "x"})
    assert response.status_code == 400
    response = client.put("/api/files/notes.md", json={"header": [], "markdown": "x"})
    assert response.status_code == 400


def test_cross_origin_writes_refused(client):
    """A state-changing request from another site's page is rejected;
    same-origin requests (and non-browser ones without Origin) aren't.
    """
    evil = client.post("/api/files", json={"name": "x"}, headers={"Origin": "http://evil.example"})
    assert evil.status_code == 403
    same = client.post("/api/files", json={"name": "y"}, headers={"Origin": "http://localhost"})
    assert same.status_code == 201
