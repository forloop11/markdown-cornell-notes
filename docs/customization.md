# Customizing the layout

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

Edit the file and run `make build` again; every page picks up the change
automatically. Under the hood this generates
`build/cornell-page-settings.tex`, the same pattern as the header and
content files described in [project structure](project-structure.md).
