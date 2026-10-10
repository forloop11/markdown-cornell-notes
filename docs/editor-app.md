# Editor app

A desktop app for the whole pipeline described in the [main README](../README.md)
— edit the header fields and a markdown file side by side with a rendered
PDF, without touching the CLI. It's a Python app (`app/`) built on
[Qt](https://www.qt.io/) through [PySide6](https://doc.qt.io/qtforpython-6/),
working on the same `md/`, `yaml/`, `pdf/`, and `assets/` files the CLI
uses, in whichever project directory you start it from.

It needs PySide6 (version 6.8 or later, with Qt WebEngine) on top of the
usual `make build` requirements. From a git checkout, install it once into
a virtual environment in `app/.venv` — where `make app` looks first — then
start the app from the repo root (which is itself a project):

```sh
python3 -m venv app/.venv
app/.venv/bin/pip install -r app/requirements.txt
make app
```

Without an `app/.venv`, `make app` runs with plain `python3`, for a
PySide6 installed system-wide; `make app APP_PYTHON=/path/to/python` names
another interpreter. From an installed `.deb`, whose `app/` is read-only,
that's how to run it: `markdown-cornell-notes app` in a project directory
uses the distribution's PySide6 packages (the `.deb` recommends them — on
Debian 13, `python3-pyside6.qtwidgets`, `.qtsvg`, `.qtwebchannel`, and
`.qtwebenginewidgets`), or pass `APP_PYTHON=` to point at a virtual
environment that has PySide6.

Standalone builds — the
[Windows installer](installation.md#installing-on-windows), the
[macOS app](installation.md#installing-the-macos-app-apple-silicon) for
Apple Silicon, and the
[Linux AppImage](installation.md#running-the-linux-appimage) — bundle
Python, Qt, pandoc, and TeX instead, and keep their project in
`Documents/Cornell Notes` rather than a directory you start them from.

The window shows the project folder in its title bar. **File > Open
Project Folder…** (Ctrl+O) switches to a different folder, and **File >
Show Project Folder** opens the current one in your file manager. If the
folder isn't a project yet (no `md/` and `yaml/`), the app says so and
offers to set one up there — the same files `make init` creates — or to
open another folder. Closing the window ends the app; anything typed since
the last autosave is saved first.

**Linux sandbox note:** the editor and PDF preview panes are drawn by Qt
WebEngine, which is built on Chromium and sandboxes it. On distributions
that restrict unprivileged user namespaces (Ubuntu 24.04 and later, via
AppArmor), it can refuse to start with an error about that sandbox. Either
allow it the usual way for your distribution, or start the app without
Chromium's sandbox:

```sh
make app APP_FLAGS=--no-sandbox
```

The app only ever loads its own bundled page and your project's local
files, but the sandbox is still a useful safety net — prefer fixing the
OS-level restriction where you can.

Everything else in the window — the menus, app bar, assets explorer, and
Details form — is native Qt widgets, following the desktop's light or dark
setting. **View > Appearance** switches to **Light** or **Dark** regardless
of the desktop (or back to **System**), and the app remembers the choice.
The editor pane keeps its own dark theme in every mode.

Along the top, an app bar stays pinned while you scroll. On the left are
the dropdown to switch between the files in `md/` and **+** (new file) /
trash (delete file) buttons; on the right, a status area,
**Download PDF**, and **Render**. The status area shows a small
"Saved"/"Saving…" autosave indicator, a "Preview out of date" chip (see
below), and — once you've clicked Render — a success/failure chip. On
failure a **Build log** expander (the raw `make build` output) opens under
the app bar so you can see what went wrong. When the window is too narrow
for all of it on one row, the status area and buttons move to a second.

Down the left side is the **assets explorer**: the project's `assets/`
folder as a tree, for managing the images and documents your notes link to
(see [Images and linked documents](editing-notes.md#images-and-linked-documents));
its heading shows how many files there are. The hamburger button at the
left end of the app bar collapses and expands it, as does **View > Assets
Explorer** (Ctrl+B); the app remembers which. In it:

- The two buttons at its top make a **new folder** or **add files**, in
  the selected folder (or the folder holding the selected file, or
  `assets/` itself when nothing is selected).
- **Drag** files from your file manager onto the tree, or onto a folder in
  it, to copy them in; drag files within the tree to move them between
  folders.
- **Double-click** a file to copy a Markdown link to it, ready to paste
  into the editor: `![flow](assets/diagrams/flow.png)` for an image (which
  embeds it), `[handout](assets/handout.pdf)` for anything else. The link
  is relative to the project, as the build expects. Ctrl+C on the selected
  file (or files — one link per line) copies the same.
- **Right-click** for Copy Markdown Link, Copy Path (just
  `assets/diagrams/flow.png`), Rename (folders), Delete (with a
  confirmation; several selected items at once works too), New Folder, Add
  Files, and Show in File Manager.

Names are tidied the same way as everywhere else in the app (spaces and
other unsafe characters become `-`), and changes made to `assets/` outside
the app show up in the tree on their own.

To the right of the explorer, below the app bar, is a collapsible **Details** section holding the header
fields: Topic, Date, and start/end times on the first row; Location,
a searchable IANA timezone field (type any part of a zone's name to filter,
then pick one), and Attendees on the second. Start and End each have a
time picker: the clock button at the field's right edge (or the Down key)
opens a panel with a column of hours and a column of minutes in steps of
five, plus **Now** and **Clear**. A time can also be typed as `HH:MM` —
any minute, not just the fives — or left blank; text that isn't a time
(or, for Timezone, isn't a zone) snaps back to the last valid value. Collapsed, it shows a one-line recap (topic, date,
time, location) next to its title. `date` is a calendar date picker
(defaulting to today for an entry that doesn't have one yet), still stored in
`yaml/<stem>.yaml` as a plain `YYYY-MM-DD` string, same as editing it by
hand. The start/end/timezone group composes into the `time` field's usual
`"HH:MM--HH:MM"` string, now with the zone's abbreviation appended (e.g.
`"10:00--10:30 PDT"`); the dropdown's actual IANA zone name (e.g.
`"America/Los_Angeles"`) is stored separately in the `timezone` field, so
reopening a file restores the exact zone in the picker rather than just
the abbreviation. The Location field is stored directly in its own
`location` field rather than folded into `time` — `settings/template.tex`
recombines the two (as `"10:00--10:30 PDT, Zoom"`) when it typesets the
Time row, and `scripts/topic_slug.py` includes `location` in the output
PDF's filename (see [Naming the output PDF](editing-notes.md#naming-the-output-pdf)).
Entries written before `timezone`/`location` existed, or hand-edited with
the old `"HH:MM--HH:MM TZ, location"` convention, still load into the
picker correctly — and get migrated to the two dedicated fields the next
time they're saved from the app.
The header form is per markdown file — each `md/<stem>.md` has its own
paired `yaml/<stem>.yaml`, so switching files in the dropdown also switches
the header fields shown, and creating a file creates a blank paired yaml
alongside it (deleting a file removes its yaml too).

The **File** menu moves notes in and out of the project:

- **Import Markdown File…** (Ctrl+I) copies a markdown file from anywhere
  on your computer into the project's `md/` as a new note and opens it.
  The original stays where it is. The note is named after it (tidied the
  usual way, with `-2`, `-3`, … added if the name is taken) and starts with
  a blank header to fill in.
- **Export Markdown…** (Ctrl+E) saves a copy of the open note's markdown,
  as it is in the editor, wherever you choose.
- **Export LaTeX…** (Ctrl+Shift+E) saves the open note as a single `.tex`
  file: `settings/template.tex` with the note's header, content, cue
  notes, summaries, and page settings written into it, so it compiles on
  its own with `pdflatex`. It names images and linked files by their
  `assets/...` paths, so compile it from the project folder (or keep a
  copy of `assets/` next to it).

The new-file, delete-file, **Render**, and **Download PDF** buttons all
disable for as long as a render is running (Render reads "Rendering…"), so
a fast double-click can't submit twice. Deleting a file asks first; **File
> Render PDF** (Ctrl+R) is the same as the Render button. Render saves both the selected
file's header and its markdown content to disk and runs `make build` for
you; the app bar's status chip (see above) reports success or failure.
Download PDF (disabled until a PDF exists) opens a save dialog to copy the
current one out of `pdf/`, defaulting to its actual output filename. The
app remembers the last file you had open for next time.

Below that, the markdown editor (left) and the resulting PDF (right) sit
side by side, sized to the window: together they fill whatever height is
left under the Details section, growing and shrinking as you resize the
window, and the divider between them drags to trade width. Folding
Details away gives them its space too. In a window too short for them
(they keep a minimum height), the page scrolls instead. The PDF pane shows the selected file's PDF
if one has already been built from its current header, and a "Preview out of
date" chip appears in the app bar whenever the header or markdown has
changed since that file's last render in this window. Header fields and markdown content
both autosave to disk continuously as you edit (about half a second after
you stop typing, or as soon as the editor loses focus) rather than only on
Render, so switching files or closing the window doesn't lose unsaved work.
The preview opens fitted to the pane — the whole page visible at once,
however the window is sized — with the viewer's page-thumbnail
sidebar closed; its menu button (top left of the preview) toggles it, and
its toolbar has zoom and fit-to-width buttons.
Links clicked inside the PDF preview open in your web browser.

The editor itself is [CodeMirror](https://codemirror.net/), with syntax
highlighting for Markdown, inline/raw HTML, and fenced ` ```html `/
` ```latex ` code blocks. It runs in a Qt WebEngine view — the one part of
the window that's a web page (`app/web/`) — which is also what gives it
Chromium's built-in spellcheck: misspelled words get the usual squiggly
underline, and the right-click menu offers spelling suggestions.
**View > Zoom Editor In/Out** changes its text size.

Spellcheck needs a dictionary. The standalone builds come with US English;
run any other way, the app has none until you give it one. In both cases
it reads Chromium-format dictionaries (`<language>.bdic`, e.g.
`en-GB.bdic`) from a `qtwebengine_dictionaries` folder in its data
directory — `~/.local/share/markdown-cornell-notes/Markdown Cornell Notes/`
on Linux — and checks in the system's language when there's a dictionary
for it. The Chromium project publishes ready-made ones in its
[hunspell_dictionaries](https://chromium.googlesource.com/chromium/deps/hunspell_dictionaries/)
repository.

The editor's JS is vendored (`app/web/editor.js`) rather than loaded from
a CDN, so the app works offline and never needs Node.js to run; only
rebuilding that bundle does. If you edit `app/frontend_src/editor.js`,
rebuild it with:

```sh
cd app
npm install
npm run build:editor
```

## Formatting toolbar

A toolbar sits above the editor, grouped by kind:

- **Bold**, *italic*, ~~strikethrough~~, inline math (`$...$`), superscript,
  subscript — wrap the current selection (or a placeholder, if nothing's
  selected) in the matching Markdown syntax; the wrapped/placeholder text
  stays selected afterward so you can type straight over it.
- **Heading** — cycles the cursor's current line through `#` → `##` → `###`
  → no heading on repeated clicks.
- Quote, bullet list, numbered list, task list — toggle a per-line prefix
  (`> `, `- `, `1. `/`2. `/…, `- [ ] `) across every line the selection
  spans; clicking again on already-prefixed lines removes it.
- Inline code, fenced code block, Link, Table — code wraps like bold/italic
  above; Link inserts `[text](https://)` with the URL placeholder selected;
  Table inserts a 2-column pipe-table skeleton with its header placeholder
  selected.
- **HR**, display math (`$$...$$`) — insert a horizontal rule or a
  display-math line.
- **^**, **^^**, **PB** — insert a [cue-column](editing-notes.md#cue-column-text) note, a
  [summary-band](editing-notes.md#summary-band-text) note, or a
  [`<!-- pagebreak -->`](editing-notes.md#pagination) directive on a new line right after
  the cursor's current line. `^`/`^^`'s page-number placeholder (defaulting
  to `1`) is pre-selected, so typing the real page number immediately
  overwrites it — the editor has no way to know which rendered PDF page the
  cursor's content will actually land on, since that's decided later by
  automatic pagination, so `1` is just as good a starting guess as any (and
  an out-of-range page number still renders on the nearest real page rather
  than vanishing, same as typing the directive by hand).

The toolbar's ~20 buttons wrap onto a second row if the editor pane isn't
wide enough to fit them all on one; the editor and PDF panes stay matched
in height either way.

## Autocompletion

The editor also offers three autocomplete sources, triggered by what you
type:

- Typing ` ``` ` at the start of a line suggests a fenced code-block
  language tag (`html`, `latex`/`tex`, `python`, `javascript`, `bash`,
  `json`, `yaml`, `text`). Only `html` and `latex`/`tex` get real syntax
  highlighting in the editor — and, like every fenced-code tag, none of
  them get highlighted in the built PDF either, since
  `scripts/markdown_to_pages.py` runs pandoc with `--no-highlight` — so the
  rest are just readable labels for the block's content, the same role
  `notes-example.md`'s own ` ```python ` block plays.
- Typing `](` inside a link or image target suggests filenames from
  `assets/` (as `assets/<name>`), so you don't have to remember exact
  names.
- Typing `/` at the start of a line or after whitespace (not mid-URL, so
  `https://` doesn't trigger it) offers snippet commands for everything the
  toolbar buttons above do (`/bold`, `/table`, `/task`, `/link`, `/image`,
  `/cue`, `/summary`, `/pagebreak`, etc.) — accepting one behaves exactly
  like clicking its toolbar button.
