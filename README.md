# Cornell Notes

A Cornell-style meeting notes template for LaTeX. Each page has a header
(topic, date, attendees, time, project), a large notes panel with a ruled
cue column beside it, and a ruled footer, all for handwriting on a
printout.

Header details and notes content aren't edited in the `.tex` file directly —
they're generated from a YAML file and a Markdown file, so day-to-day use is
just editing `meeting.yaml` / `notes.md` and running `make`.

## Requirements

- A TeX Live (or similar) install with `pdflatex` and `latexmk`, plus the
  `tikz`, `xcolor`, and `geometry` packages
- Python 3 (standard library only, no pip packages required)
- [pandoc](https://pandoc.org/), for converting `notes.md` to LaTeX

Don't want to install any of that locally? Use the [Docker image](#docker)
below instead.

## Quick start

```sh
make build
```

This regenerates the header and content from `meeting.yaml` / `notes.md`,
compiles `cornell-notes.tex`, and cleans up pdflatex's intermediate files
afterward. The result is `cornell-notes.pdf`.

## Docker

The `Dockerfile` packages just the pieces this project's build actually
uses (not a full `texlive-full` install, which runs several GB) — around
1GB total, mostly `pandoc` and the TeX Live packages themselves.

```sh
make docker
```

which is equivalent to:

```sh
docker build -t cornell-notes .
docker run --rm -v "$(pwd)":/workspace -u "$(id -u):$(id -g)" cornell-notes
```

The `-u "$(id -u):$(id -g)"` runs the container as your own user instead
of root, so `cornell-notes.pdf` and `build/` come out owned by you rather
than root. The image's entrypoint is `make`, so you can run any target,
e.g. `... cornell-notes clean`.

## Editing a page

- **`meeting.yaml`** — the header fields (`topic`, `date`, `attendees`,
  `time`, `project`). Applied to every page automatically.
- **`notes.md`** — the notes panel content, written in Markdown.

```yaml
topic: Weekly Sync
date: 2026-08-23
attendees: Alice, Bob, Priya
time: "10:00--10:30, Zoom"
project: "Project Atlas"
```

```markdown
**Agenda**

- Status update on milestone 2
- Blockers from last sprint
- Next steps
```

Run `make build` again and both files flow through to the PDF.

### Pagination

The notes panel has a fixed height, so `notes.md` is measured and
automatically split across as many pages as it needs — you don't have to
plan page breaks by hand. If you want to force a break at a specific point
anyway (e.g. to start a new topic on its own page), put a line containing
only

```
<!-- pagebreak -->
```

between two sections.

### Multiple topics per document

`cornell-notes.tex` just does `\input{build/cornell-content.tex}`, which
holds one `\cornellFlow{...}` call per `notes.md` section. Every resulting
page shares the same header from `meeting.yaml` and numbers itself
automatically (top-right corner of the header box).

## Project structure

```
cornell-notes.tex   Template + \cornellpage / \cornellFlow macros; \input's
                     the generated files below and compiles to a PDF.
meeting.yaml        Header fields (source of truth).
notes.md            Notes panel content, in Markdown (source of truth).
scripts/
  yaml_to_header.py    meeting.yaml       -> build/cornell-header.tex
  markdown_to_pages.py notes.md (+pandoc) -> build/cornell-content.tex
build/              Generated .tex fragments (gitignored, rebuilt by make).
Makefile            `make build` / `make docker` / `make clean` / `make distclean`.
Dockerfile          Container image with the build toolchain; see Docker above.
.dockerignore       Keeps .git and build/ out of the Docker build context.
```

`build/cornell-header.tex` and `build/cornell-content.tex` are generated,
not source — don't hand-edit them, and don't commit them (already
gitignored). `scripts/yaml_to_header.py` and `scripts/markdown_to_pages.py`
can also be run directly if you want to regenerate one without the other:

```sh
python3 scripts/yaml_to_header.py meeting.yaml build/cornell-header.tex
python3 scripts/markdown_to_pages.py notes.md build/cornell-content.tex
```

## Other Makefile targets

- `make docker` — runs the same build inside Docker; see [Docker](#docker) above.
- `make clean` — removes pdflatex's intermediate files, keeps the PDF.
- `make distclean` — also removes the generated `build/` files and the PDF.

## Customizing the layout

`cornell-notes.tex` has a "TEMPLATE CONFIGURATION" block near the top with
the adjustable knobs: header/footer band heights, ruled-line spacing,
column widths, and padding, all expressed as fractions of the page so they
scale with paper size and margins.

## License

MIT — see [LICENSE](LICENSE).
