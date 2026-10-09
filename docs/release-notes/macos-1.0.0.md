# Markdown Cornell Notes for macOS 1.0.0 (Apple Silicon)

The first macOS release of the Markdown Cornell Notes editor. Write meeting
notes in Markdown, fill in the topic, date, and attendees, and click
**Render** to get a printable Cornell-style PDF, with the notes panel, cue
column, and summary band laid out for you.

The app includes everything it needs to make PDFs, so there's no MacTeX,
pandoc, or Python to install separately.

## Download

| File | Size |
| --- | --- |
| `Markdown-Cornell-Notes-1.0.0-arm64-mac.zip` | 349 MB |

SHA-256: `fb7d5398b7d010b08a338feb4b7dc67b613d3f217d607d0bfb72b16501200079`

To check your download in Terminal:

```sh
shasum -a 256 ~/Downloads/Markdown-Cornell-Notes-1.0.0-arm64-mac.zip
```

## Requirements

- A Mac with Apple silicon (M1 or later). Intel Macs aren't supported by
  this download.
- macOS 13 Ventura or later
- About 850 MB of free disk space

## Installing

1. Download the zip and open it. If your browser didn't unzip it
   already, double-click it to get **Markdown Cornell Notes.app**.
2. Drag **Markdown Cornell Notes** into your **Applications** folder.
3. Open it. **The first time, macOS blocks it** with a message that Apple
   couldn't verify it's free of malware. This release isn't signed with an
   Apple Developer ID or notarized by Apple yet. To allow it:
   - Click **Done** in that message.
   - Open **System Settings > Privacy & Security**, scroll down to the
     message about "Markdown Cornell Notes", and click **Open Anyway**.
   - Confirm with your password or Touch ID, then click **Open**.

   You only need to do this once. On macOS 13 and 14 you can also
   Control-click the app in Applications, choose **Open**, then click
   **Open** again.

If macOS instead says the app "is damaged and can't be opened", clear the
download's quarantine flag in Terminal, then open it again:

```sh
xattr -dr com.apple.quarantine "/Applications/Markdown Cornell Notes.app"
```

## Getting started

The first time the app opens, it asks for permission to use your
**Documents** folder. Click **Allow**. It then creates a **Cornell Notes**
folder there with example notes, and opens it.

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

To keep notes somewhere else, use **File > Open Project Folder…** (⌘O).
If that folder isn't a notes project yet, the app offers to set one up. It
reopens the last folder you used. **File > Show Project Folder** opens the
current one in Finder.

## What's included

- The editor: a Markdown editor with a formatting toolbar and
  autocompletion, a live PDF preview, autosave, light and dark themes, and
  file and asset management.
- Everything needed to build PDFs, bundled inside the app and used only by
  it:
  - TeX Live 2026, a minimal set via TinyTeX v2026.10
  - pandoc 3.12.1
  - Python 3.13.16, from python-build-standalone

The app doesn't change your `PATH` or touch any MacTeX, Homebrew, or
Python you have installed.

## Uninstalling

Drag **Markdown Cornell Notes** from Applications to the Trash. Your notes
in `Documents/Cornell Notes` (or any other project folder) are left in
place. The app's own settings, such as the last folder you opened, are in
`~/Library/Application Support/markdown-cornell-notes-editor`, and you can delete
that folder too.

## Known issues

- **macOS blocks the first launch:** the app isn't Developer ID-signed or
  notarized yet (see Installing, step 3).
- **Apple Silicon only:** there's no Intel build yet. On an Intel Mac,
  the [Homebrew install](https://github.com/forloop11/markdown-cornell-notes/blob/main/docs/installation.md#installing-on-macos-homebrew)
  works instead.
- **Large download:** about 349 MB, mostly the bundled LaTeX and pandoc.

If something doesn't work, please
[open an issue](https://github.com/forloop11/markdown-cornell-notes/issues),
and include the **Build log** text if Render failed.

## Licenses

Markdown Cornell Notes is MIT-licensed. The bundled TeX Live, pandoc
(GPL-2.0-or-later), and Python (PSF License) keep their own licenses. See
`THIRD-PARTY-NOTICES.txt` inside the app (Control-click the app, choose
**Show Package Contents**, then open `Contents/Resources`) for details and
links to their source code.
