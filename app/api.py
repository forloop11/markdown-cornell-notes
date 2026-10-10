"""The editor's backend: every operation the window (window.py) asks for,
as plain methods over a Pipeline. Nothing here touches Qt, so the tests
(../tests/test_api.py) can drive it directly.

A user-facing failure -- a name that's taken, a file that's gone -- is
raised as PipelineError, whose message the window shows as-is.
"""
import shutil
import uuid
from pathlib import Path

import header_form
from pipeline import REPO_ROOT, Pipeline, PipelineError

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


class Api:
    def __init__(self, project_root, repo_root=REPO_ROOT, tools=None):
        self.pipeline = Pipeline(project_root, repo_root=repo_root, tools=tools)
        # Keys this window's own BUILDDIR (see render_file) so two app
        # windows rendering around the same time never race on the same
        # scratch directory.
        self.build_dir = f"build/app-{uuid.uuid4().hex}"
        if self.pipeline.project_initialized():
            self.prune_stale_build_dirs()

    def prune_stale_build_dirs(self):
        """Remove build/app-<id> directories left over from a previous run
        (see build_dir). Called once at startup, before this run has
        rendered anything, so any app-* here must be stale.
        """
        build_root = self.pipeline.project_root / "build"
        if not build_root.is_dir():
            return
        for child in build_root.iterdir():
            if child.is_dir() and child.name.startswith("app-"):
                shutil.rmtree(child, ignore_errors=True)

    def cleanup(self):
        """Remove this window's own build directory (on window close)."""
        shutil.rmtree(self.pipeline.project_root / self.build_dir, ignore_errors=True)

    @property
    def project_root(self):
        return self.pipeline.project_root

    def initialized(self):
        return self.pipeline.project_initialized()

    def init_project(self):
        """Scaffold a new project in project_root (the "no project"
        screen's "Set up project here" button).
        """
        self.pipeline.init_project()

    def pdf_info(self, path):
        """{"name", "path", "version"} for an existing PDF at `path`, else
        None. `version` (the file's mtime) lets the preview tell a
        re-rendered PDF from the one it's already showing.
        """
        if not path or not Path(path).is_file():
            return None
        path = Path(path)
        return {"name": path.name, "path": str(path), "version": path.stat().st_mtime_ns // 1_000_000}

    def existing_pdf(self, filename):
        """pdf_info for the PDF `filename`'s current header would build
        to, if that PDF already exists on disk.
        """
        try:
            slug = self.pipeline.topic_slug(self.pipeline.yaml_path_for(filename))
        except PipelineError:
            return None
        return self.pdf_info(self.pipeline.pdf_dir / f"{slug}.pdf")

    def check_markdown_file(self, filename):
        if filename not in self.pipeline.list_markdown_files():
            raise PipelineError(f"{filename} not found.")

    def save(self, filename, header, markdown):
        """Write header form `header` and `markdown` to filename's yaml/md
        files, returning the stored header fields.
        """
        if not isinstance(header, dict):
            raise PipelineError("Expected a header object.")
        if not isinstance(markdown, str):
            raise PipelineError("Expected a string for 'markdown'.")
        fields = header_form.header_from_form(header)
        self.pipeline.write_header(filename, fields)
        self.pipeline.write_markdown_file(filename, markdown)
        return fields

    # --- Markdown files ---------------------------------------------------

    def list_files(self):
        return self.pipeline.list_markdown_files()

    def create_file(self, name):
        """Create a markdown file named after `name`, returning (the
        filename actually used, the new file list).
        """
        file = self.pipeline.create_markdown_file(name)
        return file, self.pipeline.list_markdown_files()

    def import_markdown(self, path):
        """Copy the markdown file at `path` (anywhere on the computer) into
        md/ as a new note, with a blank header. It's named after the
        original -- with "-2", "-3", ... added if that name is taken.
        Returns (the filename used, the new file list).
        """
        path = Path(path)
        try:
            # utf-8-sig: drop a byte-order mark, if an editor left one.
            with open(path, encoding="utf-8-sig", newline="") as f:
                text = f.read()
        except UnicodeDecodeError as err:
            raise PipelineError(f"{path.name} isn't a UTF-8 text file.") from err
        except OSError as err:
            raise PipelineError(f"Couldn't read {path.name}: {err}") from err

        name = self.pipeline.markdown_name_for(path.name)
        existing = set(self.pipeline.list_markdown_files())
        stem, number = name[: -len(".md")], 1
        while name in existing:
            number += 1
            name = f"{stem}-{number}.md"
        file = self.pipeline.create_markdown_file(name)
        self.pipeline.write_markdown_file(file, text)
        return file, self.pipeline.list_markdown_files()

    def export_tex(self, filename, header, markdown):
        """Save `header`/`markdown`, then return filename's notes as one
        LaTeX document: {"ok", "tex", "log", "name"} -- `name` being the
        file name to suggest (the PDF's own, with .tex).
        """
        self.check_markdown_file(filename)
        self.save(filename, header, markdown)
        tex, log = self.pipeline.export_tex(filename, self.build_dir)
        try:
            name = f"{self.pipeline.topic_slug(self.pipeline.yaml_path_for(filename))}.tex"
        except PipelineError:
            name = f"{Path(filename).stem}.tex"
        return {"ok": tex is not None, "tex": tex, "log": log, "name": name}

    def load_file(self, filename):
        self.check_markdown_file(filename)
        return {
            "name": filename,
            "header": header_form.form_from_header(self.pipeline.read_header(filename)),
            "markdown": self.pipeline.read_markdown_file(filename),
            "pdf": self.existing_pdf(filename),
        }

    def save_file(self, filename, header, markdown):
        """Autosave target: the window calls this whenever the header or
        markdown changes (debounced), so closing it between renders
        doesn't lose what was typed.
        """
        self.check_markdown_file(filename)
        try:
            self.save(filename, header, markdown)
        except OSError as err:
            raise PipelineError(f"Couldn't autosave {filename}: {err}") from err

    def delete_file(self, filename):
        """Delete `filename` and its header, returning the new file list."""
        self.pipeline.delete_markdown_file(filename)
        return self.pipeline.list_markdown_files()

    def render_file(self, filename, header, markdown):
        """Save `header`/`markdown`, then build filename's PDF. The content
        is exactly what's in the editor at the moment Render was clicked,
        so the build never runs against a stale save.

        Returns {"ok", "saved", "log", "pdf"}. Slow (it runs TeX): the
        window calls this off the GUI thread.
        """
        self.check_markdown_file(filename)
        try:
            fields = self.save(filename, header, markdown)
        except OSError as err:
            log = f"Render skipped: couldn't save changes to disk.\n{err}"
            return {"ok": False, "saved": False, "log": log, "pdf": None}

        missing = [name for name in ("topic", "date") if not fields[name].strip()]
        if missing:
            return {
                "ok": False,
                "saved": True,
                "log": f"Render skipped: {' and '.join(missing)} field(s) empty.\n"
                "Fill in the header before rendering, or the output PDF's name "
                "and header row will end up mostly blank.",
                "pdf": None,
            }

        success, log, pdf_path = self.pipeline.render(filename, self.build_dir)
        return {"ok": success, "saved": True, "log": log, "pdf": self.pdf_info(pdf_path)}

    def pdf_path(self, name):
        """The path of built PDF `name` in pdf/ (for "Download PDF"'s copy)."""
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".pdf"):
            raise PipelineError(f"Invalid name: {name}.")
        path = self.pipeline.pdf_dir / name
        if not path.is_file():
            raise PipelineError(f"{name} not found.")
        return path

    # --- Assets -------------------------------------------------------------

    def asset_listing(self, subdir, errors=()):
        """What's in folder assets/<subdir> after an operation, plus any
        per-file `errors` it ran into.
        """
        folders, files = self.pipeline.list_asset_dir(subdir)
        base = self.pipeline.resolve_asset_dir(subdir)
        return {
            "errors": list(errors),
            "dir": subdir,
            "folders": folders,
            "files": [
                {
                    "name": name,
                    "path": str(base / name),
                    "size": (base / name).stat().st_size,
                    "image": Path(name).suffix.lower() in IMAGE_SUFFIXES,
                }
                for name in files
            ],
            "folder_paths": self.pipeline.list_asset_folder_paths(),
            "all_files": self.pipeline.list_asset_files(),
        }

    def list_assets(self, subdir=""):
        return self.asset_listing(subdir)

    def add_assets(self, subdir, paths):
        """Copy the files at `paths` into assets/<subdir>. One that can't
        be copied is reported in the listing's "errors" without stopping
        the rest.
        """
        errors = []
        for path in paths:
            try:
                self.pipeline.save_asset(Path(path).name, Path(path).read_bytes(), subdir)
            except PipelineError as err:
                errors.append(str(err))
            except OSError as err:
                errors.append(f"Couldn't add {Path(path).name}: {err}")
        return self.asset_listing(subdir, errors)

    def create_asset_folder(self, subdir, name):
        self.pipeline.create_asset_folder(name, subdir)
        return self.asset_listing(subdir)

    def rename_asset_folder(self, subdir, name, new_name):
        self.pipeline.rename_asset_folder(name, new_name, subdir)
        return self.asset_listing(subdir)

    def delete_asset_folder(self, subdir, name):
        self.pipeline.delete_asset_folder(name, subdir)
        return self.asset_listing(subdir)

    def delete_asset(self, subdir, name):
        self.pipeline.delete_asset(name, subdir)
        return self.asset_listing(subdir)

    def move_assets(self, subdir, names, dest):
        errors = []
        for name in names:
            try:
                self.pipeline.move_asset(name, subdir, dest)
            except PipelineError as err:
                errors.append(str(err))
        return self.asset_listing(subdir, errors)
