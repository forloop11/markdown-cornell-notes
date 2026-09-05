# Editing notes

- **`yaml/notes.yaml`** — the header fields (`topic`, `date`, `attendees`,
  `time`, `timezone`, `location`). Applied to every page automatically.
  Paired with its markdown file by name: `md/<stem>.md` goes with
  `yaml/<stem>.yaml`.
- **`md/notes.md`** — the notes panel content, written in Markdown.

```yaml
topic: Weekly Sync
date: 2026-08-23
attendees: Alice, Bob, Priya
time: "10:00--10:30"
timezone: "America/Los_Angeles"
location: "Zoom"
```

`timezone` and `location` are both optional. `timezone` is only meaningful
to the app's picker (see [Streamlit editor app](streamlit-app.md)) —
it holds the IANA zone name behind `time`'s abbreviation and isn't typeset
itself. `location` *is* typeset: `settings/template.tex` appends it to
`time` (as `"10:00--10:30, Zoom"`) on the Time row, and
`scripts/topic_slug.py` folds it into the output PDF's filename (see
[Naming the output PDF](#naming-the-output-pdf)).

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

## Pagination

The notes panel has a fixed height, so `md/notes.md` is measured and
automatically split across as many pages as it needs — you don't have to
plan page breaks by hand. If you want to force a break at a specific point
anyway (e.g. to start a new topic on its own page), put a line containing
only

```
<!-- pagebreak -->
```

between two sections.

## Cue-column text

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

## Summary-band text

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

## Multiple topics per document

`settings/template.tex` just does `\input{\cnBuildDir/cornell-content.tex}`,
which holds one `cornellFlow` environment per `md/notes.md` section.
(`\cnBuildDir` defaults to `build`, overridden per-invocation by the
Makefile's `BUILDDIR` — see `make build-example` (in the
[project structure](project-structure.md) notes) and the Streamlit app's
own scratch directory — so isolated builds actually compile their own
generated content instead of whatever's currently in the default `build/`.)
Every resulting page shares the same header from `yaml/notes.yaml` and
numbers itself automatically (top-right corner of the header box).

## Images and linked documents

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
correctly (web URLs are left untouched).

## Naming the output PDF

The PDF is written to `pdf/` and named after `yaml/notes.yaml`'s `topic`,
`date`, and `location` fields, not a fixed `cornell-notes.pdf`.
`scripts/topic_slug.py` slugifies each field — collapsing any run of
characters that aren't safe in a filename (spaces, punctuation, ...) to a
single hyphen — and joins them with an underscore, so:

```yaml
topic: Weekly Sync
date: 2026-08-23
location: Zoom
```

produces `pdf/Weekly-Sync_2026-08-23_Zoom.pdf`. A blank/missing `location`
is dropped rather than leaving a trailing underscore, so entries without
one still produce `pdf/Weekly-Sync_2026-08-23.pdf` as before. Change
`topic`/`date`/`location` and run `make build` again to rename the output;
the previous PDF isn't deleted automatically.
