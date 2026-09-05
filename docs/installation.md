# Installation

Three ways to install this outside of a git checkout, all packaging the
Makefile/scripts/template the same way and dropping a `markdown-cornell-notes`
launcher on the `PATH`: a `.deb`, a Homebrew formula, and a Docker image.

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

opens the [Streamlit editor app](streamlit-app.md) on that project;
running it (or `build`) outside an initialized directory fails with a clear
"run `markdown-cornell-notes init` first" message rather than a permission
error.

**Updating an existing install:** the package's version comes from `git
describe`, so rebuilding `make deb` without a new commit/tag produces a
`.deb` with the same filename and version as before. `sudo apt install` on
that file is then a no-op even though its contents changed — use `sudo dpkg
-i dist/markdown-cornell-notes_*.deb` instead, which reinstalls
unconditionally, and restart any already-running `markdown-cornell-notes
app` afterward (it keeps the old code loaded in memory until restarted).

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

This pulls in `pandoc` and `python@3.13` automatically, but not LaTeX
itself — MacTeX/BasicTeX are Homebrew *casks*, not formulas, and MacTeX
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
Unlike the other two, it bundles the [Streamlit editor app](streamlit-app.md)'s
`pip install` too, since there's no Debian/Homebrew-style "system package
manager" constraint to keep it out of Depends.

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
`clean`, `distclean`, `app`) — just append it after the image name, e.g.:

```sh
docker run --rm --user "$(id -u):$(id -g)" -p 8501:8501 -v "$PWD":/project markdown-cornell-notes app
```

opens the Streamlit editor on `http://localhost:8501` for that project
(the `-p` publishes the container's port; `app`'s `--server.address=0.0.0.0`
in the Makefile is what makes it reachable at all from outside the
container).

Typing the full `docker run --rm --user ... -v "$PWD":/project` prefix for
every command gets old fast — an `mcn` alias in your shell rc file
(`~/.bashrc`, `~/.zshrc`) collapses it down to the same `init`/`build`/`app`
commands as the `.deb`/Homebrew install:

```sh
alias mcn='docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/project markdown-cornell-notes'
alias mcn-app='docker run --rm --user "$(id -u):$(id -g)" -p 8501:8501 -v "$PWD":/project markdown-cornell-notes app'
```

```sh
mkdir ~/notes && cd ~/notes
mcn init
mcn build
mcn-app     # opens http://localhost:8501
```

`-v "$PWD":/project` means these only work from inside a project
directory (or a fresh one you're about to `init`) — same CWD-relative
requirement as the `.deb`'s `markdown-cornell-notes` launcher.
