#!/usr/bin/env bash
# Builds the Windows installer for the editor app (dist/windows/
# Markdown-Cornell-Notes-Setup-<version>.exe), bundling everything a build
# needs so the user installs nothing else:
#
#   resources/pipeline  scripts/, settings/template.tex, and the defaults
#                       `init` copies (same file set as the .deb's)
#   resources/python    the official embeddable CPython (stdlib only, which
#                       is all scripts/ uses)
#   resources/pandoc    pandoc.exe
#   resources/texlive   a TinyTeX (minimal TeX Live) tree with Windows
#                       binaries and just the packages settings/template.tex
#                       needs
#
# On Windows the app runs the build steps itself rather than `make build`
# (see Pipeline.buildDirect in app/lib/pipeline.js) -- no make, shell, or
# Perl needed, so latexmk isn't either.
#
# Runs on an x86_64 Linux host: the TeX tree is assembled with TinyTeX's
# own Linux tlmgr (installing packages, then `tlmgr platform add windows`
# for their Windows binaries), and electron-builder runs inside the
# electronuserland/builder:wine container (via podman or docker), which
# has the Wine that setting the .exe's icon and version info needs.
#
# Downloads are cached in dist/windows-cache/; delete it to start fresh.
# Usage: scripts/build_windows.sh   (or `make windows`)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="$ROOT/dist/windows-cache"
STAGE="$ROOT/dist/windows-stage"

TINYTEX_VERSION="v2026.10"
PANDOC_VERSION="3.12.1"
PYTHON_VERSION="3.13.16"
# Beyond TinyTeX-1's set: tikz (pgf) and the T1-encoded Type 1 fonts
# fontenc's T1 needs (cm-super) -- without the latter TeX would fall back
# to generating bitmap fonts, which needs tools this bundle leaves out.
TEX_PACKAGES="pgf cm-super"
BUILDER_IMAGE="docker.io/electronuserland/builder:wine"

mkdir -p "$CACHE"

download() { # url dest
  if [ ! -f "$2" ]; then
    echo "Downloading $(basename "$2")..."
    curl -fL --retry 3 -o "$2.part" "$1"
    mv "$2.part" "$2"
  fi
}

download "https://github.com/rstudio/tinytex-releases/releases/download/$TINYTEX_VERSION/TinyTeX-1-linux-x86_64-$TINYTEX_VERSION.tar.xz" \
  "$CACHE/TinyTeX-1-linux-$TINYTEX_VERSION.tar.xz"
download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-windows-x86_64.zip" \
  "$CACHE/pandoc-$PANDOC_VERSION-windows.zip"
download "https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-embed-amd64.zip" \
  "$CACHE/python-$PYTHON_VERSION-embed.zip"

# --- TeX: install packages + Windows binaries with the Linux tlmgr --------
# Rebuilt only when the TinyTeX version or package list changes.
TEX_TREE="$CACHE/tinytex/.TinyTeX"
TEX_STAMP="$CACHE/tinytex.stamp"
TEX_KEY="$TINYTEX_VERSION $TEX_PACKAGES windows"
if [ "$(cat "$TEX_STAMP" 2>/dev/null)" != "$TEX_KEY" ]; then
  echo "Preparing TeX tree..."
  rm -rf "$CACHE/tinytex" "$TEX_STAMP"
  mkdir -p "$CACHE/tinytex"
  tar -xJf "$CACHE/TinyTeX-1-linux-$TINYTEX_VERSION.tar.xz" -C "$CACHE/tinytex"
  tlmgr="$TEX_TREE/bin/x86_64-linux/tlmgr"
  "$tlmgr" update --self
  # shellcheck disable=SC2086
  "$tlmgr" install $TEX_PACKAGES
  "$tlmgr" platform add windows
  echo "$TEX_KEY" > "$TEX_STAMP"
fi

# --- Stage the app's extraResources (see "build" in app/package.json) -----
echo "Staging resources..."
rm -rf "$STAGE"
mkdir -p "$STAGE"/{pipeline,python,pandoc}

# The Linux binaries and tlmgr's own package database/Perl aren't needed
# to run pdflatex.
rsync -a --exclude '/bin/x86_64-linux/' --exclude '/tlpkg/' "$TEX_TREE/" "$STAGE/texlive/"

unzip -q -j "$CACHE/pandoc-$PANDOC_VERSION-windows.zip" \
  "pandoc-$PANDOC_VERSION/pandoc.exe" "pandoc-$PANDOC_VERSION/COPYRIGHT.txt" "pandoc-$PANDOC_VERSION/COPYING.rtf" \
  -d "$STAGE/pandoc"

unzip -q "$CACHE/python-$PYTHON_VERSION-embed.zip" -d "$STAGE/python"
# The embeddable build's ._pth file replaces sys.path outright -- so it no
# longer includes the running script's own directory, which scripts/ needs
# to import simple_yaml. Add that directory (relative to python.exe).
pth=("$STAGE"/python/python*._pth)
printf '%s\r\n' '..\pipeline\scripts' >> "${pth[0]}"

for f in scripts/*.py settings/template.tex settings/page.yaml md/notes-example.md yaml/notes-example.yaml assets/tux.jpg; do
  mkdir -p "$STAGE/pipeline/$(dirname "$f")"
  cp "$ROOT/$f" "$STAGE/pipeline/$f"
done

cp "$ROOT/LICENSE" "$STAGE/LICENSE.txt"
cat > "$STAGE/THIRD-PARTY-NOTICES.txt" <<EOF
Markdown Cornell Notes bundles the following third-party programs, each
distributed under its own license, unmodified, in the resources folder
next to this file.

pandoc $PANDOC_VERSION (resources/pandoc)
  Copyright (C) John MacFarlane and contributors.
  License: GNU GPL, version 2 or later -- see pandoc/COPYING.rtf and
  pandoc/COPYRIGHT.txt.
  Source code: https://github.com/jgm/pandoc/releases/tag/$PANDOC_VERSION

TeX Live, via TinyTeX $TINYTEX_VERSION (resources/texlive)
  A collection of free software under various licenses -- see
  texlive/LICENSE.TL and texlive/LICENSE.CTAN.
  Source code: https://tug.org/texlive/ and https://github.com/rstudio/tinytex-releases

Python $PYTHON_VERSION, embeddable distribution (resources/python)
  Copyright (C) Python Software Foundation.
  License: PSF License Agreement -- see python/LICENSE.txt.
  Source code: https://www.python.org/downloads/source/
EOF

# --- Package ---------------------------------------------------------------
container="${CONTAINER:-$(command -v podman || command -v docker || true)}"
if [ -z "$container" ]; then
  echo "Needs podman or docker to run electron-builder's Wine image ($BUILDER_IMAGE)." >&2
  exit 1
fi
if [ ! -d "$ROOT/app/node_modules/electron-builder" ]; then
  echo "Run 'npm ci' in app/ first." >&2
  exit 1
fi

echo "Packaging with electron-builder (in $BUILDER_IMAGE)..."
mkdir -p "$CACHE/builder-cache"
# label=disable: on SELinux hosts (e.g. Fedora), lets the container read
# the bind mounts without relabeling the checkout.
"$container" run --rm \
  --security-opt label=disable \
  -v "$ROOT":/project \
  -v "$CACHE/builder-cache":/root/.cache \
  -w /project/app \
  "$BUILDER_IMAGE" \
  npx electron-builder --win nsis --x64 --publish never

ls -lh "$ROOT"/dist/windows/*.exe
