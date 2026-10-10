# Installation

Three ways to install this outside of a git checkout, all packaging the
Makefile/scripts/template the same way and dropping a `markdown-cornell-notes`
launcher on the `PATH`: a `.deb`, a Homebrew formula, and a Docker image.
A standalone [editor app](editor-app.md) build — a
[Windows installer](#installing-on-windows), a
[macOS app](#installing-the-macos-app-apple-silicon) for Apple Silicon, or
a [Linux AppImage](#running-the-linux-appimage) — comes with everything it
needs bundled in.

## Installing as a system package

```sh
make deb                      # -> dist/markdown-cornell-notes_<version>.deb
sudo apt install ./dist/markdown-cornell-notes_*.deb
```

This stages the Makefile, scripts, `settings/template.tex`, and the app
under `/usr/share/markdown-cornell-notes` (read-only, like any installed
package) and drops a `markdown-cornell-notes` launcher in `/usr/bin`. Unlike
a git checkout, that install has nowhere writable of its own for your notes,
so each project lives in whatever directory you run the command from:

```sh
mkdir ~/notes && cd ~/notes
markdown-cornell-notes init    # scaffolds md/, yaml/, settings/page.yaml, pdf/, assets/ here
markdown-cornell-notes build   # same as `make build`
```

`markdown-cornell-notes` is just `make` pointed at the installed Makefile —
every target (`build`, `build-example`, `clean`, `distclean`, `app`) works
the same way from inside a project directory, e.g.:

```sh
cd ~/notes
markdown-cornell-notes app
```

opens the [editor app](editor-app.md) on that project (it needs Node.js and
npm — the package only Recommends them, since `build` doesn't; the first
run downloads Electron into your npm cache). Running `build` outside an
initialized directory fails with a clear "run `markdown-cornell-notes init`
first" message rather than a permission error, and the app shows the same
advice in its window.

**Updating an existing install:** the package's version comes from `git
describe`, so rebuilding `make deb` without a new commit/tag produces a
`.deb` with the same filename and version as before. `sudo apt install` on
that file is then a no-op even though its contents changed — use `sudo dpkg
-i dist/markdown-cornell-notes_*.deb` instead, which reinstalls
unconditionally, and close and reopen any already-running editor app
afterward (it keeps the old code loaded in memory until restarted).

## Installing on Windows

To just install it, download the installer from the
[Windows release](https://github.com/forloop11/markdown-cornell-notes/releases/tag/v1.0.0). The rest of this section covers
building it yourself.

`make windows` builds a Windows installer for the editor app:

```sh
cd app && npm ci && cd ..   # once, for electron-builder
make windows                # -> dist/windows/Markdown-Cornell-Notes-Setup-<version>.exe
```

Copy the `.exe` to a Windows PC and run it. It installs for the current
user only (no administrator rights needed, under
`%LOCALAPPDATA%\Programs`), adds Start menu and desktop shortcuts, and
uninstalls from Settings > Apps like any other program. Nothing else needs
installing: the app bundles everything a build needs — Python (the
official embeddable build), pandoc, and a minimal TeX Live
([TinyTeX](https://github.com/rstudio/tinytex-releases) plus the packages
`settings/template.tex` uses). Their licenses are listed in
`THIRD-PARTY-NOTICES.txt` in the install folder's `resources`.

On first launch the app creates a project in `Documents\Cornell Notes`,
holding the example notes, and opens it. **File > Open Project Folder…**
switches to another folder (offering to set up a new project there if it
isn't one yet); the app reopens whichever folder you used last.

On Windows the app has no `make` or Unix shell to run `make build` with,
so Render runs the same steps itself: the three scripts in `scripts/`,
then `pdflatex` (rerun until LaTeX stops asking for another pass, as
latexmk would) — see `Pipeline.buildDirect` in `app/lib/pipeline.js`.
The output is the same PDF.

Building the installer needs an x86_64 Linux host with podman or docker.
`scripts/build_windows.sh` downloads pinned versions of TinyTeX, pandoc,
and Python into `dist/bundle-cache/` (reused on later runs, and shared
with `make macos`; the shared steps live in `scripts/bundle_common.sh`),
installs the
extra TeX packages and the TeX Windows binaries with TinyTeX's own Linux
`tlmgr`, then runs [electron-builder](https://www.electron.build/) inside
its `electronuserland/builder:wine` image to produce the NSIS installer.
The installer is about 285 MB.

The installer isn't code-signed, so Windows SmartScreen shows an
"unrecognized app" warning the first time; choose **More info > Run
anyway**. Signing it needs a code-signing certificate — see
electron-builder's [Windows code signing](https://www.electron.build/code-signing-win)
docs, which this build's `win` settings in `app/package.json` can pick up.

## Installing the macOS app (Apple Silicon)

To just install it, download the zip from the
[macOS release](https://github.com/forloop11/markdown-cornell-notes/releases/tag/v1.0.1). The rest of this section covers
building it yourself.

`make macos` builds the editor app for Apple Silicon Macs (M1 and later,
macOS 13 or newer) as a zip, with the same bundled Python, pandoc, and TeX
as the Windows installer:

```sh
cd app && npm ci && cd ..   # once, for electron-builder
make macos                  # -> dist/macos/Markdown-Cornell-Notes-<version>-arm64-mac.zip
```

On the Mac, unzip it and drag **Markdown Cornell Notes** into
**Applications**. Like the Windows build, it opens a project in
`Documents/Cornell Notes` on first launch (macOS asks once for permission
to use the Documents folder), and **File > Open Project Folder…** switches
folders.

**First launch:** this build is only *ad-hoc* signed, not signed with an
Apple Developer ID or notarized, so macOS blocks it the first time with a
message that Apple couldn't verify it. Click **Done**, then open
**System Settings > Privacy & Security**, scroll to the message about
Markdown Cornell Notes, and click **Open Anyway**. Alternatively, clear
the download's quarantine flag in Terminal:

```sh
xattr -dr com.apple.quarantine "/Applications/Markdown Cornell Notes.app"
```

After that it opens normally. A smooth first launch needs a Developer ID
signature and notarization, which need an Apple Developer account.

How it's built: everything happens on the same x86_64 Linux host as
`make windows` — no Mac needed. TinyTeX's Linux `tlmgr` adds TeX Live's
`universal-darwin` binaries to the shared TeX tree; pandoc is its official
arm64 macOS build; Python is
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)'s
relocatable CPython (python.org has no embeddable macOS build).
electron-builder assembles the `.app` in its container image, then
[rcodesign](https://github.com/indygreg/apple-platform-rs/tree/main/apple-codesign)
ad-hoc signs every executable in it — Apple Silicon won't run code with no
signature at all. The zip is about 350 MB. The macOS build hasn't been run
on a Mac by this project's tooling; it's checked only for signatures,
architecture, and bundle layout.

## Running the Linux AppImage

To just run it, download the AppImage from the
[Linux release](https://github.com/forloop11/markdown-cornell-notes/releases/tag/v1.0.2). The rest of this section covers
building it yourself.

`make appimage` builds the editor app for x86_64 Linux as an
[AppImage](https://appimage.org/): a single executable file with the same
bundled Python, pandoc, and TeX as the Windows and macOS builds, so it
needs no `make`, TeX Live, pandoc, Python, or Node.js on the machine it
runs on.

```sh
cd app && npm ci && cd ..   # once, for electron-builder
make appimage               # -> dist/linux/Markdown-Cornell-Notes-<version>-x86_64.AppImage
```

There's nothing to install — make the file executable and run it:

```sh
chmod +x Markdown-Cornell-Notes-*-x86_64.AppImage
./Markdown-Cornell-Notes-*-x86_64.AppImage
```

Like the other standalone builds, it opens a project in
`~/Documents/Cornell Notes` on first launch, and **File > Open Project
Folder…** switches folders. To remove it, delete the file (your notes stay
where they are).

Two things can stop an AppImage from starting, depending on the
distribution:

- **"AppImages require FUSE to run"** (`error loading libfuse.so.2`):
  mounting an AppImage needs the FUSE 2 library, which newer
  distributions don't install by default. Install it (`sudo dnf install
  fuse-libs` on Fedora, `sudo apt install libfuse2t64` — or `libfuse2` on
  older releases — on Debian/Ubuntu), or skip mounting altogether with
  `./Markdown-Cornell-Notes-*-x86_64.AppImage --appimage-extract-and-run`
  (slower to start: it unpacks about 800 MB to `/tmp` each time).
- **An error about the sandbox** (Ubuntu 24.04 and later): add
  `--no-sandbox`, as described in the
  [editor app's Linux sandbox note](editor-app.md).

How it's built: `scripts/build_appimage.sh` stages the TeX tree's own
`x86_64-linux` binaries, pandoc's static Linux build, and
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)'s
relocatable CPython, then runs electron-builder's `AppImage` target in the
same container image as the other builds. The file is about 325 MB.
It has been run end to end on Fedora (Render with every system build tool
hidden from `PATH`), and its bundled Python, pandoc, and TeX also build
the example in a bare Debian 11 container.

## Installing on macOS (Homebrew)

`Formula/markdown-cornell-notes.rb` packages this the same way as the
`.deb` above: everything lands in a private prefix (Homebrew's Cellar
instead of `/usr/share`) and a thin `markdown-cornell-notes` wrapper on the
`PATH` runs `make -f <prefix>/Makefile`, so builds happen in whatever
directory you invoke it from.

No tagged release includes the CWD-relative build fixes yet, so install
straight from `main` for now:

```sh
brew install --HEAD ./Formula/markdown-cornell-notes.rb   # from a checkout of this repo
```

or, without cloning first:

```sh
brew install --HEAD https://raw.githubusercontent.com/forloop11/markdown-cornell-notes/main/Formula/markdown-cornell-notes.rb
```

This pulls in `pandoc` and `python@3.13` automatically (the optional
[editor app](editor-app.md) additionally needs `brew install node`), but not
LaTeX itself — MacTeX/BasicTeX are Homebrew *casks*, not formulas, and MacTeX
alone is several GB. `brew install` prints exact `tlmgr` instructions for
the lightweight BasicTeX path after installing; see the formula's
`caveats` (or run `brew info markdown-cornell-notes`) if you miss them.

Once a release is tagged, `brew install markdown-cornell-notes` (no
`--HEAD`) will work from a proper versioned tarball instead — the formula
has a comment marking where to fill in the new `url`/`sha256`.

## Running with Docker

`Dockerfile` packages this the same way as the `.deb`/Homebrew formula
above (see [Installing as a system package](#installing-as-a-system-package)):
everything lands under `/usr/share/markdown-cornell-notes` and a thin
`markdown-cornell-notes` wrapper on `PATH` runs `make -f <that>/Makefile`.
It's for the CLI only: the [editor app](editor-app.md) is a desktop window,
and a container has no display to open it in — install the `.deb` or
Homebrew formula (or use a git checkout) for that.

Build the image, then bind-mount a project directory at `/project` (the
image's `WORKDIR`) and pass `--user "$(id -u):$(id -g)"` so generated files
are owned by you, not root:

```sh
docker build -t markdown-cornell-notes .

mkdir ~/notes && cd ~/notes
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/project markdown-cornell-notes init
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/project markdown-cornell-notes build
```

The image's `ENTRYPOINT` is `markdown-cornell-notes` itself, so any command
works the same way `make <target>` does above (`build`, `build-example`,
`clean`, `distclean`) — just append it after the image name, e.g.:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/project markdown-cornell-notes build-example
```

Typing the full `docker run --rm --user ... -v "$PWD":/project` prefix for
every command gets old fast — an `mcn` alias in your shell rc file
(`~/.bashrc`, `~/.zshrc`) collapses it down to the same `init`/`build`
commands as the `.deb`/Homebrew install:

```sh
alias mcn='docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/project markdown-cornell-notes'
```

```sh
mkdir ~/notes && cd ~/notes
mcn init
mcn build
```

`-v "$PWD":/project` means these only work from inside a project
directory (or a fresh one you're about to `init`) — same CWD-relative
requirement as the `.deb`'s `markdown-cornell-notes` launcher.
