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

opens the [editor app](editor-app.md) on that project (it needs PySide6 —
the package only Recommends the distribution's PySide6 packages, since
`build` doesn't; see the editor app's page for using a virtual environment
instead). Running `build` outside an
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
building it yourself, and describes the build this source tree makes — the
published release predates the app's move from Electron to Qt.

`make windows` builds a Windows installer for the editor app:

```sh
make windows                # -> dist/windows/Markdown-Cornell-Notes-Setup-<version>.exe
```

Copy the `.exe` to a Windows PC and run it. It installs for the current
user only (no administrator rights needed, under
`%LOCALAPPDATA%\Programs`), adds Start menu and desktop shortcuts, and
uninstalls from Settings > Apps like any other program. Nothing else needs
installing: the app bundles everything it and a build need — Python (the
official embeddable build), Qt (PySide6), pandoc, and a minimal TeX Live
([TinyTeX](https://github.com/rstudio/tinytex-releases) plus the packages
`settings/template.tex` uses). Their licenses are listed in
`THIRD-PARTY-NOTICES.txt` in the install folder's `resources`. The app
has no `.exe` of its own: its shortcuts start the bundled `pythonw.exe`
(Python without a console window) on `app/main.py`.

On first launch the app creates a project in `Documents\Cornell Notes`,
holding the example notes, and opens it. **File > Open Project Folder…**
switches to another folder (offering to set up a new project there if it
isn't one yet); the app reopens whichever folder you used last.

On Windows the app has no `make` or Unix shell to run `make build` with,
so Render runs the same steps itself: the three scripts in `scripts/`,
then `pdflatex` (rerun until LaTeX stops asking for another pass, as
latexmk would) — see `Pipeline.build_direct` in `app/pipeline.py`.
The output is the same PDF.

Building the installer needs an x86_64 Linux host — no Windows.
`scripts/build_windows.sh` downloads pinned versions of TinyTeX, pandoc,
Python, and PySide6's Windows wheels into `dist/bundle-cache/` (reused on
later runs, and shared with `make macos` and `make appimage`; the shared
steps live in `scripts/bundle_common.sh`), installs the extra TeX packages
and the TeX Windows binaries with TinyTeX's own Linux `tlmgr`, trims
PySide6 to the Qt modules the app uses (`scripts/bundle_prune_qt.py`), and
compiles the installer with [NSIS](https://nsis.sourceforge.io/)'s
`makensis` — the host's if it has one, else in a container (podman or
docker). The installer is about 270 MB.

The Windows build hasn't been run on Windows by this project's tooling:
it's checked only as far as a Linux host can — that the installer
compiles, and that nothing kept from Qt still refers to a module that was
trimmed away.

The installer isn't code-signed, so Windows SmartScreen shows an
"unrecognized app" warning the first time; choose **More info > Run
anyway**. Signing it needs a code-signing certificate, applied to the
`.exe` after the build (e.g. with `signtool` or `osslsigncode`).

## Installing the macOS app (Apple Silicon)

To just install it, download the zip from the
[macOS release](https://github.com/forloop11/markdown-cornell-notes/releases/tag/v1.0.1). The rest of this section covers
building it yourself, and describes the build this source tree makes — the
published release predates the app's move from Electron to Qt (and runs on
macOS 13).

`make macos` builds the editor app for Apple Silicon Macs (M1 and later,
macOS 14 or newer — what Qt's own builds need) as a zip, with the same
bundled Python, Qt, pandoc, and TeX as the Windows installer:

```sh
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
relocatable CPython (python.org has no embeddable macOS build), with
PySide6's macOS wheels installed into it. `scripts/build_macos.sh`
assembles the `.app` folder itself. Its executable is a small launcher
(`scripts/macos_launcher.c`) that starts the bundled Python on
`app/main.py`, cross-compiled with [zig](https://ziglang.org/) (a pinned
download, like the rest); then
[rcodesign](https://github.com/indygreg/apple-platform-rs/tree/main/apple-codesign)
ad-hoc signs every executable in it — Apple Silicon won't run code with no
signature at all. The zip is about 525 MB (Qt's macOS builds are
universal, carrying Intel code too).

The macOS build hasn't been run on a Mac by this project's tooling; it's
checked only for signatures, architecture, bundle layout, and that nothing
kept from Qt still refers to a module that was trimmed away. One thing to
expect until someone does: because the launcher hands over to the bundled
Python, the menu bar may name the app after Python rather than "Markdown
Cornell Notes".

## Running the Linux AppImage

To just run it, download the AppImage from the
[Linux release](https://github.com/forloop11/markdown-cornell-notes/releases/tag/v1.0.2). The rest of this section covers
building it yourself, and describes the build this source tree makes — the
published release predates the app's move from Electron to Qt (it needs
FUSE 2 to mount, and runs on older distributions).

`make appimage` builds the editor app for x86_64 Linux as an
[AppImage](https://appimage.org/): a single executable file with the same
bundled Python, Qt, pandoc, and TeX as the Windows and macOS builds, so it
needs no `make`, TeX Live, pandoc, Python, or PySide6 on the machine it
runs on.

```sh
make appimage               # -> dist/linux/Markdown-Cornell-Notes-<version>-x86_64.AppImage
                            #    and the .AppImage.zsync file next to it
```

There's nothing to install — make the file executable and run it:

```sh
chmod +x Markdown-Cornell-Notes-*-x86_64.AppImage
./Markdown-Cornell-Notes-*-x86_64.AppImage
```

To have it in your application menu instead, `make install-appimage`
copies the one you built to `~/Applications` (or `APPIMAGE_DIR`) and adds
a menu entry and icon for it, all for the current user only;
`make uninstall-appimage` removes them again.

Like the other standalone builds, it opens a project in
`~/Documents/Cornell Notes` on first launch, and **File > Open Project
Folder…** switches folders. To remove it, delete the file (your notes stay
where they are).

What it needs from the machine it runs on:

- **glibc 2.34 or newer** — Ubuntu 22.04, Debian 12, Fedora 35, RHEL 9, or
  later. That floor comes from Qt's own builds.
- **The usual desktop libraries** (X11/Wayland, OpenGL, fontconfig, NSS,
  ALSA), which a desktop install already has. The one that's commonly
  missing is `libxcb-cursor`, which Qt needs on X11 sessions: `sudo apt
  install libxcb-cursor0` on Debian/Ubuntu, `sudo dnf install
  xcb-util-cursor` on Fedora.
- **Nothing for mounting**: the AppImage's runtime is static, so unlike
  older AppImages it doesn't need the FUSE 2 library (`libfuse2`). Where
  FUSE isn't available at all (some containers),
  `./Markdown-Cornell-Notes-*-x86_64.AppImage --appimage-extract-and-run`
  unpacks it to `/tmp` and runs it from there instead.

If it stops with **an error about the sandbox** (Ubuntu 24.04 and later),
add `--no-sandbox`, as described in the
[editor app's Linux sandbox note](editor-app.md).

**Updates:** the AppImage carries update information pointing at this
project's latest GitHub release, so
[AppImageUpdate](https://github.com/AppImageCommunity/AppImageUpdate) and
similar tools can update it in place — provided each release publishes the
`.AppImage.zsync` file the build writes alongside the AppImage.

How it's built: `scripts/build_appimage.sh` stages the TeX tree's own
`x86_64-linux` binaries, pandoc's static Linux build, and
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)'s
relocatable CPython with PySide6's Linux wheels installed into it, then
packs that folder with
[appimagetool](https://github.com/AppImage/appimagetool). The file is about
335 MB. It has been run on Fedora: launched as the AppImage, and
driven through a Render with every system build tool hidden from `PATH`.

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
[editor app](editor-app.md) additionally needs PySide6 in a virtual
environment — the formula's caveats give the commands), but not
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
