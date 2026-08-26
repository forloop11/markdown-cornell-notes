# Cornell Notes

A Cornell-style meeting notes template for LaTeX. Each page has a header
(topic, date, attendees, time), a large notes panel with a ruled cue
column beside it, and a ruled footer, all for handwriting on a printout.

Header details, notes content, and the page layout itself aren't edited in
the `.tex` file directly — they're generated from YAML and Markdown files,
so day-to-day use is just editing `header.yaml` / `notes.md` /
`settings/page.yaml` and running `make`.

![](assets/page-layout.drawio.png)

## Requirements

- A TeX Live (or similar) install with `pdflatex` and `latexmk`, plus the
  `tikz`, `xcolor`, `geometry`, `hyperref`, `amssymb`, `longtable`, and
  `booktabs` packages
- Python 3 (standard library only, no pip packages required)
- [pandoc](https://pandoc.org/), for converting `notes.md` to LaTeX

Don't want to install any of that locally? Use the [Docker image](#docker)
below instead.

## Quick start

```sh
make build
```

This regenerates the header, content, and page settings from
`header.yaml` / `notes.md` / `settings/page.yaml`, compiles
`settings/template.tex`, and cleans up pdflatex's intermediate files
afterward. The result is `cornell-notes.pdf`.

## Docker

The `docker/Dockerfile` packages just the pieces this project's build
actually uses (not a full `texlive-full` install, which runs several GB)
— around 1GB total, mostly `pandoc` and the TeX Live packages themselves.

```sh
make docker
```

which is equivalent to:

```sh
docker build -t cornell-notes -f docker/Dockerfile .
docker run --rm -v "$(pwd)":/workspace -u "$(id -u):$(id -g)" cornell-notes
```

The `-u "$(id -u):$(id -g)"` runs the container as your own user instead
of root, so `cornell-notes.pdf` and `build/` come out owned by you rather
than root. The image's entrypoint is `make`, so you can run any target,
e.g. `... cornell-notes clean`.

## Editing a page

- **`header.yaml`** — the header fields (`topic`, `date`, `attendees`,
  `time`). Applied to every page automatically.
- **`notes.md`** — the notes panel content, written in Markdown.

```yaml
topic: Weekly Sync
date: 2026-08-23
attendees: Alice, Bob, Priya
time: "10:00--10:30, Zoom"
```

```markdown
**Agenda**

- Status update on milestone 2
- Blockers from last sprint
- Next steps
```

Run `make build` again and both files flow through to the PDF.

> The `notes.md` shipped in this repo is currently a test file exercising
> the Markdown syntax this pipeline supports — formatting, lists, tables,
> code blocks, math, images, and so on — rather than real meeting
> content. Replace it with your own notes; until you do, it doubles as a
> working reference for what's supported (its HTML comments also note
> what isn't, and why).

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

`settings/template.tex` just does `\input{build/cornell-content.tex}`, which
holds one `cornellFlow` environment per `notes.md` section. Every
resulting page shares the same header from `header.yaml` and numbers
itself automatically (top-right corner of the header box).

### Images and linked documents

Put images and any other files `notes.md` references in `assets/`, then
reference them with paths relative to the repo root:

```markdown
![](assets/diagram.png)

See the [reference notes](assets/reference-notes.txt) for background.
```

Images are auto-scaled to fit the notes panel width, so a full-resolution
screenshot won't overflow the page. Links are real, clickable PDF links
(via `hyperref`) — for a local file like the example above, a PDF viewer
resolves it relative to `cornell-notes.pdf`'s own location on disk. This
also works with `make docker`: the whole project directory, `assets/`
included, is mounted into the container at build time.

## Project structure

```
header.yaml         Header fields (source of truth).
notes.md            Notes panel content, in Markdown (source of truth).
assets/             Images & other files notes.md links to (source of truth).
settings/
  template.tex         Template + \cornellpage / \cornellFlow macros; \input's
                        the generated files below and compiles to a PDF.
  page.yaml            Page geometry & layout proportions (source of truth).
scripts/
  simple_yaml.py        Shared minimal YAML parser used by the three below.
  yaml_to_header.py      header.yaml        -> build/cornell-header.tex
  markdown_to_pages.py   notes.md (+pandoc) -> build/cornell-content.tex
  yaml_to_settings.py    settings/page.yaml -> build/cornell-page-settings.tex
build/              Generated .tex fragments (gitignored, rebuilt by make).
Makefile            `make build` / `make docker` / `make clean` / `make distclean`.
docker/
  Dockerfile           Container image with the build toolchain; see Docker above.
.dockerignore       Keeps .git and build/ out of the Docker build context.
```

Everything under `build/` is generated, not source — don't hand-edit those
files, and don't commit them (already gitignored). Each generator script
can also be run directly if you want to regenerate one file without the
others:

```sh
python3 scripts/yaml_to_header.py header.yaml build/cornell-header.tex
python3 scripts/markdown_to_pages.py notes.md build/cornell-content.tex
python3 scripts/yaml_to_settings.py settings/page.yaml build/cornell-page-settings.tex
```

## Other Makefile targets

- `make docker` — runs the same build inside Docker; see [Docker](#docker) above.
- `make clean` — removes pdflatex's intermediate files, keeps the PDF.
- `make distclean` — also removes the generated `build/` files and the PDF.

## Customizing the layout

`settings/page.yaml` controls the page geometry and layout proportions —
no need to touch `settings/template.tex` itself:

```yaml
paper: letterpaper
margin: 0.5in

header_height: 0.12
footer_height: 0.18
cue_width: 0.25

rule_spacing: 0.30in
padding: 0.12in
border_inset: 2pt
```

- **`paper`, `margin`** — passed straight to the LaTeX `geometry` package,
  so any value it accepts works (e.g. `paper: a4paper`, `margin: 20mm`).
- **`header_height`, `footer_height`, `cue_width`** — sizing for the
  header band, footer band, and right-hand ruled cue column, each as a
  plain decimal fraction of the drawable page height/width.
- **`rule_spacing`, `padding`, `border_inset`** — ruled-line spacing,
  inner text padding, and the safety margin that keeps thick strokes
  inside the printable area, each a LaTeX length.

Edit the file and run `make build` (or `make docker`) again; every page
picks up the change automatically. Under the hood this generates
`build/cornell-page-settings.tex`, the same pattern as the header and
content files above.

## License

MIT — see [LICENSE](LICENSE).
