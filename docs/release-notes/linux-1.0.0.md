# Markdown Cornell Notes for Linux 1.0.0 (AppImage)

The first standalone Linux release of the Markdown Cornell Notes editor.
Write meeting notes in Markdown, fill in the topic, date, and attendees,
and click **Render** to get a printable Cornell-style PDF, with the notes
panel, cue column, and summary band laid out for you.

It's a single file that includes everything the app needs to make PDFs, so
there's no TeX Live, pandoc, Python, or Node.js to install.

## Download

| File | Size |
| --- | --- |
| `Markdown-Cornell-Notes-1.0.0-x86_64.AppImage` | 326 MB |

SHA-256: `d173709314e40b9f3c9b67939a16235aa1ea537d93776aef1cf1358caddbc8a6`

To check your download:

```sh
sha256sum Markdown-Cornell-Notes-1.0.0-x86_64.AppImage
```

## Requirements

- A 64-bit Intel or AMD (x86_64) PC. ARM devices such as the Raspberry Pi
  aren't supported by this download.
- A desktop Linux distribution from about 2020 or later, for example
  Ubuntu 20.04, Debian 11, Fedora 40, or newer
- About 350 MB of free disk space for the file

## Running it

There's nothing to install. Make the file executable, then run it:

```sh
chmod +x Markdown-Cornell-Notes-1.0.0-x86_64.AppImage
./Markdown-Cornell-Notes-1.0.0-x86_64.AppImage
```

In most file managers you can instead right-click the file, open
**Properties**, allow it to run as a program, and then double-click it.

### If it doesn't start

- **"AppImages require FUSE to run"** (or `error loading libfuse.so.2`):
  AppImages need the FUSE 2 library, which many newer distributions don't
  install by default. Install it:

  ```sh
  sudo dnf install fuse-libs      # Fedora
  sudo apt install libfuse2t64    # Ubuntu 24.04+, Debian 13+
  sudo apt install libfuse2       # older Ubuntu and Debian
  ```

  Or run it without FUSE. This is slower to start, because it unpacks
  about 800 MB to `/tmp` each time:

  ```sh
  ./Markdown-Cornell-Notes-1.0.0-x86_64.AppImage --appimage-extract-and-run
  ```

- **An error mentioning the sandbox** (Ubuntu 24.04 and later restrict a
  feature the app's sandbox relies on): start it with `--no-sandbox`:

  ```sh
  ./Markdown-Cornell-Notes-1.0.0-x86_64.AppImage --no-sandbox
  ```

## Getting started

The first time the app opens, it creates a **Cornell Notes** folder in your
**Documents** folder with example notes, and opens it.

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
Folder** opens the current one in your file manager.

## What's included

- The editor: a Markdown editor with a formatting toolbar and
  autocompletion, a live PDF preview, autosave, light and dark themes, and
  file and asset management.
- Everything needed to build PDFs, bundled inside the file and used only
  by this app:
  - TeX Live 2026, a minimal set via TinyTeX v2026.10
  - pandoc 3.12.1
  - Python 3.13.16, from python-build-standalone

The app doesn't change your `PATH` or touch any TeX Live, pandoc, or Python
you have installed.

## Removing it

Delete the AppImage file. Your notes in `Documents/Cornell Notes` (or any
other project folder) are left in place. The app's own settings, such as
the last folder you opened, are in
`~/.config/markdown-cornell-notes-editor`, and you can delete that folder
too.

## Known issues

- **May need FUSE 2 or `--no-sandbox` to start** on some distributions
  (see "If it doesn't start").
- **x86_64 only:** there's no ARM build yet.
- **No menu entry:** an AppImage doesn't add itself to your applications
  menu. Run the file directly, or use a tool such as AppImageLauncher or
  Gear Lever to integrate it.
- **Large download:** about 326 MB, mostly the bundled LaTeX and pandoc.
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
(GPL-2.0-or-later), and Python (PSF License) keep their own licenses. To
read `THIRD-PARTY-NOTICES.txt`, with details and links to their source
code, run the AppImage with `--appimage-extract` and look in
`squashfs-root/resources`.
