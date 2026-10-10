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
│   ├── build_deb.sh           `make deb`: packages a .deb (see installation.md).
│   ├── build_windows.sh       `make windows`: the Windows installer, with
│   │                          Python/pandoc/TeX bundled (see installation.md).
│   ├── build_macos.sh         `make macos`: the Apple Silicon macOS app zip,
│   │                          bundled the same way.
│   ├── build_appimage.sh      `make appimage`: the x86_64 Linux AppImage,
│   │                          bundled the same way.
│   ├── bundle_common.sh       Shared by those three: pinned versions, the
│   │                          download cache, the TeX tree, staging.
│   └── topic_slug.py          yaml/notes.yaml's topic+date -> output PDF's
│                              filename
├── build/              Generated .tex fragments (gitignored, rebuilt by
                        make).
├── pdf/                Output PDF (see Naming the output PDF in
                        editing-notes.md).
├── app/                The Electron editor app; see editor-app.md.
│   ├── main.js           Main process: the window, IPC handlers, save dialog,
│   │                     right-click/spellcheck menu.
│   ├── preload.js        Exposes the main process's operations to the page
│   │                     as window.mcn.
│   ├── lib/
│   │   ├── api.js          Everything the page can ask for (files, render,
│   │   │                   assets), as plain functions main.js wires to IPC.
│   │   ├── pipeline.js     Header/markdown/asset file I/O, project setup,
│   │   │                   and builds (`make build`, or the same steps run
│   │   │                   directly on Windows).
│   │   └── header-form.js  Converts between the yaml header fields and the
│   │                       app's header form (date/time/timezone pickers).
│   ├── renderer/         The app's page: HTML, CSS, app.js, and editor.js
│   │                     (the built CodeMirror bundle -- markdown/HTML/LaTeX
│   │                     highlighting + native spellcheck).
│   ├── frontend_src/     Source for renderer/editor.js (`npm run
│   │                     build:editor`).
│   ├── test/             The app's tests (`node --test`, run by `make test`).
│   ├── build-resources/  The app icon (icon.svg, rendered to icon.png) for
│   │                     the Windows, macOS, and AppImage builds.
│   └── package.json      Electron + build tooling (`npm install` once, in a
│                         git checkout).
├── tests/              pytest tests for scripts/.
└── Makefile            `make build` / `make app` / `make test` / `make
                        clean` / `make distclean`.
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
