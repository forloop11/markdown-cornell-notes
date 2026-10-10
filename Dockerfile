# Container equivalent of the .deb (see scripts/build_deb.sh): stages the
# Makefile, scripts, settings/template.tex, and app under
# /usr/share/markdown-cornell-notes (read-only, like an installed package)
# and drops a markdown-cornell-notes launcher on PATH. Depends list mirrors
# the .deb's Depends line in scripts/build_deb.sh.
#
# The image is for the CLI (`build`, `init`, ...) only: the editor app is a
# Qt desktop window, which has no display to open in here (and its PySide6
# dependency isn't installed). app/ is still staged so the image's file set
# matches the .deb's.
#
# trixie, not bookworm: bookworm's pandoc (2.17) predates the LaTeX writer
# change that emits \st{...} for strikethrough -- it emits \sout{...}
# instead, which settings/template.tex doesn't define (see its \st comment),
# so builds with any ~~strikethrough~~ fail with "Undefined control
# sequence". trixie's pandoc (3.1.x) matches what the .deb's Depends
# resolves to on current Debian/Ubuntu.
FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        make \
        pandoc \
        latexmk \
        texlive-latex-extra \
        texlive-latex-recommended \
        texlive-pictures \
        rsync \
    && rm -rf /var/lib/apt/lists/*

ENV PKG_NAME=markdown-cornell-notes
ENV MCN_ROOT=/usr/share/markdown-cornell-notes

# Same file set as build_deb.sh's rsync, staged straight into the image
# instead of a .deb payload. requirements-dev.txt/pytest.ini/tests/ are
# staged (not installed) so `make test` at least has something to run if
# invoked, once pytest is installed.
COPY Makefile README.md LICENSE requirements-dev.txt pytest.ini "$MCN_ROOT"/
COPY scripts "$MCN_ROOT"/scripts/
COPY settings "$MCN_ROOT"/settings/
COPY app "$MCN_ROOT"/app/
COPY tests "$MCN_ROOT"/tests/
COPY md "$MCN_ROOT"/md/
COPY yaml "$MCN_ROOT"/yaml/
COPY assets "$MCN_ROOT"/assets/
COPY docs "$MCN_ROOT"/docs/

RUN printf '#!/bin/sh\nexec make -f %s/Makefile "$@"\n' "$MCN_ROOT" \
        > /usr/bin/markdown-cornell-notes \
    && chmod 755 /usr/bin/markdown-cornell-notes

# No -C in the launcher above: like the .deb, the caller's CWD (this
# workdir, meant to be bind-mounted to a project directory on the host)
# stays the project directory instead of the read-only MCN_ROOT tree.
WORKDIR /project

ENTRYPOINT ["markdown-cornell-notes"]
CMD ["build"]
