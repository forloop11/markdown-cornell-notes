"""Thin wrapper around the Cornell notes CLI pipeline (see ../Makefile) for
the Streamlit app: header read/write, markdown file management, and
`make build` invocation.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
MD_DIR = REPO_ROOT / "md"
YAML_DIR = REPO_ROOT / "yaml"
PDF_DIR = REPO_ROOT / "pdf"
BUILDDIR = "build/app"

sys.path.insert(0, str(SCRIPTS_DIR))
from simple_yaml import parse_yaml  # noqa: E402  (needs SCRIPTS_DIR on sys.path first)

HEADER_FIELDS = ["topic", "date", "attendees", "time"]

HEADER_COMMENT = (
    "# Header details for the first \\cornellpage in settings/template.tex.\n"
    "# Run `python3 scripts/yaml_to_header.py` to regenerate build/cornell-header.tex, then\n"
    "# compile settings/template.tex with pdflatex as usual.\n"
)

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


class PipelineError(Exception):
    pass


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


def topic_slug(yaml_path):
    result = subprocess.run(
        [sys.executable, "scripts/topic_slug.py", str(yaml_path)],
        cwd=REPO_ROOT,
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
    """
    if yaml_path is None:
        yaml_path = yaml_path_for(md_filename)
    md_path = f"md/{md_filename}"
    proc = subprocess.run(
        [
            "make",
            "build",
            f"MD={md_path}",
            f"YAML={yaml_path.relative_to(REPO_ROOT)}",
            f"BUILDDIR={BUILDDIR}",
        ],
        cwd=REPO_ROOT,
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
