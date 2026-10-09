# Markdown Cornell Notes for Windows 1.0.0

The first Windows release of the Markdown Cornell Notes editor. Write
meeting notes in Markdown, fill in the topic, date, and attendees, and click
**Render** to get a printable Cornell-style PDF, with the notes panel, cue
column, and summary band laid out for you.

This installer includes everything the app needs to make PDFs, so there's
no LaTeX, pandoc, or Python to install separately.

## Download

| File | Size |
| --- | --- |
| `Markdown-Cornell-Notes-Setup-1.0.0.exe` | 285 MB |

SHA-256: `d74cdb3480725243d51ce939f2f041563fe8b6b5d7db4618d51b7f5358f49c28`

To check your download in PowerShell:

```powershell
Get-FileHash .\Markdown-Cornell-Notes-Setup-1.0.0.exe -Algorithm SHA256
```

## Requirements

- Windows 10 or Windows 11, 64-bit (x64)
- About 950 MB of free disk space
- No administrator rights: the app installs for your user account only

## Installing

1. Download `Markdown-Cornell-Notes-Setup-1.0.0.exe` and run it.
2. **Windows may show "Windows protected your PC."** This release isn't
   code-signed yet, so SmartScreen doesn't recognize it. Click
   **More info**, then **Run anyway**.
3. Accept the license, pick an install folder (the default is fine), and
   finish. The installer adds Start menu and desktop shortcuts.

## Getting started

The first time you open the app, it creates a **Cornell Notes** folder in
your **Documents** folder with example notes, and opens it.

- **Edit your notes** in the Markdown editor on the left. Your changes save
  automatically as you type.
- **Fill in the details** (topic, date, start and end time, timezone,
  location, attendees) in the **Details** card. They make up the header at
  the top of each page.
- **Click Render** to build the PDF. It appears in the preview on the right
  and is saved in the project's `pdf` folder, named after the topic, date,
  and location.
- **Download PDF** saves a copy wherever you like.
- **Add questions to the cue column** with `^1 your question` (the number
  is the page), and **summary notes** with `^^1 your summary`. The toolbar
  buttons insert these for you.
- **Add images and files** with the **Assets** panel at the bottom, then
  link to them from your notes.

To keep notes somewhere else, use **File > Open Project Folder…**
(Ctrl+O). If that folder isn't a notes project yet, the app offers to set
one up. It reopens the last folder you used. **File > Show Project
Folder** opens the current one in File Explorer.

## What's included

- The editor: a Markdown editor with a formatting toolbar and
  autocompletion, a live PDF preview, autosave, light and dark themes, and
  file and asset management.
- Everything needed to build PDFs, bundled and used only by this app:
  - TeX Live 2026, a minimal set via TinyTeX v2026.10
  - pandoc 3.12.1
  - Python 3.13.16, the embeddable version

The app doesn't change your system's `PATH` or touch any other LaTeX,
pandoc, or Python you have installed.

## Uninstalling

Use **Settings > Apps > Installed apps > Markdown Cornell Notes >
Uninstall**. Your notes in `Documents\Cornell Notes` (or any other project
folder) are left in place.

## Known issues

- **SmartScreen warning on first install:** the installer isn't
  code-signed yet (see Installing, step 2).
- **Large download:** about 285 MB, mostly the bundled LaTeX and pandoc.
- **Windows only:** this installer is for Windows. On Linux and macOS, see
  the [installation guide](https://github.com/forloop11/markdown-cornell-notes/blob/main/docs/installation.md).

If something doesn't work, please
[open an issue](https://github.com/forloop11/markdown-cornell-notes/issues),
and include the **Build log** text if Render failed.

## Licenses

Markdown Cornell Notes is MIT-licensed. The bundled TeX Live, pandoc
(GPL-2.0-or-later), and Python (PSF License) keep their own licenses. See
`THIRD-PARTY-NOTICES.txt` in the app's `resources` folder for details and
links to their source code.
