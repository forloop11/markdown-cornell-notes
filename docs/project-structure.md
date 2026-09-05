# Project structure

```
.
├── yaml/
│   └── notes.yaml        Header fields (source of truth). Paired with
│                         md/notes.md by filename stem -- see Editing notes
│                         (editing-notes.md).
├── md/
│   └── notes.md          Notes panel content, in Markdown (source of
│                         truth).
├── assets/             Images & other files md/notes.md links to (source of
                        truth).
├── docs/
│   └── page-layout.drawio   Editable diagram source for the README's
│                            layout image (assets/page-layout.drawio.png);
│                            edit in draw.io/diagrams.net and re-export the
│                            PNG by hand.
├── settings/
│   ├── template.tex      Template + \cornellpage / \cornellFlow macros;
│   │                     \input's the generated files below and compiles
│   │                     to a PDF.
│   └── page.yaml         Page geometry & layout proportions (source of
│                         truth).
├── scripts/
│   ├── simple_yaml.py         Shared minimal YAML parser used by the
│   │                          scripts below.
│   ├── yaml_to_header.py      yaml/notes.yaml -> build/cornell-header.tex
│   ├── markdown_to_pages.py   md/notes.md (+pandoc) -> build/cornell-
│   │                          content.tex, build/cornell-cue.tex,
│   │                          build/cornell-summary.tex
│   ├── yaml_to_settings.py    settings/page.yaml -> build/cornell-page-
│   │                          settings.tex
│   └── topic_slug.py          yaml/notes.yaml's topic+date -> output PDF's
│                              filename
├── build/              Generated .tex fragments (gitignored, rebuilt by
                        make).
├── pdf/                Output PDF (see Naming the output PDF in
                        editing-notes.md).
├── app/
│   ├── streamlit_app.py  The Streamlit editor app; see streamlit-app.md.
│   ├── pipeline.py       Header/markdown file I/O + `make build`
│   │                     invocation for the app.
│   └── components/
│       └── code_editor/      CodeMirror-based editor component
│                             (markdown/HTML/LaTeX highlighting + native
│                             browser spellcheck).
├── requirements.txt    Python deps for the app (`streamlit`); not needed for
│                       `make build`.
└── Makefile            `make build` / `make app` / `make clean` / `make
                        distclean`.
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
