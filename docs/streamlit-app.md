# Streamlit editor app

A browser UI for the whole pipeline described in the [main README](../README.md)
— edit the header fields and a markdown file side by side with a rendered
PDF, without touching the CLI.

```sh
pip install -r requirements.txt
make app
```

then open the URL `streamlit` prints (defaults to
[http://localhost:8501](http://localhost:8501)).

The page has a collapsible **Header** section (`topic`/`date`/`attendees`/
`time`) at the top. Location lives under Topic, and start/end time (12-hour,
with an AM/PM toggle) + a searchable IANA timezone dropdown live under Date,
all stacked below their respective field; the dropdown to switch between the
files in `md/` lives under Attendees. `date` is a calendar date picker, still stored in
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

Below the **Header** section is an **Assets** expander (labeled with the
current file count) that manages the `assets/` folder used for images and
linked documents (see [Images and linked documents](editing-notes.md#images-and-linked-documents)):
it lists each file with an image thumbnail (where applicable), a
copyable `assets/<name>` path to paste into your Markdown, and its size, plus
an uploader to add new files and a delete confirmation per file.

Below that, a centered row of **New file**/**Delete file** buttons (to
create or delete a file) sits next to **Render** and **Download PDF**.
Render saves both the selected file's header and its markdown content to
disk and runs `make build` for you, showing a success/failure message once
it's done. Download PDF (disabled until a PDF exists) downloads the current
one under its actual output filename. Below that, the markdown editor
(left) and the resulting PDF (right) sit side by side,
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
