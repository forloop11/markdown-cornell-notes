#!/bin/sh
# Packages this project into a .deb (dist/markdown-cornell-notes_<version>.deb).
# No compiled code here -- this just stages the pipeline (Makefile, scripts,
# settings, app) under /usr/share, drops a /usr/bin launcher, and declares
# the system deps (texlive, pandoc, latexmk) apt already knows about.
# The optional editor app is a PySide6 (Qt) desktop app (see `make app` in
# the Makefile): its Qt bindings are Recommends rather than Depends, since
# `make build` itself doesn't need them.
#
# Usage: scripts/build_deb.sh [version]   (or `make deb`)
# The version defaults to `git describe`'s (e.g. 2.0.0-3-gabc1234 a few
# commits after the v2.0.0 tag); pass one to name a release exactly.
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-$(git -C "$REPO_ROOT" describe --tags --always 2>/dev/null | sed 's/^v//')}"
VERSION="${VERSION:-0.0.0}"

DIST_DIR="$REPO_ROOT/dist"
PKG_NAME="markdown-cornell-notes"
DEB_IMAGE="docker.io/library/debian:trixie-slim" # only used without a dpkg-deb on the host
STAGE="$DIST_DIR/${PKG_NAME}_${VERSION}"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/share/$PKG_NAME" "$STAGE/usr/bin"

rsync -a \
  --exclude .git \
  --exclude build \
  --exclude dist \
  --exclude '__pycache__' \
  --exclude 'node_modules' \
  --exclude '.venv' \
  --exclude '.pytest_cache' \
  --exclude '.claude' \
  --exclude '.agents' \
  --exclude 'pdf/*.pdf' \
  "$REPO_ROOT/Makefile" "$REPO_ROOT/README.md" "$REPO_ROOT/LICENSE" \
  "$REPO_ROOT/scripts" "$REPO_ROOT/settings" "$REPO_ROOT/app" \
  "$REPO_ROOT/requirements-dev.txt" \
  "$REPO_ROOT/pytest.ini" "$REPO_ROOT/tests" \
  "$REPO_ROOT/md" "$REPO_ROOT/yaml" \
  "$REPO_ROOT/assets" "$REPO_ROOT/docs" \
  "$STAGE/usr/share/$PKG_NAME/"

cat > "$STAGE/usr/bin/$PKG_NAME" <<EOF
#!/bin/sh
# No -C: keep the caller's CWD as the project directory (see "make init")
# instead of running in place inside the root-owned /usr/share tree.
exec make -f /usr/share/$PKG_NAME/Makefile "\$@"
EOF
chmod 755 "$STAGE/usr/bin/$PKG_NAME"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG_NAME
Version: $VERSION
Section: text
Priority: optional
Architecture: all
Depends: python3, make, pandoc, latexmk, texlive-latex-extra, texlive-latex-recommended, texlive-pictures
Recommends: python3-pyside6.qtwidgets, python3-pyside6.qtsvg, python3-pyside6.qtwebchannel, python3-pyside6.qtwebenginewidgets
Maintainer: Todd C. Takala <todd.c.takala@gmail.com>
Description: Cornell-style meeting notes generator (LaTeX/Markdown)
 Generates Cornell-note-taking-system PDFs from YAML header files and
 Markdown content, with an optional desktop editor app (Qt).
EOF

DEB_FILE="$DIST_DIR/${PKG_NAME}_${VERSION}.deb"
if command -v dpkg-deb > /dev/null; then
  dpkg-deb --build --root-owner-group "$STAGE" "$DEB_FILE" >&2
else
  # Not a Debian-family host (e.g. Fedora): run dpkg-deb in a Debian
  # container instead, which has it built in.
  container="${CONTAINER:-$(command -v podman || command -v docker || true)}"
  if [ -z "$container" ]; then
    echo "Needs dpkg-deb, or podman or docker to run it in $DEB_IMAGE." >&2
    exit 1
  fi
  # label=disable: on SELinux hosts, lets the container read the bind
  # mount without relabeling the checkout.
  "$container" run --rm --security-opt label=disable -v "$DIST_DIR":/dist "$DEB_IMAGE" \
    dpkg-deb --build --root-owner-group "/dist/${PKG_NAME}_${VERSION}" "/dist/${PKG_NAME}_${VERSION}.deb" >&2
fi

echo "$DEB_FILE"
