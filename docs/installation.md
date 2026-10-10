# Installation

Four ways to install this outside of a git checkout, all packaging the
Makefile/scripts/template the same way and dropping a `markdown-cornell-notes`
launcher on the `PATH`: a `.deb`, an
[RPM](#installing-on-fedora-and-rhel-family-systems-rpm), a Homebrew
formula, and a Docker image.
A standalone [editor app](editor-app.md) build — a
[Windows installer](#installing-on-windows), a
[macOS app](#installing-the-macos-app-apple-silicon) for Apple Silicon, a
[Linux AppImage](#running-the-linux-appimage), or a
[snap](#building-the-snap) — comes with everything it needs bundled in.

## Installing as a system package

To just install it, download the `.deb` from the
[v2.0.0 release](https://github.com/forloop11/markdown-cornell-notes/releases/tag/v2.0.0); its
[release notes](release-notes/deb-2.0.0.md) cover installing it. To build
it yourself:

```sh
make deb                      # -> dist/markdown-cornell-notes_<version>.deb
sudo apt install ./dist/markdown-cornell-notes_*.deb
```

`make deb` works on any host: without `dpkg-deb` (e.g. on Fedora) it runs
it in a Debian container, with podman or docker. The version comes from
`git describe`; `scripts/build_deb.sh 2.0.0` names one exactly.

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

## Installing on Fedora and RHEL-family systems (RPM)

`make rpm` builds the RPM counterpart of the `.deb`, from
`markdown-cornell-notes.spec`:

```sh
make rpm                      # -> dist/rpm/markdown-cornell-notes-<version>-1.<dist>.noarch.rpm
sudo dnf install ./dist/rpm/markdown-cornell-notes-*.noarch.rpm
```

It's laid out and used exactly like the `.deb` above — everything under
`/usr/share/markdown-cornell-notes`, a `markdown-cornell-notes` launcher,
one project per directory. `dnf` brings in what a build needs (pandoc,
latexmk, and the handful of TeX Live packages the template uses, by name
rather than a whole TeX scheme) and, as a weak dependency, `python3-pyside6`
for the [editor app](editor-app.md). Building the package needs `rpmbuild`
(`sudo dnf install rpm-build`), or podman or docker to run it in a Fedora
container.

It has been installed in a clean Fedora 44 container, where it built the
example PDF with only the dependencies `dnf` resolved, and the app's tests
pass against Fedora's own PySide6 (6.11).

### Publishing it with COPR

[COPR](https://copr.fedorainfracloud.org/) is Fedora's free service for
personal package repositories; with a project there, people install with

```sh
sudo dnf copr enable forloop11/markdown-cornell-notes
sudo dnf install markdown-cornell-notes
```

and get new versions through `dnf upgrade`. Those commands fail with a 404
until the project exists and has a finished build. To set it up, once:

1. Push this repository's `markdown-cornell-notes.spec` and
   `.copr/Makefile` to GitHub (COPR builds from what's there, not from
   your working copy).
2. Sign in to [copr.fedorainfracloud.org](https://copr.fedorainfracloud.org/)
   with a [Fedora account](https://accounts.fedoraproject.org/).
3. **New Project**: name it `markdown-cornell-notes`, and tick the build
   targets to offer it for — e.g. the current `fedora-*-x86_64` releases
   (the package is the same for every architecture, so one per release is
   enough).
4. In the project, **Packages > New Package**: source type **SCM**, clone
   URL `https://github.com/forloop11/markdown-cornell-notes.git`, spec
   file `markdown-cornell-notes.spec`, and **make srpm** as the way to
   build the source RPM. That last choice runs `.copr/Makefile`, which
   packs the repository at the commit being built.
5. **Rebuild** the package. When the build goes green, the `dnf` commands
   above work.

For later versions: change `Version` in the spec (keeping it in step with
`app/package.json`; `make rpm` checks), add a `%changelog` entry, push,
and rebuild in COPR — or turn on the package's auto-rebuild option with a
GitHub webhook to have a push do it.

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
signature and notarization, which need an Apple Developer account — see
[Signing and notarizing](#signing-and-notarizing-the-macos-app) below.

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

### Signing and notarizing the macOS app

With an [Apple Developer](https://developer.apple.com/programs/) account,
`make macos` can sign the app with your Developer ID and have Apple
notarize it, so it opens on other people's Macs with no warning to get
past. It does so when three environment variables name the credentials;
without them it ad-hoc signs as described above. All of it runs on the
Linux build host.

One-time setup — keep every file it produces **outside the repository**
(they are your signing identity):

1. **Make a private key and a certificate signing request:**

   ```sh
   rcodesign=dist/bundle-cache/apple-codesign-*/rcodesign    # downloaded by `make macos`
   openssl genrsa -out developer-id.key 2048
   $rcodesign generate-certificate-signing-request \
     --pem-file developer-id.key --csr-pem-file developer-id.csr
   ```

2. **Get the certificate.** At
   [developer.apple.com/account](https://developer.apple.com/account) >
   Certificates, add a certificate of type **Developer ID Application**
   (only the account holder can), upload `developer-id.csr`, and download
   the `.cer` file it gives you.

3. **Combine the certificate and key into a `.p12`,** with a password of
   your choosing, saved in a file of its own:

   ```sh
   openssl x509 -inform DER -in developerID_application.cer -out developer-id.pem
   openssl pkcs12 -export -inkey developer-id.key -in developer-id.pem -out developer-id.p12
   ```

4. **Make an App Store Connect API key,** which is what submits the app
   for notarization: at
   [appstoreconnect.apple.com](https://appstoreconnect.apple.com) > Users
   and Access > Integrations, create a key (the Developer role is enough)
   and download its `.p8` file — it's offered once. Note the key ID and
   the issuer ID shown there, then:

   ```sh
   $rcodesign encode-app-store-connect-api-key -o notary-key.json \
     <issuer ID> <key ID> AuthKey_<key ID>.p8
   ```

Then, for each build:

```sh
export MACOS_SIGN_P12=~/keys/developer-id.p12
export MACOS_SIGN_P12_PASSWORD_FILE=~/keys/developer-id.password
export MACOS_NOTARY_API_KEY=~/keys/notary-key.json
make macos
```

The build signs every executable in the app with the hardened runtime
(which notarization requires), giving the ones that run the app — the
bundled Python and Qt's WebEngine helper — the entitlements in
`scripts/macos_entitlements.plist` that Chromium's JavaScript engine
needs. It then uploads the app to Apple, waits for the verdict (usually a
few minutes), staples the approval to the `.app`, and zips it. With
`MACOS_NOTARY_API_KEY` unset, it signs but skips notarization.

If Apple rejects the submission, the build stops with a submission ID;
`$rcodesign notary-log --api-key-file notary-key.json <submission ID>`
prints what it objected to.

This path has been exercised only as far as a Linux host without Apple
credentials can take it: with a self-made test certificate, every program
in the bundle comes out signed with the hardened runtime and the right
entitlements. Signing with a real Developer ID, notarization itself, and —
above all — running the result on a Mac are untested. The hardened runtime
is strict, so expect that a first run on a Mac may turn up a program that
needs another entitlement.

## Running the Linux AppImage

To just run it, download the AppImage from the
[Linux release](https://github.com/forloop11/markdown-cornell-notes/releases/tag/v2.1.0); its
[release notes](release-notes/linux-2.1.0.md) cover running it. The rest
of this section covers building it yourself. (Version 1.0, the
[earlier Electron-based release](https://github.com/forloop11/markdown-cornell-notes/releases/tag/v1.0.2), runs on older
distributions but needs FUSE 2 to mount.)

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

## Building the snap

`snap/snapcraft.yaml` packages the editor app as a
[snap](https://snapcraft.io/), for the Snap Store. It wraps the same
self-contained bundle as the AppImage — Python, Qt, pandoc, TeX, and the
app — so it needs nothing else installed.

**This packaging hasn't been built or run yet**: it's written to
snapcraft's documentation, and the first build is the test. The parts
most likely to need adjusting are noted below.

Build it with [snapcraft](https://snapcraft.io/docs/snapcraft), which
runs most smoothly on Ubuntu:

```sh
snapcraft                                                   # -> markdown-cornell-notes_<version>_amd64.snap
sudo snap install --dangerous ./markdown-cornell-notes_*.snap    # --dangerous: a local file, not from the store
markdown-cornell-notes
```

Without an Ubuntu machine, the **Snap** workflow in GitHub Actions builds
it: run it from the repository's Actions tab, then download the `.snap`
from the run's artifacts. It only builds; it publishes nothing.

To publish, make a free account at [snapcraft.io](https://snapcraft.io),
then:

```sh
snapcraft login
snapcraft register markdown-cornell-notes    # once: claims the name
snapcraft upload --release=stable ./markdown-cornell-notes_*.snap
```

How it differs from the AppImage, being confined:

- **Notes folder:** as usual it opens `Documents/Cornell Notes`, in your
  real home folder. It can open any other folder in your home that isn't
  hidden (the `home` interface); for notes on an external drive, run
  `sudo snap connect markdown-cornell-notes:removable-media` once.
- **Chromium's sandbox is off** inside the snap (it can't be set up under
  confinement); the snap's own confinement stands in for it. So there's no
  `--no-sandbox` to add on Ubuntu 24.04.
- **Desktop libraries** come from the GNOME runtime snap, plus the handful
  of packages listed under `stage-packages`. If the app fails to start
  with a missing-library error, that list is where to add it.
- **Its own settings** are kept under `~/snap/markdown-cornell-notes/`.

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
