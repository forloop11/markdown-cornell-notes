#!/bin/sh
# Packages this project into a .deb (dist/markdown-cornell-notes_<version>.deb).
# No compiled code here -- this just stages the pipeline (Makefile, scripts,
# settings, app) under /usr/share, drops a /usr/bin launcher, and declares
# the system deps (texlive, pandoc, latexmk) apt already knows about.
# Streamlit is pip-only in Debian, so it's left out of Depends -- see
# README.md's Streamlit editor app section.
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-$(git -C "$REPO_ROOT" describe --tags --always 2>/dev/null | sed 's/^v//')}"
VERSION="${VERSION:-0.0.0}"

DIST_DIR="$REPO_ROOT/dist"
PKG_NAME="markdown-cornell-notes"
STAGE="$DIST_DIR/${PKG_NAME}_${VERSION}"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/share/$PKG_NAME" "$STAGE/usr/bin"

rsync -a \
  --exclude .git \
  --exclude build \
  --exclude dist \
  --exclude '__pycache__' \
  --exclude 'node_modules' \
  --exclude '.claude' \
  --exclude '.agents' \
  --exclude 'pdf/*.pdf' \
  "$REPO_ROOT/Makefile" "$REPO_ROOT/README.md" "$REPO_ROOT/LICENSE" \
  "$REPO_ROOT/scripts" "$REPO_ROOT/settings" "$REPO_ROOT/app" \
  "$REPO_ROOT/requirements.txt" "$REPO_ROOT/md" "$REPO_ROOT/yaml" \
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
Suggests: python3-pip
Maintainer: Todd C. Takala <todd.c.takala@gmail.com>
Description: Cornell-style meeting notes generator (LaTeX/Markdown)
 Generates Cornell-note-taking-system PDFs from YAML header files and
 Markdown content, with an optional Streamlit editor UI (pip install
 streamlit separately).
EOF

DEB_FILE="$DIST_DIR/${PKG_NAME}_${VERSION}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB_FILE" >&2

echo "$DEB_FILE"
