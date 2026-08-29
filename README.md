# Cornell Notes

![screenshot](assets/screenshot.png)

A Cornell-style meeting notes template for LaTeX. Each page has a header
(topic, date, attendees, time), a large notes panel with a cue column
beside it, and a summary band below both, all blank for handwriting on
a printout.

Header details, notes content, and the page layout itself aren't edited in
the `.tex` file directly — they're generated from YAML and Markdown files,
so day-to-day use is just editing `yaml/notes.yaml` / `md/notes.md` /
`settings/page.yaml` and running `make`. The yaml file is paired with the
markdown file by name: `md/<stem>.md` goes with `yaml/<stem>.yaml`.

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
- Python 3 (standard library only, no pip packages required, for `make
  build` itself — the optional [Streamlit editor app](#streamlit-editor-app)
  below needs `pip install -r requirements.txt`)
- [pandoc](https://pandoc.org/), for converting `md/notes.md` to LaTeX

Don't want to install any of that locally? Use the [Docker image](#docker)
below instead.

## Quick start

```sh
make build
```

This regenerates the header, content, and page settings from
`yaml/notes.yaml` / `md/notes.md` / `settings/page.yaml`, compiles
`settings/template.tex`, and cleans up pdflatex's intermediate files
afterward. The result lands in `pdf/`, named after `yaml/notes.yaml`'s
`topic` and `date` fields (e.g. `pdf/Weekly-Sync_2026-08-23.pdf`) — see
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

## Streamlit editor app

A browser UI for the whole pipeline above — edit the header fields and a
markdown file side by side with a rendered PDF, without touching the CLI.

```sh
pip install -r requirements.txt
make app
```

then open the URL `streamlit` prints (defaults to
[http://localhost:8501](http://localhost:8501)). Or, without installing
anything locally:

```sh
make docker-app
```

which builds the same Docker image as `make docker` and runs it with its
port published, `-p 8501:8501`.

The page has a header form (`topic`/`date`/`attendees`/`time`) at the top, a
dropdown to switch between the files in `md/` (with buttons to create or
delete one), and, on the right of that row, **Render** and **Download PDF**.
The header form is per markdown file — each `md/<stem>.md` has its own
paired `yaml/<stem>.yaml`, so switching files in the dropdown also switches
the header fields shown, and creating a file creates a blank paired yaml
alongside it (deleting a file removes its yaml too). Render saves both the
selected file's header and its markdown content to disk and runs `make
build` for you — the build log is shown in an expander so LaTeX/pandoc
errors surface in the UI instead of disappearing. Download PDF (disabled
until a PDF exists) downloads the current one under its actual output
filename. Below the file controls, an **Assets** expander (labeled with the
current file count) manages the `assets/` folder used for images and linked
documents (see [Images and linked documents](#images-and-linked-documents)
below): it lists each file with an image thumbnail (where applicable), a
copyable `assets/<name>` path to paste into your Markdown, and its size, plus
an uploader to add new files and a delete confirmation per file. Below that,
the markdown editor (left) and the resulting PDF (right) sit side by side,
matched in height so their tops and bottoms align; switching files preserves
each file's unsaved edits for the rest of the session, though only Render
writes them to disk.

The editor itself is [CodeMirror](https://codemirror.net/), with syntax
highlighting for Markdown, inline/raw HTML, and fenced ` ```html `/
` ```latex ` code blocks, and — the reason it's CodeMirror rather than a
more typical embedded code-editor widget — real support for the browser's
own spellcheck: misspelled words get the usual squiggly underline, and
right-click → "Add to dictionary" uses the browser's own per-profile
dictionary, so it's remembered on future visits with no app-side state at
all. Its JS is vendored (`app/components/code_editor/frontend/bundle.js`)
rather than loaded from a CDN, so the app works offline; if you edit
`app/components/code_editor/frontend_src/editor.js`, rebuild it with:

```sh
cd app/components/code_editor/frontend_src
npm install
npm run build
```

## Editing a page

- **`yaml/notes.yaml`** — the header fields (`topic`, `date`, `attendees`,
  `time`). Applied to every page automatically. Paired with its markdown
  file by name: `md/<stem>.md` goes with `yaml/<stem>.yaml`.
- **`md/notes.md`** — the notes panel content, written in Markdown.

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

> The `md/notes.md` shipped in this repo is currently a test file exercising
> the Markdown syntax this pipeline supports — formatting, lists, tables,
> code blocks, math, images, and so on — rather than real meeting
> content. Replace it with your own notes; until you do, it doubles as a
> working reference for what's supported (its HTML comments also note
> what isn't, and why).

### Pagination

The notes panel has a fixed height, so `md/notes.md` is measured and
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

`settings/template.tex` just does `\input{\cnBuildDir/cornell-content.tex}`,
which holds one `cornellFlow` environment per `md/notes.md` section.
(`\cnBuildDir` defaults to `build`, overridden per-invocation by the
Makefile's `BUILDDIR` — see `make build-example` below and the Streamlit
app's own scratch directory — so isolated builds actually compile their own
generated content instead of whatever's currently in the default `build/`.)
Every resulting page shares the same header from `yaml/notes.yaml` and
numbers itself automatically (top-right corner of the header box).

### Images and linked documents

Put images and any other files `md/notes.md` references in `assets/`, then
reference them with paths relative to the repo root:

```markdown
![](assets/diagram.png)

See the [reference notes](assets/reference-notes.txt) for background.
```

Images are auto-scaled to fit the notes panel width, so a full-resolution
screenshot won't overflow the page. Links are real, clickable PDF links
(via `hyperref`) — for a local file like the example above, a PDF viewer
resolves it relative to the output PDF's own location on disk, which is
`pdf/` rather than the repo root; `scripts/markdown_to_pages.py`
rewrites each relative link with a `../` prefix so it still resolves
correctly (web URLs are left untouched). This also works with `make
docker`: the whole project directory, `assets/` included, is mounted
into the container at build time.

## Project structure

```
yaml/
  notes.yaml           Header fields (source of truth). Paired with md/notes.md
                        by filename stem -- see Editing a page above.
md/
  notes.md             Notes panel content, in Markdown (source of truth).
assets/             Images & other files md/notes.md links to (source of truth).
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
  yaml_to_header.py      yaml/notes.yaml    -> build/cornell-header.tex
  markdown_to_pages.py   md/notes.md (+pandoc) -> build/cornell-content.tex,
                                                build/cornell-cue.tex,
                                                build/cornell-summary.tex
  yaml_to_settings.py    settings/page.yaml -> build/cornell-page-settings.tex
  topic_slug.py          yaml/notes.yaml's topic+date -> output PDF's filename
build/              Generated .tex fragments (gitignored, rebuilt by make).
pdf/                Output PDF (see Naming the output PDF below).
app/
  streamlit_app.py     The Streamlit editor app; see Streamlit editor app above.
  pipeline.py           Header/markdown file I/O + `make build` invocation for the app.
  components/
    code_editor/         CodeMirror-based editor component (markdown/HTML/LaTeX
                          highlighting + native browser spellcheck).
requirements.txt   Python deps for the app (`streamlit`); not needed for `make build`.
Makefile            `make build` / `make docker` / `make app` / `make docker-app` / `make clean` / `make distclean`.
docker/
  Dockerfile           Container image with the build toolchain (+ the app); see Docker above.
.dockerignore       Keeps .git and build/ out of the Docker build context.
```

Everything under `build/` is generated, not source — don't hand-edit those
files, and don't commit them (already gitignored). Each generator script
can also be run directly if you want to regenerate one file without the
others:

```sh
python3 scripts/yaml_to_header.py yaml/notes.yaml build/cornell-header.tex
python3 scripts/markdown_to_pages.py md/notes.md build/cornell-content.tex build/cornell-cue.tex build/cornell-summary.tex
python3 scripts/yaml_to_settings.py settings/page.yaml build/cornell-page-settings.tex
```

## Other Makefile targets

- `make build-example` — builds `md/notes-example.md` / `yaml/notes-example.yaml`
  instead of `md/notes.md` / `yaml/notes.yaml`, using its own `build/example/`
  scratch directory so it never collides with (or goes stale against) a
  regular `make build`. Useful for regenerating the reference PDF that
  demonstrates this pipeline's Markdown syntax without touching your own
  notes.
- `make docker` — runs the same build inside Docker; see [Docker](#docker) above.
- `make app` / `make docker-app` — runs the [Streamlit editor app](#streamlit-editor-app),
  locally or in Docker.
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

The PDF is written to `pdf/` and named after `yaml/notes.yaml`'s `topic`
and `date` fields, not a fixed `cornell-notes.pdf`. `scripts/topic_slug.py`
slugifies each field — collapsing any run of characters that aren't safe
in a filename (spaces, punctuation, ...) to a single hyphen — and joins
them with an underscore, so:

```yaml
topic: Weekly Sync
date: 2026-08-23
```

produces `pdf/Weekly-Sync_2026-08-23.pdf`. Change `topic`/`date` and
run `make build` again to rename the output; the previous PDF isn't
deleted automatically.

## License

MIT — see [LICENSE](LICENSE).
