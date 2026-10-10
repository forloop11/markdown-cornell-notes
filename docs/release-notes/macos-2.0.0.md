# Markdown Cornell Notes for macOS 2.0.0 (Apple Silicon) — test build

> **This is a test build.** Version 2 of the app has been rebuilt on Qt,
> and this macOS build of it **has not yet been run on a Mac**: it's
> assembled and checked on Linux only. It also isn't signed with an Apple
> Developer ID or notarized, so macOS blocks it on first launch (see
> "Installing"). If you try it, please
> [report what happens](https://github.com/forloop11/markdown-cornell-notes/issues)
> — whether it works or not.

Write meeting notes in Markdown, fill in the topic, date, and attendees,
and click **Render** to get a printable Cornell-style PDF, with the notes
panel, cue column, and summary band laid out for you.

The app includes everything it needs to make PDFs, so there's no MacTeX,
pandoc, or Python to install separately.

## Download

| File | Size |
| --- | --- |
| `Markdown-Cornell-Notes-2.0.0-arm64-mac.zip` | 525 MB |

SHA-256: `8ca6081f19275edbc1b759c78fc0eba7e35f541b1ff4f42918ec3b2450ab48f1`

To check your download in Terminal:

```sh
shasum -a 256 ~/Downloads/Markdown-Cornell-Notes-2.0.0-arm64-mac.zip
```

## What's new since 1.0

- **Assets explorer.** A file tree of the project's `assets/` folder down
  the left side of the window, replacing the Assets panel at the bottom.
  Drag files in from Finder, drag them between folders, and double-click
  a file to copy a ready-to-paste Markdown link. The red hamburger button
  in the app bar hides and shows it.
- **Import and export.** **File > Import Markdown File…** brings an
  existing `.md` file into the project as a new note. **Export Markdown…**
  and **Export LaTeX…** save the open note as a `.md` file or a single
  self-contained `.tex` file.
- **A window that fits.** The editor and PDF preview fill the window and
  resize with it; the preview opens with the whole page fitted.
- **Time picker** for Start and End, and **View > Appearance** to switch
  between Light, Dark, and following the system.
- **Images without a size now render.** `![alt](assets/file.png)` with no
  `{width=...}` used to fail to build.

## Requirements

- A Mac with Apple silicon (M1 or later). Intel Macs aren't supported by
  this download.
- **macOS 14 Sonoma or later** — newer than 1.0 needed (macOS 13).
- About 1.5 GB of free disk space

## Installing

1. Download the zip and open it. If your browser didn't unzip it
   already, double-click it to get **Markdown Cornell Notes.app**.
2. Drag **Markdown Cornell Notes** into your **Applications** folder.
3. Open it. **The first time, macOS blocks it** with a message that Apple
   couldn't verify it's free of malware. To allow it:
   - Click **Done** in that message.
   - Open **System Settings > Privacy & Security**, scroll down to the
     message about "Markdown Cornell Notes", and click **Open Anyway**.
   - Confirm with your password or Touch ID, then click **Open**.

   You only need to do this once.

If macOS instead says the app "is damaged and can't be opened", clear the
download's quarantine flag in Terminal, then open it again:

```sh
xattr -dr com.apple.quarantine "/Applications/Markdown Cornell Notes.app"
```

## Getting started

The first time the app opens, it may ask for permission to use your
**Documents** folder. Click **Allow**. It then creates a **Cornell Notes**
folder there with example notes, and opens it — or, if 1.0 already made
one, opens that with your notes as you left them.

- **Fill in the details** (topic, date, start and end time, timezone,
  location, attendees) in the **Details** section.
- **Edit your notes** in the Markdown editor on the left. Your changes save
  automatically as you type.
- **Click Render** (⌘R) to build the PDF, shown on the right and saved in
  the project's `pdf` folder.
- **Add images and files** with the assets explorer on the left, then
  double-click one to copy its link and paste it into your notes.

## Known issues

- **Untested on a Mac**, as above. Things that may go wrong on a first
  run: the app not starting at all, the editor or PDF pane staying blank,
  or Render failing. The **Build log** that opens on a failed Render, and
  anything printed when the app is started from Terminal
  (`"/Applications/Markdown Cornell Notes.app/Contents/MacOS/markdown-cornell-notes"`),
  are the most useful things to include in a report.
- **The menu bar may show "Python"** as the app's name instead of
  "Markdown Cornell Notes".
- **Not signed or notarized**, so the first launch needs the steps above.
- **Spellcheck is US English only.**
- **Apple silicon only**, and a large download: Qt's macOS files carry
  Intel code as well.

## Licenses

Markdown Cornell Notes is MIT-licensed. The bundled TeX Live, pandoc
(GPL-2.0-or-later), Python (PSF License), and Qt (LGPL-3.0) keep their own
licenses; `THIRD-PARTY-NOTICES.txt`, inside the app at
`Contents/Resources`, has details and links to their source code.
