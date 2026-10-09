# Editor app

A desktop app for the whole pipeline described in the [main README](../README.md)
— edit the header fields and a markdown file side by side with a rendered
PDF, without touching the CLI. It's an [Electron](https://www.electronjs.org/)
app (`app/`) working on the same `md/`, `yaml/`, `pdf/`, and `assets/` files
the CLI uses, in whichever project directory you start it from.

It needs [Node.js](https://nodejs.org/) (with npm) on top of the usual
`make build` requirements. From a git checkout, install the app's
dependencies once, then start it from the repo root (which is itself a
project):

```sh
cd app && npm install && cd ..
make app
```

From an installed `.deb`/Homebrew package, just run
`markdown-cornell-notes app` in a project directory — with no `npm install`
of its own to use, the first run downloads the Electron version the app
pins into your npm cache (via `npx`), and later runs reuse it.

The window shows the project folder in its title bar. Closing it ends the
app; anything typed since the last autosave is saved first.

**Linux sandbox note:** on distributions that restrict unprivileged user
namespaces (Ubuntu 24.04 and later, via AppArmor), Electron can refuse to
start with an error about its sandbox. Either allow it the usual Electron
way for your distribution, or start it without Chromium's sandbox:

```sh
make app ELECTRON_FLAGS=--no-sandbox
```

The app only ever loads its own bundled page and your project's local
files, but the sandbox is still a useful safety net — prefer fixing the
OS-level restriction where you can.

Along the top, an app bar stays pinned while you scroll. On the left are
the dropdown to switch between the files in `md/` and **+** (new file) /
trash (delete file) buttons; on the right, a status area, the pane-height
dropdown, **Download PDF**, and **Render**. The status area shows a small
"Saved"/"Saving…" autosave indicator, a "Preview out of date" chip (see
below), and — once you've clicked Render — a success/failure chip. On
failure a **Build log** expander (the raw `make build` output) opens under
the app bar so you can see what went wrong.

Below the app bar is a collapsible **Details** section holding the header
fields: Topic, Date, and start/end time pickers on the first row; Location,
a searchable IANA timezone field (type to filter, then pick a zone), and
Attendees on the second. Collapsed, it shows a one-line recap (topic, date,
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

The new-file, delete-file, **Render**, and **Download PDF** buttons all
disable for as long as a render is running (Render shows a spinner), so a
fast double-click can't submit twice. Render saves both the selected
file's header and its markdown content to disk and runs `make build` for
you; the app bar's status chip (see above) reports success or failure.
Download PDF (disabled until a PDF exists) opens a save dialog to copy the
current one out of `pdf/`, defaulting to its actual output filename. The
pane-height dropdown next to it (30%–200%, 100% by default) scales the
editor/PDF pane height below — pick a smaller value to fit both panes on a
shorter screen without scrolling. The app remembers that choice, and the
last file you had open, for next time.

Below that, the markdown editor (left) and the resulting PDF (right) sit
side by side, matched in height (per the pane-height dropdown above) so
their tops and bottoms align. The PDF pane shows the selected file's PDF
if one has already been built from its current header, and a "Preview out of
date" chip appears in the app bar whenever the header or markdown has
changed since that file's last render in this window. Header fields and markdown content
both autosave to disk continuously as you edit (about half a second after
you stop typing, or as soon as the editor loses focus) rather than only on
Render, so switching files or closing the window doesn't lose unsaved work.
Links clicked inside the PDF preview open in your web browser.

At the bottom is an **Assets** expander (labeled with the current file
count) that manages the `assets/` folder used for images and linked
documents (see [Images and linked documents](editing-notes.md#images-and-linked-documents)):
it lists each file with an image thumbnail (where applicable), a
copyable `assets/<name>` path to paste into your Markdown, and its size, plus
an uploader to add new files and a delete confirmation per file. Folders
can be created, opened (with a breadcrumb trail back up), renamed, and
deleted, and checked files can be moved into another folder in bulk.

The editor itself is [CodeMirror](https://codemirror.net/), with syntax
highlighting for Markdown, inline/raw HTML, and fenced ` ```html `/
` ```latex ` code blocks, and — the reason it's CodeMirror rather than a
more typical embedded code-editor widget — real support for Chromium's
built-in spellcheck: misspelled words get the usual squiggly underline, and
the right-click menu offers spelling suggestions and "Add to dictionary",
which Electron remembers across sessions with no app-side state at all.
Its JS is vendored (`app/renderer/editor.js`) rather than loaded from a
CDN, so the app works offline and an installed copy doesn't need to build
anything; if you edit `app/frontend_src/editor.js`, rebuild it with:

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
