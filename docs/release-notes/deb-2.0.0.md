# Markdown Cornell Notes 2.0.0 for Debian and Ubuntu (.deb)

The command-line tool and the editor app as a `.deb` package, for people
who would rather use their system's own TeX Live, pandoc, and Python than
the self-contained AppImage. It's small (about 1 MB): `apt` installs what
it needs alongside it.

## Download

| File | Size |
| --- | --- |
| `markdown-cornell-notes_2.0.0.deb` | 1.2 MB |

SHA-256: `448547b1d045de302794755519cdad17fb63d915f3d0125d75083901a6e24990`

To check your download:

```sh
sha256sum markdown-cornell-notes_2.0.0.deb
```

## Requirements

- Debian 13 (trixie) or later, or Ubuntu 24.04 or later. Built for any
  architecture (it contains no compiled code); tested on Debian 13.
- On older releases the command-line build may still work, but their
  pandoc is too old for some notes (strikethrough fails to build with
  pandoc 2), and the editor needs PySide6 6.8 or later, which they don't
  package.

## Installing

```sh
sudo apt install ./markdown-cornell-notes_2.0.0.deb
```

`apt` brings in pandoc, latexmk, and TeX Live (`texlive-latex-extra` and
what it needs — several hundred megabytes if you don't have TeX Live
yet), plus the PySide6 packages for the editor app, which the package
recommends.

## Using it

Each project lives in a directory of its own:

```sh
mkdir ~/notes && cd ~/notes
markdown-cornell-notes init     # example notes to start from
markdown-cornell-notes build    # -> pdf/<topic>_<date>_<location>.pdf
markdown-cornell-notes app      # the editor, on this directory's notes
```

See the
[documentation](https://github.com/forloop11/markdown-cornell-notes#documentation)
for the notes format and the editor.

## Updating and removing

Installed from a downloaded file like this, the package doesn't update
itself: install a newer `.deb` the same way when there is one. To remove
it, `sudo apt remove markdown-cornell-notes`; your notes are untouched.

## Known issues

- **On Ubuntu 24.04 and later the editor may refuse to start** with a
  message about its sandbox;
  `markdown-cornell-notes app APP_FLAGS=--no-sandbox` starts it without.
- **No spellcheck dictionary is included** (the AppImage has US English);
  the [editor app](https://github.com/forloop11/markdown-cornell-notes/blob/main/docs/editor-app.md)
  page says how to add one.
- **No application-menu entry**: start the editor with
  `markdown-cornell-notes app` from a project directory.

## License

MIT. The package contains only this project's own files; TeX Live, pandoc,
Python, and Qt come from your distribution's packages under their own
licenses.
