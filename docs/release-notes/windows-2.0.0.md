# Markdown Cornell Notes for Windows 2.0.0 — test build

> **This is a test build.** Version 2 of the app has been rebuilt on Qt,
> and this Windows build of it **has not yet been run on Windows**: it's
> assembled and checked on Linux only. It also isn't code-signed, so
> Windows warns before running the installer (see "Installing"). If you
> try it, please
> [report what happens](https://github.com/forloop11/markdown-cornell-notes/issues)
> — whether it works or not.

Write meeting notes in Markdown, fill in the topic, date, and attendees,
and click **Render** to get a printable Cornell-style PDF, with the notes
panel, cue column, and summary band laid out for you.

This installer includes everything the app needs to make PDFs, so there's
no LaTeX, pandoc, or Python to install separately.

## Download

| File | Size |
| --- | --- |
| `Markdown-Cornell-Notes-Setup-2.0.0.exe` | 270 MB |

SHA-256: `42242aaff961ebbced15391ae5194c17966756676694af19b77ecac1ec2f4a15`

To check your download in PowerShell:

```powershell
Get-FileHash .\Markdown-Cornell-Notes-Setup-2.0.0.exe -Algorithm SHA256
```

## What's new since 1.0

- **Assets explorer.** A file tree of the project's `assets` folder down
  the left side of the window, replacing the Assets panel at the bottom.
  Drag files in from File Explorer, drag them between folders, and
  double-click a file to copy a ready-to-paste Markdown link. The red
  hamburger button in the app bar hides and shows it.
- **Import and export.** **File > Import Markdown File…** brings an
  existing `.md` file into the project as a new note. **Export Markdown…**
  and **Export LaTeX…** save the open note as a `.md` file or a single
  self-contained `.tex` file.
- **A window that fits.** The editor and PDF preview fill the window and
  resize with it; the preview opens with the whole page fitted.
- **Time picker** for Start and End, and **View > Appearance** to switch
  between Light, Dark, and following Windows.
- **Images without a size now render.** `![alt](assets/file.png)` with no
  `{width=...}` used to fail to build.

## Requirements

- Windows 10 or Windows 11, 64-bit (x64)
- About 1.1 GB of free disk space
- No administrator rights: the app installs for your user account only

## Installing

If version 1.0 is installed, uninstall it first (**Settings > Apps**), so
its files and shortcuts don't linger alongside version 2's. Your notes
aren't affected.

1. Download `Markdown-Cornell-Notes-Setup-2.0.0.exe` and run it.
2. **Windows may show "Windows protected your PC."** This build isn't
   code-signed, so SmartScreen doesn't recognize it. Click **More info**,
   then **Run anyway**.
3. Accept the license, pick an install folder (the default is fine), and
   finish. The installer adds Start menu and desktop shortcuts.

To remove it later, uninstall **Markdown Cornell Notes** from
**Settings > Apps**. Your notes stay where they are.

## Getting started

The first time you open the app, it creates a **Cornell Notes** folder in
your **Documents** folder with example notes, and opens it — or, if 1.0
already made one, opens that with your notes as you left them.

- **Fill in the details** (topic, date, start and end time, timezone,
  location, attendees) in the **Details** section.
- **Edit your notes** in the Markdown editor on the left. Your changes save
  automatically as you type.
- **Click Render** (Ctrl+R) to build the PDF, shown on the right and saved
  in the project's `pdf` folder.
- **Add images and files** with the assets explorer on the left, then
  double-click one to copy its link and paste it into your notes.

## Known issues

- **Untested on Windows**, as above. Things that may go wrong on a first
  run: the app not starting at all, the editor or PDF pane staying blank,
  or Render failing. The **Build log** that opens on a failed Render is
  the most useful thing to include in a report. If the app doesn't start,
  running it from Command Prompt shows why:

  ```bat
  "%LOCALAPPDATA%\Programs\Markdown Cornell Notes\resources\python\python.exe" "%LOCALAPPDATA%\Programs\Markdown Cornell Notes\resources\pipeline\app\main.py"
  ```

- **The app has no `.exe` of its own**: its shortcuts start the bundled
  Python. The taskbar or Task Manager may show it as "Python".
- **Not code-signed**, so SmartScreen warns about the installer.
- **Spellcheck is US English only.**

## Licenses

Markdown Cornell Notes is MIT-licensed. The bundled TeX Live, pandoc
(GPL-2.0-or-later), Python (PSF License), and Qt (LGPL-3.0) keep their own
licenses; `THIRD-PARTY-NOTICES.txt`, in the install folder's `resources`,
has details and links to their source code.
