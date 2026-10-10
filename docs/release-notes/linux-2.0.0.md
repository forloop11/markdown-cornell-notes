# Markdown Cornell Notes for Linux 2.0.0 (AppImage)

Write meeting notes in Markdown, fill in the topic, date, and attendees,
and click **Render** to get a printable Cornell-style PDF, with the notes
panel, cue column, and summary band laid out for you.

Version 2 is the same idea in a rebuilt app: the editor now runs on Qt
instead of Electron, and gains an assets explorer, Markdown import,
Markdown and LaTeX export, and a window that sizes itself sensibly. It's
still a single file that includes everything the app needs to make PDFs,
so there's no TeX Live, pandoc, or Python to install.

## Download

| File | Size |
| --- | --- |
| `Markdown-Cornell-Notes-2.0.0-x86_64.AppImage` | 334 MB |
| `Markdown-Cornell-Notes-2.0.0-x86_64.AppImage.zsync` | 0.6 MB |

You only need the `.AppImage`. The `.zsync` file is for update tools (see
"Updating").

SHA-256 of the AppImage:
`df26a0da9e6f0d21524da68b2dd0dc3436f0632a8ce6d1ce79bdd70b25e7f05b`

To check your download:

```sh
sha256sum Markdown-Cornell-Notes-2.0.0-x86_64.AppImage
```

## What's new since 1.0

- **Assets explorer.** A file tree of the project's `assets/` folder down
  the left side of the window, replacing the Assets panel at the bottom.
  Drag files in from your file manager, drag them between folders, and
  double-click a file to copy a ready-to-paste Markdown link
  (`![pipeline](assets/diagrams/pipeline.png)`). The red hamburger button
  in the app bar hides and shows it.
- **Import and export.** **File > Import Markdown File…** brings an
  existing `.md` file into the project as a new note. **Export Markdown…**
  and **Export LaTeX…** save the open note as a `.md` file or a single
  self-contained `.tex` file.
- **A window that fits.** The editor and PDF preview now fill the window
  and resize with it; the pane-height dropdown is gone. The preview opens
  with the whole page fitted.
- **Time picker.** Start and End open a picker of hours and minutes (in
  steps of five); typing any time still works.
- **Light or dark, your choice.** **View > Appearance** switches between
  Light, Dark, and following your desktop.
- **Images without a size now render.** `![alt](assets/file.png)` with no
  `{width=...}` used to fail to build; it now fits the image to the notes
  panel.
- **No FUSE 2 needed.** The AppImage starts without the `libfuse2`
  library that 1.0 needed on newer distributions.
- **Updates.** The AppImage knows where its updates are published, so
  update tools can fetch new versions.

## Requirements

- A 64-bit Intel or AMD (x86_64) PC. ARM devices such as the Raspberry Pi
  aren't supported by this download.
- A desktop Linux distribution with glibc 2.34 or later: Ubuntu 22.04,
  Debian 12, Fedora 35, RHEL 9, or newer. **This is newer than 1.0
  needed** (which ran on Ubuntu 20.04 and Debian 11); on those, stay with
  1.0.
- About 350 MB of free disk space for the file

## Running it

There's nothing to install. Make the file executable, then run it:

```sh
chmod +x Markdown-Cornell-Notes-2.0.0-x86_64.AppImage
./Markdown-Cornell-Notes-2.0.0-x86_64.AppImage
```

In most file managers you can instead right-click the file, open
**Properties**, allow it to run as a program, and then double-click it.

### If it doesn't start

- **An error about `libxcb-cursor`** (on X11 desktops): install the one
  small library Qt needs there:

  ```sh
  sudo apt install libxcb-cursor0     # Ubuntu, Debian
  sudo dnf install xcb-util-cursor    # Fedora
  ```

- **An error mentioning the sandbox** (Ubuntu 24.04 and later restrict a
  feature the app's sandbox relies on): start it with `--no-sandbox`:

  ```sh
  ./Markdown-Cornell-Notes-2.0.0-x86_64.AppImage --no-sandbox
  ```

- **"version `GLIBC_2.34' not found"**: the distribution is older than
  this release supports (see Requirements).

## Getting started

The first time the app opens, it creates a **Cornell Notes** folder in your
**Documents** folder with example notes, and opens it. If you used 1.0,
that folder is already there, and the app opens it with your notes as you
left them.

- **Fill in the details** (topic, date, start and end time, timezone,
  location, attendees) in the **Details** section. They make up the header
  at the top of each page.
- **Edit your notes** in the Markdown editor on the left. Your changes save
  automatically as you type.
- **Click Render** (Ctrl+R) to build the PDF. It appears in the preview on
  the right and is saved in the project's `pdf` folder, named after the
  topic, date, and location.
- **Download PDF** saves a copy wherever you like.
- **Add questions to the cue column** with `^1 your question` (the number
  is the page), and **summary notes** with `^^1 your summary`. The toolbar
  buttons insert these for you.
- **Add images and files** with the assets explorer on the left, then
  double-click one to copy its link and paste it into your notes.

To keep notes somewhere else, use **File > Open Project Folder…**
(Ctrl+O). If that folder isn't a notes project yet, the app offers to set
one up. It reopens the last folder you used. **File > Show Project
Folder** opens the current one in your file manager.

## Updating

This AppImage carries update information pointing at this project's
latest GitHub release. A tool such as
[AppImageUpdate](https://github.com/AppImageCommunity/AppImageUpdate) or
Gear Lever can use it to fetch a newer version when there is one,
downloading only what changed.

## What's included

- The editor: a Markdown editor with a formatting toolbar, autocompletion,
  and US English spellcheck; a PDF preview; an assets explorer; autosave;
  import and export; and light and dark themes.
- Everything needed to build PDFs, bundled inside the file and used only
  by this app:
  - TeX Live 2026, a minimal set via TinyTeX v2026.10
  - pandoc 3.12.1
  - Python 3.13.16, from python-build-standalone
  - Qt 6.12, through PySide6

The app doesn't change your `PATH` or touch any TeX Live, pandoc, Python,
or Qt you have installed.

## Removing it

Delete the AppImage file. Your notes in `Documents/Cornell Notes` (or any
other project folder) are left in place. The app's own settings, such as
the last folder you opened, are in `~/.config/markdown-cornell-notes`, and
you can delete that folder too. (Version 1.0 kept its settings in
`~/.config/markdown-cornell-notes-editor`, which 2.0 doesn't use.)

## Known issues

- **Needs a newer distribution than 1.0** (see Requirements).
- **May need `--no-sandbox` to start** on Ubuntu 24.04 and later (see "If
  it doesn't start").
- **Spellcheck is US English only**, and has no "add to dictionary".
- **Only folders can be renamed** in the assets explorer, and only files
  can be moved by dragging.
- **x86_64 only:** there's no ARM build yet.
- **No menu entry:** an AppImage doesn't add itself to your applications
  menu. Run the file directly, or use a tool such as AppImageLauncher or
  Gear Lever to integrate it.
- **Large download:** about 334 MB, mostly Qt and the bundled LaTeX and
  pandoc.
- This release was tested on Fedora 44. Please report problems on other
  distributions.

Already have TeX Live and pandoc? The
[`.deb` package and `make app`](https://github.com/forloop11/markdown-cornell-notes/blob/main/docs/installation.md)
use your system's tools instead and are much smaller.

If something doesn't work, please
[open an issue](https://github.com/forloop11/markdown-cornell-notes/issues),
and include the **Build log** text if Render failed.

## Licenses

Markdown Cornell Notes is MIT-licensed. The bundled TeX Live, pandoc
(GPL-2.0-or-later), Python (PSF License), and Qt (LGPL-3.0) keep their own
licenses. To read `THIRD-PARTY-NOTICES.txt`, with details and links to
their source code, run the AppImage with `--appimage-extract` and look in
`squashfs-root/resources`.
