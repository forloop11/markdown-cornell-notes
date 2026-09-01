"""Thin wrapper around the Cornell notes CLI pipeline (see ../Makefile) for
the Streamlit app: header read/write, markdown file management, and
`make build` invocation.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

# REPO_ROOT is where this file (and the rest of the pipeline -- scripts/,
# the Makefile) lives, which for an installed package is the read-only
# /usr/share/markdown-cornell-notes tree. PROJECT_ROOT is the user's actual
# project -- the CWD `streamlit run` was launched from, matching `make
# app`/the installed CLI's "operate on CWD" model (see Makefile's MCN_ROOT).
# md/, yaml/, pdf/, assets/ are project data and live under PROJECT_ROOT;
# scripts/ is library code and stays under REPO_ROOT.
REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = Path.cwd()
SCRIPTS_DIR = REPO_ROOT / "scripts"
MD_DIR = PROJECT_ROOT / "md"
YAML_DIR = PROJECT_ROOT / "yaml"
PDF_DIR = PROJECT_ROOT / "pdf"
ASSETS_DIR = PROJECT_ROOT / "assets"
BUILDDIR = "build/app"

sys.path.insert(0, str(SCRIPTS_DIR))
from simple_yaml import parse_yaml  # noqa: E402  (needs SCRIPTS_DIR on sys.path first)

HEADER_FIELDS = ["topic", "date", "attendees", "time", "timezone", "location"]

HEADER_COMMENT = (
    "# Header details for the first \\cornellpage in settings/template.tex.\n"
    "# Run `python3 scripts/yaml_to_header.py` to regenerate build/cornell-header.tex, then\n"
    "# compile settings/template.tex with pdflatex as usual.\n"
)

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


class PipelineError(Exception):
    pass


def project_initialized():
    """Whether PROJECT_ROOT looks like a scaffolded project (see `make
    init`) -- MD_DIR/YAML_DIR must exist before any read/write below is
    safe to call."""
    return MD_DIR.is_dir() and YAML_DIR.is_dir()


def yaml_path_for(md_filename):
    """The header yaml paired with a markdown file: md/<stem>.md <-> yaml/<stem>.yaml."""
    return YAML_DIR / f"{Path(md_filename).stem}.yaml"


def read_header(md_filename):
    path = yaml_path_for(md_filename)
    if not path.exists():
        return {name: "" for name in HEADER_FIELDS}
    fields = parse_yaml(path)
    return {name: fields.get(name, "") for name in HEADER_FIELDS}


def write_header(md_filename, fields):
    path = yaml_path_for(md_filename)
    lines = [HEADER_COMMENT.rstrip("\n"), ""]
    for name in HEADER_FIELDS:
        value = fields.get(name, "").replace('"', '\\"')
        lines.append(f'{name}: "{value}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def list_markdown_files():
    return sorted(p.name for p in MD_DIR.glob("*.md"))


def _sanitize_stem(name):
    stem = Path(name).stem.strip()
    stem = _SAFE_STEM_RE.sub("-", stem).strip("-")
    if not stem:
        raise PipelineError("File name can't be empty.")
    return stem


def create_markdown_file(name):
    filename = f"{_sanitize_stem(name)}.md"
    path = MD_DIR / filename
    if path.exists():
        raise PipelineError(f"{filename} already exists.")
    path.write_text("# New notes\n", encoding="utf-8")
    write_header(filename, {field: "" for field in HEADER_FIELDS})
    return filename


def delete_markdown_file(name):
    files = list_markdown_files()
    if name not in files:
        raise PipelineError(f"{name} not found.")
    if len(files) <= 1:
        raise PipelineError("Can't delete the last remaining markdown file.")
    (MD_DIR / name).unlink()
    yaml_path_for(name).unlink(missing_ok=True)


def read_markdown_file(name):
    return (MD_DIR / name).read_text(encoding="utf-8")


def write_markdown_file(name, content):
    (MD_DIR / name).write_text(content, encoding="utf-8")


def list_asset_files():
    """All files under assets/, recursively, as paths relative to assets/
    (e.g. "diagrams/flow.png") -- used for the editor's link/image
    autocompletion and the Assets panel's file count.
    """
    return sorted(str(p.relative_to(ASSETS_DIR)) for p in ASSETS_DIR.rglob("*") if p.is_file())


def _resolve_asset_dir(subdir=""):
    """Resolve a folder path within assets/, guarding against escaping it
    (e.g. a subdir of "../../etc")."""
    if not subdir:
        return ASSETS_DIR
    path = (ASSETS_DIR / subdir).resolve()
    if path != ASSETS_DIR and ASSETS_DIR not in path.parents:
        raise PipelineError("Invalid folder path.")
    return path


def _asset_display_dir(subdir=""):
    return f"assets/{subdir}" if subdir else "assets"


def list_asset_dir(subdir=""):
    """Folders and files directly inside assets/<subdir> (not recursive), as
    two sorted name lists."""
    base = _resolve_asset_dir(subdir)
    if not base.exists():
        return [], []
    folders = sorted(p.name for p in base.iterdir() if p.is_dir())
    files = sorted(p.name for p in base.iterdir() if p.is_file())
    return folders, files


def list_asset_folder_paths():
    """All folder paths under assets/, recursively, as slash-joined paths
    relative to assets/ ("" for assets/ itself) -- used to populate a
    "move to folder" picker."""
    paths = sorted(str(p.relative_to(ASSETS_DIR)) for p in ASSETS_DIR.rglob("*") if p.is_dir())
    return [""] + paths


def _sanitize_name(name):
    # Path(name).name drops any directory components (e.g. from "../../etc/passwd"
    # or a browser sending a full path), then unsafe characters collapse to "-"
    # same as markdown filenames -- but the extension (if any) is kept, since
    # assets/folders (unlike notes/header files) aren't all forced into one
    # fixed suffix.
    name = _SAFE_STEM_RE.sub("-", Path(name).name.strip()).strip("-")
    if not name:
        raise PipelineError("Name can't be empty.")
    return name


def save_asset(filename, data, subdir=""):
    safe_name = _sanitize_name(filename)
    base = _resolve_asset_dir(subdir)
    path = base / safe_name
    if path.exists():
        raise PipelineError(f"{safe_name} already exists in {_asset_display_dir(subdir)}/.")
    path.write_bytes(data)
    return safe_name


def delete_asset(name, subdir=""):
    base = _resolve_asset_dir(subdir)
    path = base / name
    if not path.exists() or not path.is_file():
        raise PipelineError(f"{name} not found in {_asset_display_dir(subdir)}/.")
    path.unlink()


def move_asset(name, src_subdir, dest_subdir):
    src_base = _resolve_asset_dir(src_subdir)
    dest_base = _resolve_asset_dir(dest_subdir)
    src_path = src_base / name
    if not src_path.is_file():
        raise PipelineError(f"{name} not found in {_asset_display_dir(src_subdir)}/.")
    if not dest_base.is_dir():
        raise PipelineError(f"{_asset_display_dir(dest_subdir)}/ not found.")
    dest_path = dest_base / name
    if dest_path.exists():
        raise PipelineError(f"{name} already exists in {_asset_display_dir(dest_subdir)}/.")
    src_path.rename(dest_path)


def create_asset_folder(name, subdir=""):
    folder_name = _sanitize_name(name)
    base = _resolve_asset_dir(subdir)
    path = base / folder_name
    if path.exists():
        raise PipelineError(f"{folder_name} already exists in {_asset_display_dir(subdir)}/.")
    path.mkdir(parents=True)
    return folder_name


def rename_asset_folder(old_name, new_name, subdir=""):
    base = _resolve_asset_dir(subdir)
    old_path = base / old_name
    if not old_path.is_dir():
        raise PipelineError(f"{old_name} not found in {_asset_display_dir(subdir)}/.")
    new_name = _sanitize_name(new_name)
    new_path = base / new_name
    if new_path != old_path and new_path.exists():
        raise PipelineError(f"{new_name} already exists in {_asset_display_dir(subdir)}/.")
    old_path.rename(new_path)
    return new_name


def delete_asset_folder(name, subdir=""):
    base = _resolve_asset_dir(subdir)
    path = base / name
    if not path.is_dir():
        raise PipelineError(f"{name} not found in {_asset_display_dir(subdir)}/.")
    shutil.rmtree(path)


def topic_slug(yaml_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "topic_slug.py"), str(yaml_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PipelineError(result.stderr.strip() or "Failed to compute output filename.")
    return result.stdout.strip()


def render(md_filename, yaml_path=None):
    """Run `make build` for the given markdown file, using a scratch
    BUILDDIR dedicated to the app so it never collides with (or goes stale
    against) a manual `make build`/`make build-example` run from the CLI.

    Returns (success, log, pdf_path). pdf_path is set even on failure when
    it could still be resolved, so the caller can show the previous PDF.

    Runs `make` against REPO_ROOT/Makefile (the library copy -- read-only
    when installed) but with PROJECT_ROOT as the CWD, so MD/YAML/BUILDDIR
    below resolve against the user's project, the same as the `-f
    .../Makefile` (no `-C`) invocation the installed CLI uses.
    """
    if yaml_path is None:
        yaml_path = yaml_path_for(md_filename)
    md_path = f"md/{md_filename}"
    proc = subprocess.run(
        [
            "make",
            "-f", str(REPO_ROOT / "Makefile"),
            "build",
            f"MD={md_path}",
            f"YAML={yaml_path.relative_to(PROJECT_ROOT)}",
            f"BUILDDIR={BUILDDIR}",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    log = proc.stdout + proc.stderr
    success = proc.returncode == 0

    pdf_path = None
    try:
        slug = topic_slug(yaml_path)
        candidate = PDF_DIR / f"{slug}.pdf"
        if candidate.exists():
            pdf_path = candidate
    except PipelineError:
        pass

    return success, log, pdf_path
