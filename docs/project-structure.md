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
│   ├── build_rpm.sh           `make rpm`: packages an RPM from
│   │                          markdown-cornell-notes.spec (at the top level,
│   │                          with .copr/Makefile for Fedora COPR builds).
│   ├── build_windows.sh       `make windows`: the Windows installer, with
│   │                          Python/Qt/pandoc/TeX bundled (see installation.md).
│   ├── build_macos.sh         `make macos`: the Apple Silicon macOS app zip,
│   │                          bundled the same way.
│   ├── build_appimage.sh      `make appimage`: the x86_64 Linux AppImage,
│   │                          bundled the same way.
│   ├── install_appimage.sh    `make install-appimage` / `uninstall-appimage`:
│   │                          puts the built AppImage in ~/Applications
│   │                          with a menu entry and icon.
│   ├── bundle_common.sh       Shared by those three: pinned versions, the
│   │                          download cache, the TeX tree, staging.
│   ├── bundle_prune_qt.py     Trims the bundled PySide6 to the Qt modules
│   │                          the app uses.
│   ├── macos_launcher.c       The macOS app's executable, which starts the
│   │                          bundled Python on app/main.py.
│   ├── macos_entitlements.plist  What the macOS app's programs may do
│   │                          under Apple's hardened runtime.
│   ├── macos_sign_scopes.py   Lists the programs in the .app for Developer
│   │                          ID signing (see build_macos.sh).
│   ├── make_icons.py          Regenerates the app icon's .ico and .icns.
│   ├── release.sh             The steps of a release: bump the version,
│   │                          build the packages with checksums, publish.
│   ├── make_tutorial_gif.py   Records the README's tutorial
│   │                          (assets/tutorial.gif) from the real app.
│   └── topic_slug.py          yaml/notes.yaml's topic+date -> output PDF's
│                              filename
├── build/              Generated .tex fragments (gitignored, rebuilt by
                        make).
├── pdf/                Output PDF (see Naming the output PDF in
                        editing-notes.md).
├── app/                The editor app (Python, PySide6/Qt); see editor-app.md.
│   ├── main.py           Entry point: starts Qt, finds the project (and, in
│   │                     a standalone build, the bundled tools).
│   ├── window.py         The window: app bar, Details form, panes, menus,
│   │                     autosave, and rendering.
│   ├── assets_explorer.py  The assets file explorer down the left side.
│   ├── webviews.py       The two Qt WebEngine panes: the markdown editor
│   │                     and the PDF preview.
│   ├── widgets.py        Small widgets the window is built from (cards,
│   │                     chips, the time and timezone fields).
│   ├── theme.py          Light/dark colors, style sheet, and icons.
│   ├── api.py            Everything the window can ask for (files, render,
│   │                     assets), as plain methods with no Qt in them.
│   ├── pipeline.py       Header/markdown/asset file I/O, project setup,
│   │                     and builds (`make build`, or the same steps run
│   │                     directly on Windows and in standalone builds).
│   ├── header_form.py    Converts between the yaml header fields and the
│   │                     app's header form (date/time/timezone fields).
│   ├── sync.py           Matches markdown lines with text in the PDF, for
│   │                     the editor <-> preview sync.
│   ├── web/              The two panes' pages. The preview: pdf.html,
│   │                     pdf.css, pdf_bridge.js, and pdfviewer.js (the
│   │                     built PDF.js bundle) with PDF.js's pdf_viewer.css.
│   │                     The editor: index.html, editor.css,
│   │                     bridge.js (its link to webviews.py), and editor.js
│   │                     (the built CodeMirror bundle -- markdown/HTML/LaTeX
│   │                     highlighting, toolbar, autocompletion).
│   ├── frontend_src/     Source for web/editor.js and web/pdfviewer.js
│   │                     (`npm run build`).
│   ├── build-resources/  The application-menu entry the .deb and RPM
│   │                     install; the app icon (icon.svg, rendered to icon.png, and
│   │                     from that to icon.ico/.icns by
│   │                     scripts/make_icons.py) and the style sheet's
│   │                     dropdown arrows.
│   ├── requirements.txt  What the app needs from pip (PySide6).
│   └── package.json      Build tooling for web/editor.js only (`npm
│                         install` once, to rebuild it).
├── snap/               snapcraft.yaml: the editor app as a snap (see
│                       installation.md).
├── tests/              pytest tests for scripts/ and app/ (`make test`).
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
