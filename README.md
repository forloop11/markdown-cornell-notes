# Markdown Cornell Notes

![screenshot](assets/README/screenshot.png)

---

![screenshot_2](assets/README/screenshot_2.png)

A Cornell-style meeting notes template for LaTeX. Each page has a header
(topic, date, attendees, time), a large notes panel with a cue column
beside it, and a summary band below both, all blank for handwriting on
a printout.

Header details, notes content, and the page layout itself aren't edited in
the `.tex` file directly — they're generated from YAML and Markdown files,
so day-to-day use is just editing `yaml/notes.yaml` / `md/notes.md` /
`settings/page.yaml` and running `make`. The yaml file is paired with the
markdown file by name: `md/<stem>.md` goes with `yaml/<stem>.yaml`.

![](assets/README/page-layout.drawio.png)

The page layout (notes panel, cue column, and summary band) follows the
Cornell Note-Taking System, developed by Walter Pauk at Cornell
University and first published in his book *How to Study in College*
(Houghton Mifflin, 1962). This LaTeX/Markdown build pipeline implementing
that layout was created by Todd Takala; it isn't affiliated with Cornell
University or the Pauk estate.

## Table of contents

- [Markdown Cornell Notes](#markdown-cornell-notes)
  - [Table of contents](#table-of-contents)
  - [Requirements](#requirements)
  - [Quick start](#quick-start)
  - [Documentation](#documentation)
  - [Other Makefile targets](#other-makefile-targets)
  - [License](#license)

## Requirements

- A TeX Live (or similar) install with `pdflatex` and `latexmk`, plus the
  `tikz`, `xcolor`, `geometry`, `hyperref`, `amssymb`, `longtable`, and
  `booktabs` packages
- Python 3 (standard library only, no pip packages required, for `make
  build` itself — the optional [Streamlit editor app](docs/streamlit-app.md)
  needs `pip install -r requirements.txt`)
- [pandoc](https://pandoc.org/), for converting `md/notes.md` to LaTeX

## Quick start

```sh
make build
```

This regenerates the header, content, and page settings from
`yaml/notes.yaml` / `md/notes.md` / `settings/page.yaml`, compiles
`settings/template.tex`, and cleans up pdflatex's intermediate files
afterward. The result lands in `pdf/`, named after `yaml/notes.yaml`'s
`topic` and `date` fields (e.g. `pdf/Weekly-Sync_2026-08-23.pdf`) — see
[Naming the output PDF](docs/editing-notes.md#naming-the-output-pdf).

To customize the header fields and notes content, see
[Editing notes](docs/editing-notes.md), or use the
[Streamlit editor app](docs/streamlit-app.md) for a browser UI over the
same files.

## Documentation

- **[Streamlit editor app](docs/streamlit-app.md)** — the browser UI: header
  form, assets manager, Markdown editor with a formatting toolbar and
  autocompletion, and live PDF preview.
- **[Editing notes](docs/editing-notes.md)** — the `yaml`/`md` file format,
  pagination, cue-column and summary-band directives, multi-topic
  documents, linking assets, and how the output PDF is named.
- **[Project structure](docs/project-structure.md)** — what lives in each
  directory and how the build scripts fit together.
- **[Installation](docs/installation.md)** — installing as a `.deb`, via
  Homebrew on macOS, or running with Docker, instead of using a git
  checkout directly.
- **[Customizing the layout](docs/customization.md)** — page geometry and
  proportions via `settings/page.yaml`.

## Other Makefile targets

- `make build-example` — builds `md/notes-example.md` / `yaml/notes-example.yaml`
  instead of `md/notes.md` / `yaml/notes.yaml`, using its own `build/example/`
  scratch directory so it never collides with (or goes stale against) a
  regular `make build`. Useful for regenerating the reference PDF that
  demonstrates this pipeline's Markdown syntax without touching your own
  notes.
- `make app` — runs the [Streamlit editor app](docs/streamlit-app.md).
- `make clean` — removes pdflatex's intermediate files, keeps the PDF.
- `make distclean` — also removes the generated `build/` files and the PDF.
- `make deb` — packages this project as a `.deb`; see
  [Installation](docs/installation.md#installing-as-a-system-package).
- `make init` — scaffolds a fresh `md/`, `yaml/`, `settings/page.yaml`,
  `pdf/`, and `assets/` (with the `tux.jpg` the example note embeds) in the
  current directory from the bundled defaults. Only needed when using the
  installed `.deb` (a git checkout already has these); refuses to run if
  any of them already exist.

## License

MIT — see [LICENSE](LICENSE).
