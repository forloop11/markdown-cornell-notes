# Markdown Cornell Notes 2.0.0 for Fedora (RPM)

The command-line tool and the editor app as an RPM package, for people who
would rather use their system's own TeX Live, pandoc, and Python than the
self-contained AppImage. It's small (about 1 MB): `dnf` installs what it
needs alongside it.

## Download

| File | Size |
| --- | --- |
| `markdown-cornell-notes-2.0.0-1.fc44.noarch.rpm` | 1.2 MB |
| `markdown-cornell-notes-2.0.0-1.fc44.src.rpm` (source package) | 1.8 MB |

SHA-256 of the `.noarch.rpm`:
`ead342c74a246d3f33d076fc3d27663b482f3bde7fb50e9b09da24dd1cc15e28`

To check your download:

```sh
sha256sum markdown-cornell-notes-2.0.0-1.fc44.noarch.rpm
```

## Requirements

- Fedora. Built and tested on Fedora 44; the package contains no compiled
  code, so other current Fedora releases should work the same way.
- RHEL-family systems (RHEL, AlmaLinux, Rocky) are untested, and may not
  offer pandoc or PySide6 in their standard repositories.

## Installing

```sh
sudo dnf install ./markdown-cornell-notes-2.0.0-1.fc44.noarch.rpm
```

`dnf` brings in pandoc, latexmk, and the handful of TeX Live packages the
notes template uses, plus `python3-pyside6` for the editor app. The first
install downloads a few hundred megabytes of those if you don't have TeX
Live yet.

The package isn't signed. `dnf` installs a local file without a signature
check by default; if yours is configured to insist on one, add
`--nogpgcheck`.

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
itself: install a newer `.rpm` the same way when there is one. To remove
it, `sudo dnf remove markdown-cornell-notes`; your notes are untouched.

## Known issues

- **Ubuntu 24.04-style sandbox errors don't apply on Fedora**, but if the
  editor ever refuses to start with a message about its sandbox,
  `markdown-cornell-notes app APP_FLAGS=--no-sandbox` starts it without.
- **No spellcheck dictionary is included** (the AppImage has US English);
  the [editor app](https://github.com/forloop11/markdown-cornell-notes/blob/main/docs/editor-app.md)
  page says how to add one.
- **No application-menu entry**: start the editor with
  `markdown-cornell-notes app` from a project directory.

## License

MIT. The package contains only this project's own files; TeX Live, pandoc,
Python, and Qt come from Fedora's packages under their own licenses.
