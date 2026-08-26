# Cornell Notes

A Cornell-style meeting notes template for LaTeX. Each page has a header
(topic, date, attendees, time), a large notes panel with a cue column
beside it, and a summary band below both, all blank for handwriting on
a printout.

Header details, notes content, and the page layout itself aren't edited in
the `.tex` file directly — they're generated from YAML and Markdown files,
so day-to-day use is just editing `header.yaml` / `notes.md` /
`settings/page.yaml` and running `make`.

![](assets/page-layout.drawio.png)

The page layout (notes panel, cue column, and summary band) follows the
Cornell Note-Taking System, developed by Walter Pauk at Cornell
University and first published in his book *How to Study in College*
(Houghton Mifflin, 1962). This LaTeX/Markdown build pipeline implementing
that layout was created by Todd Takala; it isn't affiliated with Cornell
University or the Pauk estate.

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
afterward. The result lands in `notes/`, named after `header.yaml`'s
`topic` and `date` fields (e.g. `notes/Weekly-Sync_2026-08-23.pdf`) — see
[Naming the output PDF](#naming-the-output-pdf) below.

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
of root, so the output PDF and `build/` come out owned by you rather
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

### Cue-column text

A line of the form

```
^<page> <text>
```

e.g. `^1 This is my question for Cue`, adds `<text>` as a bullet point in
the cue column of that page number (the actual rendered PDF page,
matching the "Page N" printed in each page's header) instead of the main
notes panel — handy for questions or keywords next to the notes they
relate to. The directive line itself isn't printed. `<text>` goes through
the same Markdown/LaTeX pipeline as the main content, so it can use
inline formatting (`**bold**`, etc.); multiple entries targeting the same
page each become their own bullet, in document order.

### Summary-band text

A line of the form

```
^^<page> <text>
```

e.g. `^^1 This is my summary for page 1`, adds `<text>` as an item in an
ordered (numbered) list in that page's summary band — the strip at
the bottom of the page — instead of the main notes panel. The band is
split into two side-by-side columns: text starts in the left column,
word-wrapped to half the band's width, and if it's too long to fit, the
overflow continues at the top of the right column instead of running
past the band. Otherwise this behaves just like cue-column text: the
directive line isn't printed, and `<text>` goes through the same
Markdown/LaTeX pipeline as the main content.

The two directives are easy to tell apart even in shorthand: one caret
(`^1 ...`) is the cue column, two carets (`^^1 ...`) is the summary band.

`<page>` doesn't have to be a valid page number: anything below 1 (e.g.
`^0` or `^-3`) is clamped to page 1, and anything past the document's
actual last page (e.g. `^99` in a 3-page document) renders on that last
page instead — so a directive never silently vanishes just because the
page count changed or was miscounted.

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
resolves it relative to the output PDF's own location on disk, which is
`notes/` rather than the repo root; `scripts/markdown_to_pages.py`
rewrites each relative link with a `../` prefix so it still resolves
correctly (web URLs are left untouched). This also works with `make
docker`: the whole project directory, `assets/` included, is mounted
into the container at build time.

## Project structure

```
header.yaml         Header fields (source of truth).
notes.md            Notes panel content, in Markdown (source of truth).
assets/             Images & other files notes.md links to (source of truth).
docs/
  page-layout.drawio   Editable diagram source for the README's layout image
                        (assets/page-layout.drawio.png); edit in draw.io/diagrams.net
                        and re-export the PNG by hand.
settings/
  template.tex         Template + \cornellpage / \cornellFlow macros; \input's
                        the generated files below and compiles to a PDF.
  page.yaml            Page geometry & layout proportions (source of truth).
scripts/
  simple_yaml.py        Shared minimal YAML parser used by the scripts below.
  yaml_to_header.py      header.yaml        -> build/cornell-header.tex
  markdown_to_pages.py   notes.md (+pandoc) -> build/cornell-content.tex,
                                                build/cornell-cue.tex,
                                                build/cornell-summary.tex
  yaml_to_settings.py    settings/page.yaml -> build/cornell-page-settings.tex
  topic_slug.py          header.yaml's topic+date -> output PDF's filename
build/              Generated .tex fragments (gitignored, rebuilt by make).
notes/              Output PDF (see Naming the output PDF below).
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
python3 scripts/markdown_to_pages.py notes.md build/cornell-content.tex build/cornell-cue.tex build/cornell-summary.tex
python3 scripts/yaml_to_settings.py settings/page.yaml build/cornell-page-settings.tex
```

## Other Makefile targets

- `make build-example` — builds `notes-example.md` / `header-example.yaml`
  instead of `notes.md` / `header.yaml`, using its own `build/example/`
  scratch directory so it never collides with (or goes stale against) a
  regular `make build`. Useful for regenerating the reference PDF that
  demonstrates this pipeline's Markdown syntax without touching your own
  notes.
- `make docker` — runs the same build inside Docker; see [Docker](#docker) above.
- `make clean` — removes pdflatex's intermediate files, keeps the PDF.
- `make distclean` — also removes the generated `build/` files and the PDF.

## Customizing the layout

`settings/page.yaml` controls the page geometry and layout proportions —
no need to touch `settings/template.tex` itself:

```yaml
paper: letterpaper
margin: 0.25in

header_height: 0.12
cue_width: 0.25
summary_height: 0.18

padding: 0.12in
border_inset: 2pt
```

- **`paper`, `margin`** — passed straight to the LaTeX `geometry` package,
  so any value it accepts works (e.g. `paper: a4paper`, `margin: 20mm`).
- **`header_height`, `cue_width`, `summary_height`** — sizing for the
  header band, right-hand cue column, and the summary band at the bottom
  of the page, each as a plain decimal fraction of the drawable page
  height/width.
- **`padding`, `border_inset`** — inner text padding and the safety
  margin that keeps thick strokes inside the printable area, each a
  LaTeX length.

Edit the file and run `make build` (or `make docker`) again; every page
picks up the change automatically. Under the hood this generates
`build/cornell-page-settings.tex`, the same pattern as the header and
content files above.

## Naming the output PDF

The PDF is written to `notes/` and named after `header.yaml`'s `topic`
and `date` fields, not a fixed `cornell-notes.pdf`. `scripts/topic_slug.py`
slugifies each field — collapsing any run of characters that aren't safe
in a filename (spaces, punctuation, ...) to a single hyphen — and joins
them with an underscore, so:

```yaml
topic: Weekly Sync
date: 2026-08-23
```

produces `notes/Weekly-Sync_2026-08-23.pdf`. Change `topic`/`date` and
run `make build` again to rename the output; the previous PDF isn't
deleted automatically.

## License

MIT — see [LICENSE](LICENSE).
