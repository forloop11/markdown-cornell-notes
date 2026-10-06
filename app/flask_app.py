"""Flask front end for the Cornell notes pipeline: edit the header and a
markdown file, render, and preview the resulting PDF -- all without leaving
the browser. Run with `make app` (see ../Makefile) or directly, from a
project directory:

    python3 app/flask_app.py [--host HOST] [--port PORT]

The page itself (templates/index.html + static/app.js) is a single-page UI
over the small JSON API below; all state lives on disk (md/, yaml/, pdf/,
assets/ -- see pipeline.py) or in the browser tab, none in this process.
"""
import argparse
import re
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import header_form
import pipeline

# The editor/PDF pane height in pixels at the pane-height dropdown's "100%".
# Deliberately shorter than a full-width, letter-size page (aspect ratio
# 11/8.5 ~= 1.29 -- see settings/page.yaml's `paper`), so both panes fit
# comfortably on screen; the PDF frame still fills its full width via
# #view=FitH (see app.js), just with some scrolling needed to see the
# bottom of the page.
BASE_PANE_HEIGHT = 600

# Offered next to the Render button so the editor/PDF panes can be shrunk
# (e.g. on a smaller screen) or grown beyond BASE_PANE_HEIGHT's default.
PANE_HEIGHT_OPTIONS = [f"{pct}%" for pct in range(30, 201, 10)]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

# A browser tab's build id (see index() and render_file()) -- uuid4().hex.
_BUILD_ID_RE = re.compile(r"[0-9a-f]{32}")


def _prune_stale_build_dirs():
    """Remove any build/app-<id> directories left over from a previous run
    of the app (see render_file's per-tab BUILDDIR). Called once at
    startup, before any tab has had a chance to create its own, so anything
    matching app-* here must be left over from a *previous* run.
    """
    build_root = pipeline.PROJECT_ROOT / "build"
    if not build_root.is_dir():
        return
    for child in build_root.iterdir():
        if child.is_dir() and child.name.startswith("app-"):
            shutil.rmtree(child, ignore_errors=True)


def _json_body():
    """The request's JSON object body, or a 400 if it isn't one."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected a JSON object body.")
    return body


def _str_field(body, key, default=""):
    """body[key] (or `default` if absent), or a 400 if it isn't a string."""
    value = body.get(key, default)
    if not isinstance(value, str):
        abort(400, description=f"Expected a string for {key!r}.")
    return value


def _existing_pdf(md_filename):
    """{"name", "version"} for the PDF md_filename's current header would
    build to, if that PDF already exists on disk -- else None. `version`
    (the file's mtime) lets the browser bust its cache after a re-render.
    """
    try:
        slug = pipeline.topic_slug(pipeline.yaml_path_for(md_filename))
    except pipeline.PipelineError:
        return None
    return _pdf_info(pipeline.PDF_DIR / f"{slug}.pdf")


def _pdf_info(path):
    """{"name", "version"} for an existing PDF at `path`, else None."""
    if path is None or not path.is_file():
        return None
    return {"name": path.name, "version": path.stat().st_mtime_ns}


def _save(filename, body):
    """Write the header form and markdown in request `body` to filename's
    yaml/md files, returning the stored header fields.
    """
    header = body.get("header")
    if not isinstance(header, dict):
        abort(400, description="Expected a header object.")
    header_fields = header_form.header_from_form(header)
    markdown = _str_field(body, "markdown", None)
    pipeline.write_header(filename, header_fields)
    pipeline.write_markdown_file(filename, markdown)
    return header_fields


def _check_markdown_file(filename):
    """Raise PipelineError unless `filename` is one of md/'s files."""
    if filename not in pipeline.list_markdown_files():
        raise pipeline.PipelineError(f"{filename} not found.")


def _asset_listing(subdir):
    """Everything the Assets panel and the editor's path autocompletion
    need for folder assets/<subdir>.
    """
    folders, files = pipeline.list_asset_dir(subdir)
    base = pipeline.ASSETS_DIR / subdir
    return {
        "dir": subdir,
        "folders": folders,
        "files": [
            {
                "name": name,
                "size": (base / name).stat().st_size,
                "image": Path(name).suffix.lower() in IMAGE_SUFFIXES,
            }
            for name in files
        ],
        "folder_paths": pipeline.list_asset_folder_paths(),
        "all_files": pipeline.list_asset_files(),
    }


def create_app():
    """Build the Flask app for the project in pipeline.PROJECT_ROOT."""
    app = Flask(__name__)
    if pipeline.project_initialized():
        _prune_stale_build_dirs()

    @app.before_request
    def reject_cross_origin_writes():
        """Refuse state-changing requests sent from some other site's page.

        `make app` binds 0.0.0.0 with no login, so this is what stops a
        page on any other origin from (say) POSTing a form-encoded asset
        upload or delete here. Browsers always send Origin on cross-origin
        POST/PUT/PATCH/DELETE; a request with no Origin at all (curl,
        tests) didn't come from a browser page, so it's let through.
        """
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            abort(403, description="Cross-origin request refused.")
        return None

    @app.errorhandler(pipeline.PipelineError)
    def pipeline_error(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def http_error(exc):
        if request.path.startswith("/api/"):
            return jsonify(error=exc.description), exc.code
        return exc

    @app.get("/")
    def index():
        if not pipeline.project_initialized():
            return render_template("not_initialized.html", project_root=pipeline.PROJECT_ROOT), 500
        config = {
            # Keys this tab's own BUILDDIR (see render_file) so two tabs
            # rendering around the same time never race on the same scratch
            # directory.
            "buildId": uuid.uuid4().hex,
            "basePaneHeight": BASE_PANE_HEIGHT,
            "paneHeightOptions": PANE_HEIGHT_OPTIONS,
            "tzOptions": header_form.TZ_OPTIONS,
        }
        return render_template("index.html", config=config)

    @app.get("/api/files")
    def list_files():
        return jsonify(files=pipeline.list_markdown_files())

    @app.post("/api/files")
    def create_file():
        created = pipeline.create_markdown_file(_str_field(_json_body(), "name"))
        return jsonify(file=created, files=pipeline.list_markdown_files()), 201

    @app.get("/api/files/<filename>")
    def load_file(filename):
        _check_markdown_file(filename)
        return jsonify(
            name=filename,
            header=header_form.form_from_header(pipeline.read_header(filename)),
            markdown=pipeline.read_markdown_file(filename),
            pdf=_existing_pdf(filename),
        )

    @app.put("/api/files/<filename>")
    def save_file(filename):
        """Autosave target: the browser calls this whenever the header or
        markdown changes (debounced), so a closed tab between renders
        doesn't lose what was typed.
        """
        _check_markdown_file(filename)
        try:
            _save(filename, _json_body())
        except OSError as exc:
            return jsonify(error=f"Couldn't autosave {filename}: {exc}"), 500
        return jsonify(ok=True)

    @app.delete("/api/files/<filename>")
    def delete_file(filename):
        pipeline.delete_markdown_file(filename)
        return jsonify(files=pipeline.list_markdown_files())

    @app.post("/api/files/<filename>/render")
    def render_file(filename):
        """Save the posted header/markdown, then build filename's PDF.

        The posted content is exactly what's in the browser at the moment
        Render was clicked, so the build never runs against a stale save.
        """
        _check_markdown_file(filename)
        body = _json_body()
        build_id = _str_field(body, "build_id")
        if not _BUILD_ID_RE.fullmatch(build_id):
            abort(400, description="Invalid build id.")

        try:
            header_fields = _save(filename, body)
        except OSError as exc:
            return jsonify(
                ok=False, saved=False, log=f"Render skipped: couldn't save changes to disk.\n{exc}", pdf=None
            )

        missing = [name for name in ("topic", "date") if not header_fields[name].strip()]
        if missing:
            return jsonify(
                ok=False,
                saved=True,
                log=(
                    f"Render skipped: {' and '.join(missing)} field(s) empty.\n"
                    "Fill in the header before rendering, or the output PDF's name "
                    "and header row will end up mostly blank."
                ),
                pdf=None,
            )

        success, log, pdf_path = pipeline.render(filename, builddir=f"build/app-{build_id}")
        return jsonify(ok=success, saved=True, log=log, pdf=_pdf_info(pdf_path))

    @app.get("/pdf/<filename>")
    def pdf(filename):
        """Serve a built PDF inline (for the preview pane), or as a
        download with ?download=1.
        """
        return send_from_directory(
            pipeline.PDF_DIR,
            filename,
            mimetype="application/pdf",
            as_attachment=request.args.get("download") == "1",
            max_age=0,
        )

    @app.get("/asset-files/<path:subpath>")
    def asset_file(subpath):
        """Serve a file from assets/ (the Assets panel's image thumbnails)."""
        return send_from_directory(pipeline.ASSETS_DIR, subpath, max_age=0)

    @app.get("/api/assets")
    def list_assets():
        return jsonify(_asset_listing(request.args.get("dir", "")))

    @app.post("/api/assets/upload")
    def upload_assets():
        subdir = request.form.get("dir", "")
        errors = []
        for upload in request.files.getlist("files"):
            try:
                pipeline.save_asset(upload.filename or "", upload.read(), subdir)
            except pipeline.PipelineError as exc:
                errors.append(str(exc))
        return jsonify(errors=errors, **_asset_listing(subdir))

    @app.post("/api/assets/folders")
    def create_asset_folder():
        body = _json_body()
        subdir = _str_field(body, "dir")
        pipeline.create_asset_folder(_str_field(body, "name"), subdir)
        return jsonify(_asset_listing(subdir))

    @app.patch("/api/assets/folders")
    def rename_asset_folder():
        body = _json_body()
        subdir = _str_field(body, "dir")
        pipeline.rename_asset_folder(_str_field(body, "name"), _str_field(body, "new_name"), subdir)
        return jsonify(_asset_listing(subdir))

    @app.delete("/api/assets/folders")
    def delete_asset_folder():
        body = _json_body()
        subdir = _str_field(body, "dir")
        pipeline.delete_asset_folder(_str_field(body, "name"), subdir)
        return jsonify(_asset_listing(subdir))

    @app.delete("/api/assets/files")
    def delete_asset():
        body = _json_body()
        subdir = _str_field(body, "dir")
        pipeline.delete_asset(_str_field(body, "name"), subdir)
        return jsonify(_asset_listing(subdir))

    @app.post("/api/assets/move")
    def move_assets():
        body = _json_body()
        subdir = _str_field(body, "dir")
        names = body.get("names")
        if not isinstance(names, list):
            abort(400, description="Expected a list of names.")
        dest = _str_field(body, "dest")
        errors = []
        for name in names:
            try:
                pipeline.move_asset(name, subdir, dest)
            except pipeline.PipelineError as exc:
                errors.append(str(exc))
        return jsonify(errors=errors, **_asset_listing(subdir))

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1", help="address to bind (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8501, help="port to listen on (default: %(default)s)")
    args = parser.parse_args()
    create_app().run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
