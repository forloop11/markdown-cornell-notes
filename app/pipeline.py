"""Thin wrapper around the Cornell notes CLI pipeline (see ../Makefile) for
the editor app: header read/write, markdown file management, and building
the PDF -- via `make build`, or (on Windows, which has no make or Unix
shell, and in the standalone builds) by running the same steps directly;
see Pipeline.render.

File, folder, and asset names passed in here come from what the user typed
or picked (see api.py), so every method that takes one checks it can't
escape its own directory (see _check_plain_name) rather than trusting the
caller.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The build scripts' own yaml parser, so the app reads headers exactly the
# way `make build` will.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from simple_yaml import parse_yaml  # noqa: E402  (needs scripts/ on sys.path first)

HEADER_FIELDS = ["topic", "date", "attendees", "time", "timezone", "location"]

HEADER_COMMENT = (
    "# Header details for the first \\cornellpage in settings/template.tex.\n"
    "# Run `python3 scripts/yaml_to_header.py` to regenerate build/cornell-header.tex, then\n"
    "# compile settings/template.tex with pdflatex as usual.\n"
)

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")

# The files `make init` copies into a fresh project: (source under
# repo_root, destination under project_root).
INIT_FILES = [
    ("md/notes-example.md", "md/notes.md"),
    ("yaml/notes-example.yaml", "yaml/notes.yaml"),
    ("settings/page.yaml", "settings/page.yaml"),
    ("assets/tux.jpg", "assets/tux.jpg"),
]
INIT_DIRS = ["md", "yaml", "settings", "pdf", "assets"]

# pdflatex log lines asking for another pass (cross-references, longtable
# column widths, hyperref's outlines via rerunfilecheck) -- what latexmk
# watches for when deciding to rerun.
RERUN_RE = re.compile(r"Rerun to get|Label\(s\) may have changed|Table widths have changed")
MAX_LATEX_PASSES = 4

# How settings/template.tex pulls in a generated fragment: \input{...},
# for most of them wrapped in \IfFileExists{...}{...}{} so the template
# also compiles on its own.
FRAGMENT_INPUT_RE = re.compile(
    r"\\IfFileExists\{\\cnBuildDir/(?P<name>[\w.-]+\.tex)\}\{\\input\{\\cnBuildDir/(?P=name)\}\}\{\}"
    r"|\\input\{\\cnBuildDir/(?P<name2>[\w.-]+\.tex)\}"
)

# The pdflatex auxiliary files `latexmk -c` would remove after a build.
LATEX_AUX_SUFFIXES = [".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"]

WINDOWS = sys.platform == "win32"


class PipelineError(Exception):
    """A user-facing error from this module (e.g. a name collision or an
    invalid path) -- the app shows its message as-is, unlike an unexpected
    exception.
    """


class RunResult:
    """A finished command: exit code and full output."""

    def __init__(self, code, stdout="", stderr=""):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr


def run(command, args, cwd, env):
    """Run a command to completion, returning (never raising on a non-zero
    exit) its exit code and full output. A missing executable comes back
    with code 127 and the error in stderr, like a shell would report it.
    """
    try:
        proc = subprocess.run(
            [str(command), *map(str, args)],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            # No console window flashing up per step on Windows.
            creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0,
        )
    except OSError as err:
        return RunResult(127, "", f"{err}\n")
    return RunResult(proc.returncode, proc.stdout, proc.stderr)


def _default_python():
    """The interpreter to run scripts/ with: this one -- except that
    pythonw.exe (which the Windows build starts the app with, so no console
    opens) has no usable stdout, so its console twin stands in.
    """
    exe = Path(sys.executable)
    if WINDOWS and exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return str(exe)


def _base_name(name):
    """The last non-empty, non-"." component of a slash-separated name."""
    parts = [p for p in name.split("/") if p and p != "."]
    return parts[-1] if parts else ""


def _stem_of(name):
    """_base_name minus its last ".suffix" (a leading dot, as in
    ".hidden", isn't a suffix).
    """
    base = _base_name(name)
    dot = base.rfind(".")
    return base[:dot] if 0 < dot < len(base) - 1 else base


def _slugify(value):
    """Collapse unsafe characters to "-" and strip leading/trailing "-"."""
    return _SAFE_STEM_RE.sub("-", value).strip("-")


def _check_plain_name(name):
    """Raise PipelineError unless `name` is a single path component (no
    "/" or "\\" separators, and not "", "." or "..") -- i.e. something
    that, joined onto a directory, can only name an entry directly inside
    it.
    """
    if (
        not isinstance(name, str)
        or name in ("", ".", "..")
        or "/" in name
        or "\\" in name
        or "\0" in name
    ):
        raise PipelineError(f"Invalid name: {name!r}.")


def _sanitize_name(name):
    """Derive a safe asset/folder name from `name`: drop any directory
    components (e.g. from "../../etc/passwd"), then collapse unsafe
    characters to "-" same as markdown filenames -- but keep the
    extension, since assets/folders (unlike notes) aren't all one fixed
    suffix.
    """
    safe = _slugify(_base_name(str(name)).strip())
    if not safe:
        raise PipelineError("Name can't be empty.")
    return safe


def _display_dir(subdir=""):
    """The user-facing "assets/..." path for `subdir`, for error messages."""
    return f"assets/{subdir}" if subdir else "assets"


def _walk(root):
    """Every entry under `root`, recursively, as (slash-joined relative
    path, is_dir) -- not following symlinked directories, so a link can't
    loop or lead outside.
    """
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel = Path(dirpath).relative_to(root)
        for name in dirnames:
            path = Path(dirpath) / name
            # os.walk lists a symlink to a directory under dirnames (without
            # descending into it); it's still a folder to everything here.
            out.append(((rel / name).as_posix(), path.is_dir()))
        for name in filenames:
            out.append(((rel / name).as_posix(), False))
    return out


class Pipeline:
    """repo_root is where the pipeline itself (scripts/, the Makefile)
    lives, which for an installed package is the read-only
    /usr/share/markdown-cornell-notes tree. project_root is the user's
    actual project -- the directory the app was launched from, matching
    `make app`/the installed CLI's "operate on CWD" model (see Makefile's
    MCN_ROOT). md/, yaml/, pdf/, assets/ are project data and live under
    project_root.

    `tools` says how to reach the build's helper programs: "python" is the
    interpreter to run scripts/ with, "path_dirs" are prepended to PATH
    (e.g. the standalone builds' bundled pandoc and TeX directories -- see
    main.py), and "direct_build" runs the build steps here instead of via
    `make` (always the case on Windows).
    """

    def __init__(self, project_root, repo_root=REPO_ROOT, tools=None):
        tools = tools or {}
        self.project_root = Path(os.path.abspath(project_root))
        self.repo_root = Path(repo_root)
        self.python = tools.get("python") or _default_python()
        self.path_dirs = [str(d) for d in tools.get("path_dirs", [])]
        direct = tools.get("direct_build")
        self.direct_build = (WINDOWS or os.environ.get("MCN_DIRECT_BUILD") == "1") if direct is None else direct
        self.scripts_dir = self.repo_root / "scripts"
        self.md_dir = self.project_root / "md"
        self.yaml_dir = self.project_root / "yaml"
        self.pdf_dir = self.project_root / "pdf"
        self.assets_dir = self.project_root / "assets"

    def project_initialized(self):
        """Whether project_root looks like a scaffolded project (see `make
        init`) -- md/ and yaml/ must exist before any read/write below is
        safe.
        """
        return self.md_dir.is_dir() and self.yaml_dir.is_dir()

    def init_project(self):
        """Scaffold a fresh project in project_root from the bundled
        defaults -- the same checks and files as the Makefile's `init`
        target.
        """
        if self.project_root.resolve() == self.repo_root.resolve():
            raise PipelineError("Already in the markdown-cornell-notes source tree; nothing to init.")
        for name in INIT_DIRS:
            if (self.project_root / name).exists():
                raise PipelineError(f"Refusing to init: '{name}' already exists in {self.project_root}.")
        for name in INIT_DIRS:
            (self.project_root / name).mkdir(parents=True)
        for source, dest in INIT_FILES:
            shutil.copyfile(self.repo_root / source, self.project_root / dest)

    def child_env(self):
        """The environment for helper programs: this process's, with
        path_dirs prepended to PATH. (Windows spells it "Path", and treats
        it case-insensitively -- reuse whichever key is there rather than
        adding a second one.) PYTHONUTF8 keeps Python's own I/O UTF-8
        regardless of the Windows code page.
        """
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        if self.path_dirs:
            key = next((k for k in env if k.upper() == "PATH"), "PATH")
            env[key] = os.pathsep.join([*self.path_dirs, *filter(None, [env.get(key)])])
        return env

    def run_script(self, script, args):
        """Run one of scripts/ with the configured Python, from project_root."""
        return run(self.python, [self.scripts_dir / script, *args], cwd=self.project_root, env=self.child_env())

    def yaml_path_for(self, md_filename):
        """The header yaml paired with a markdown file: md/<stem>.md <-> yaml/<stem>.yaml."""
        return self.yaml_dir / f"{_stem_of(md_filename)}.yaml"

    def read_header(self, md_filename):
        """md_filename's paired header, with every HEADER_FIELDS name (""
        if the yaml doesn't exist, or doesn't set that field).
        """
        path = self.yaml_path_for(md_filename)
        fields = parse_yaml(path) if path.is_file() else {}
        return {name: fields.get(name, "") for name in HEADER_FIELDS}

    def write_header(self, md_filename, fields):
        """Write `fields` to md_filename's paired header yaml, quoting and
        escaping each value.
        """
        lines = [HEADER_COMMENT.rstrip("\n"), ""]
        for name in HEADER_FIELDS:
            # Backslash first, then quote -- otherwise a value containing a
            # literal backslash would corrupt the quote-escaping below (and,
            # since simple_yaml.strip_quotes unescapes in the same order,
            # doing it any other way here would break the round-trip).
            value = (fields.get(name) or "").replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{name}: "{value}"')
        _write_text(self.yaml_path_for(md_filename), "\n".join(lines) + "\n")

    def list_markdown_files(self):
        """All *.md filenames directly inside md/, sorted."""
        return sorted(p.name for p in self.md_dir.iterdir() if p.name.endswith(".md") and p.is_file())

    def markdown_name_for(self, name):
        """The md/ filename `name` turns into: its stem with unsafe
        characters collapsed to "-", plus ".md".
        """
        stem = _slugify(_stem_of(str(name)).strip())
        if not stem:
            raise PipelineError("File name can't be empty.")
        return f"{stem}.md"

    def create_markdown_file(self, name):
        """Create a new, blank markdown file (and its paired, blank header
        yaml) named after the sanitized stem of `name`, returning the
        filename actually used.
        """
        filename = self.markdown_name_for(name)
        path = self.md_dir / filename
        if path.exists():
            raise PipelineError(f"{filename} already exists.")
        _write_text(path, "# New notes\n")
        self.write_header(filename, {field: "" for field in HEADER_FIELDS})
        return filename

    def rename_markdown_file(self, name, new_name):
        """Rename `name` (one of list_markdown_files()) and its paired
        header yaml after the sanitized stem of `new_name`, returning the
        filename actually used. PDFs already built keep their names (they
        come from the header, not from this one).
        """
        if name not in self.list_markdown_files():
            raise PipelineError(f"{name} not found.")
        filename = self.markdown_name_for(new_name)
        if filename == name:
            return name
        old_path, new_path = self.md_dir / name, self.md_dir / filename
        old_yaml, new_yaml = self.yaml_path_for(name), self.yaml_path_for(filename)
        # (samefile: a change of capitals only, where the file system
        # doesn't tell those apart, isn't a collision.)
        if new_path.exists() and not new_path.samefile(old_path):
            raise PipelineError(f"{filename} already exists.")
        if new_yaml.exists() and not (old_yaml.exists() and new_yaml.samefile(old_yaml)):
            raise PipelineError(f"yaml/{new_yaml.name} already exists.")
        old_path.rename(new_path)
        if old_yaml.exists():
            old_yaml.rename(new_yaml)
        return filename

    def delete_markdown_file(self, name):
        """Delete `name` (one of list_markdown_files()) and its paired
        header yaml. Refuses to delete the last remaining markdown file.
        """
        files = self.list_markdown_files()
        if name not in files:
            raise PipelineError(f"{name} not found.")
        if len(files) <= 1:
            raise PipelineError("Can't delete the last remaining markdown file.")
        (self.md_dir / name).unlink()
        self.yaml_path_for(name).unlink(missing_ok=True)

    def markdown_path(self, name):
        """md/<name>, for an existing markdown file `name`."""
        _check_plain_name(name)
        path = self.md_dir / name
        if not name.endswith(".md") or not path.is_file():
            raise PipelineError(f"{name} not found.")
        return path

    def read_markdown_file(self, name):
        # newline="": hand back the file's own line endings untouched.
        with open(self.markdown_path(name), encoding="utf-8", newline="") as f:
            return f.read()

    def write_markdown_file(self, name, content):
        """Overwrite md/<name> (which must already exist) with `content`."""
        _write_text(self.markdown_path(name), content)

    def list_asset_files(self):
        """All files under assets/, recursively, as paths relative to
        assets/ (e.g. "diagrams/flow.png") -- for the editor's link/image
        autocompletion and the Assets panel's file count.
        """
        if not self.assets_dir.is_dir():
            return []
        return sorted(rel for rel, _ in _walk(self.assets_dir) if (self.assets_dir / rel).is_file())

    def resolve_asset_dir(self, subdir=""):
        """Resolve a folder path within assets/, guarding against escaping
        it (e.g. a subdir of "../../etc", or a symlink pointing outside).
        """
        if not subdir:
            return self.assets_dir
        if not isinstance(subdir, str):
            raise PipelineError("Invalid folder path.")

        def inside(path, root):
            return path == root or root in path.parents

        resolved = Path(os.path.abspath(self.assets_dir / subdir))
        if not inside(resolved, self.assets_dir):
            raise PipelineError("Invalid folder path.")
        if resolved.exists() and not inside(resolved.resolve(), self.assets_dir.resolve()):
            raise PipelineError("Invalid folder path.")
        return resolved

    def list_asset_dir(self, subdir=""):
        """Folders and files directly inside assets/<subdir> (not
        recursive), as two sorted name lists.
        """
        base = self.resolve_asset_dir(subdir)
        if not base.is_dir():
            return [], []
        names = sorted(p.name for p in base.iterdir())
        return [n for n in names if (base / n).is_dir()], [n for n in names if (base / n).is_file()]

    def list_asset_folder_paths(self):
        """Every folder under assets/, recursively, as slash-joined paths
        ("" for assets/ itself) -- for the "move to folder" picker.
        """
        if not self.assets_dir.is_dir():
            return [""]
        return ["", *sorted(rel for rel, is_dir in _walk(self.assets_dir) if is_dir)]

    def save_asset(self, filename, data, subdir=""):
        """Write `data` (bytes) as a new file named after the sanitized
        form of `filename` inside assets/<subdir>, returning the name
        actually used.
        """
        safe_name = _sanitize_name(filename)
        path = self.resolve_asset_dir(subdir) / safe_name
        if path.exists():
            raise PipelineError(f"{safe_name} already exists in {_display_dir(subdir)}/.")
        path.write_bytes(data)
        return safe_name

    def delete_asset(self, name, subdir=""):
        _check_plain_name(name)
        path = self.resolve_asset_dir(subdir) / name
        if not path.is_file():
            raise PipelineError(f"{name} not found in {_display_dir(subdir)}/.")
        path.unlink()

    def rename_asset(self, old_name, new_name, subdir=""):
        """Rename the file assets/<subdir>/<old_name> to the sanitized form
        of `new_name`, returning the name actually used. Notes that link to
        it aren't touched.
        """
        _check_plain_name(old_name)
        base = self.resolve_asset_dir(subdir)
        old_path = base / old_name
        if not old_path.is_file():
            raise PipelineError(f"{old_name} not found in {_display_dir(subdir)}/.")
        safe_name = _sanitize_name(new_name)
        new_path = base / safe_name
        if new_path != old_path and new_path.exists() and not new_path.samefile(old_path):
            raise PipelineError(f"{safe_name} already exists in {_display_dir(subdir)}/.")
        old_path.rename(new_path)
        return safe_name

    def move_asset(self, name, src_subdir, dest_subdir):
        """Move assets/<src_subdir>/<name> into assets/<dest_subdir>/,
        keeping its name.
        """
        _check_plain_name(name)
        src = self.resolve_asset_dir(src_subdir) / name
        dest_base = self.resolve_asset_dir(dest_subdir)
        if not src.is_file():
            raise PipelineError(f"{name} not found in {_display_dir(src_subdir)}/.")
        if not dest_base.is_dir():
            raise PipelineError(f"{_display_dir(dest_subdir)}/ not found.")
        dest = dest_base / name
        if dest.exists():
            raise PipelineError(f"{name} already exists in {_display_dir(dest_subdir)}/.")
        src.rename(dest)

    def create_asset_folder(self, name, subdir=""):
        folder_name = _sanitize_name(name)
        path = self.resolve_asset_dir(subdir) / folder_name
        if path.exists():
            raise PipelineError(f"{folder_name} already exists in {_display_dir(subdir)}/.")
        path.mkdir(parents=True)
        return folder_name

    def rename_asset_folder(self, old_name, new_name, subdir=""):
        _check_plain_name(old_name)
        base = self.resolve_asset_dir(subdir)
        old_path = base / old_name
        if not old_path.is_dir():
            raise PipelineError(f"{old_name} not found in {_display_dir(subdir)}/.")
        safe_name = _sanitize_name(new_name)
        new_path = base / safe_name
        if new_path != old_path and new_path.exists():
            raise PipelineError(f"{safe_name} already exists in {_display_dir(subdir)}/.")
        old_path.rename(new_path)
        return safe_name

    def delete_asset_folder(self, name, subdir=""):
        _check_plain_name(name)
        path = self.resolve_asset_dir(subdir) / name
        if not path.is_dir():
            raise PipelineError(f"{name} not found in {_display_dir(subdir)}/.")
        shutil.rmtree(path)

    def topic_slug(self, yaml_path):
        """The output PDF's base filename (the latexmk jobname) for the
        header yaml at `yaml_path`. Runs scripts/topic_slug.py -- the same
        script the Makefile names the PDF with -- so the two can never
        disagree.
        """
        result = self.run_script("topic_slug.py", [yaml_path])
        if result.code != 0:
            raise PipelineError(result.stderr.strip() or "Failed to compute output filename.")
        return result.stdout.strip()

    def render(self, md_filename, builddir):
        """Build `md_filename`'s PDF, in scratch BUILDDIR `builddir` (one
        per app window, so it never collides with -- or goes stale against
        -- a manual `make build`/`make build-example` run from the CLI).

        Returns (success, log, pdf_path). pdf_path is set even on failure
        when it could still be resolved, so the caller can show the
        previous PDF.
        """
        yaml_path = self.yaml_path_for(md_filename)
        build = self.build_direct if self.direct_build else self.build_with_make
        result = build(md_filename, yaml_path, builddir)

        pdf_path = None
        try:
            candidate = self.pdf_dir / f"{self.topic_slug(yaml_path)}.pdf"
            if candidate.is_file():
                pdf_path = candidate
        except PipelineError:
            pass
        return result.code == 0, result.stdout + result.stderr, pdf_path

    def build_with_make(self, md_filename, yaml_path, builddir):
        """`make build`, against repo_root's Makefile (the library copy --
        read-only when installed) but with project_root as the CWD, so
        MD/YAML/BUILDDIR resolve against the user's project, the same as
        the `-f .../Makefile` (no `-C`) invocation the installed CLI uses.
        """
        return run(
            "make",
            [
                "-f",
                self.repo_root / "Makefile",
                "build",
                f"MD=md/{md_filename}",
                f"YAML={yaml_path.relative_to(self.project_root).as_posix()}",
                f"BUILDDIR={builddir}",
            ],
            cwd=self.project_root,
            env=self.child_env(),
        )

    def generate_fragments(self, md_filename, yaml_path, builddir):
        """The first half of a build: run the three scripts that turn the
        header yaml, the markdown, and settings/page.yaml into the .tex
        fragments settings/template.tex pulls in, written to `builddir`.
        Stops at the first failing script.
        """
        out = RunResult(0)

        def step(result):
            out.stdout += result.stdout
            out.stderr += result.stderr
            out.code = result.code
            return result.code == 0

        if not (self.project_root / "settings" / "page.yaml").is_file():
            return RunResult(1, "", "settings/page.yaml not found -- set up the project first.\n")
        (self.project_root / builddir).mkdir(parents=True, exist_ok=True)
        # The scripts get forward-slash paths relative to project_root
        # (their CWD).
        tex_build_dir = Path(builddir).as_posix()
        yaml_rel = yaml_path.relative_to(self.project_root).as_posix()

        def in_build(name):
            return f"{tex_build_dir}/{name}"

        step(self.run_script("yaml_to_header.py", [yaml_rel, in_build("cornell-header.tex")])) and step(
            self.run_script(
                "markdown_to_pages.py",
                [
                    f"md/{md_filename}",
                    in_build("cornell-content.tex"),
                    in_build("cornell-cue.tex"),
                    in_build("cornell-summary.tex"),
                ],
            )
        ) and step(self.run_script("yaml_to_settings.py", ["settings/page.yaml", in_build("cornell-page-settings.tex")]))
        return out

    def export_tex(self, md_filename, builddir):
        """`md_filename`'s notes as one self-contained LaTeX document:
        settings/template.tex with every generated fragment it would
        \\input written into it in place. Returns (tex, log) -- tex is
        None if generating the fragments failed, and log says why.

        The document still names images by their assets/... paths, so it
        compiles from the project folder.
        """
        result = self.generate_fragments(md_filename, self.yaml_path_for(md_filename), builddir)
        if result.code != 0:
            return None, result.stdout + result.stderr
        build_dir = self.project_root / builddir

        def fragment(match):
            path = build_dir / (match.group("name") or match.group("name2"))
            return path.read_text(encoding="utf-8").rstrip("\n") if path.is_file() else ""

        template = (self.repo_root / "settings" / "template.tex").read_text(encoding="utf-8")
        tex = FRAGMENT_INPUT_RE.sub(fragment, template)
        header = (
            f"% {md_filename}, exported from Markdown Cornell Notes as a single LaTeX file.\n"
            "% Images and linked files keep their assets/... paths, so compile it from\n"
            "% the project folder (the one holding assets/), e.g.: pdflatex <this file>\n\n"
        )
        return header + tex, result.stdout + result.stderr

    def build_direct(self, md_filename, yaml_path, builddir):
        """The Makefile's `build` target, step by step, for platforms
        without make (Windows) and the standalone builds: the same three
        scripts, then pdflatex -- rerun until its log stops asking for
        another pass, as latexmk would -- then latexmk -c's cleanup.
        Stops at the first failing step.
        """
        out = self.generate_fragments(md_filename, yaml_path, builddir)
        if out.code != 0:
            return out

        def step(result):
            out.stdout += result.stdout
            out.stderr += result.stderr
            out.code = result.code
            return result.code == 0

        build_dir = self.project_root / builddir
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        tex_build_dir = Path(builddir).as_posix()

        def in_build(name):
            return f"{tex_build_dir}/{name}"

        try:
            jobname = self.topic_slug(yaml_path)
        except PipelineError as err:
            return RunResult(1, out.stdout, f"{out.stderr}{err}\n")

        # A copy of the template inside the build directory, so pdflatex
        # gets a short relative path -- the installed template's own path
        # may hold spaces or backslashes (e.g. under C:\Program Files) that
        # TeX's \input doesn't take kindly to.
        shutil.copyfile(self.repo_root / "settings" / "template.tex", build_dir / "cornell-template.tex")
        # Same as the Makefile's -usepretex: \cnBuildDir tells the template
        # where the generated .tex fragments are.
        latex_args = [
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-jobname={jobname}",
            "-output-directory=pdf",
            f"\\def\\cnBuildDir{{{tex_build_dir}}}\\input{{{in_build('cornell-template.tex')}}}",
        ]
        log_file = self.pdf_dir / f"{jobname}.log"
        for _ in range(MAX_LATEX_PASSES):
            if not step(run("pdflatex", latex_args, cwd=self.project_root, env=self.child_env())):
                return out
            log = log_file.read_text(encoding="latin-1") if log_file.is_file() else ""
            if not RERUN_RE.search(log):
                break
        for suffix in LATEX_AUX_SUFFIXES:
            (self.pdf_dir / f"{jobname}{suffix}").unlink(missing_ok=True)
        return out


def _write_text(path, text):
    # newline="": write the text's own line endings, not the platform's.
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
