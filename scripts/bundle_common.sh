# Shared by scripts/build_windows.sh, build_macos.sh, and
# build_appimage.sh (sourced, not run): pinned versions, the download
# cache, the TeX tree, and staging the pieces every platform's bundle has
# in common.
#
# Every bundle carries a resources folder holding:
#
#   pipeline/  the editor app (app/), scripts/, settings/template.tex, and
#              the defaults `init` copies (same file set as the .deb's)
#   python/    a self-contained CPython, with PySide6 (Qt) installed into
#              it and pruned to the modules the app uses. It runs the app
#              and, from the app, scripts/ (stdlib only)
#   pandoc/    the pandoc binary
#   texlive/   a TinyTeX (minimal TeX Live) tree with that platform's
#              binaries and just the packages settings/template.tex needs
#   qtwebengine_dictionaries/
#              the editor's en-US spellcheck dictionary
#
# app/main.py recognizes that layout (pandoc/ and texlive/ next to
# pipeline/) as a standalone build. The app runs the build steps itself
# there rather than `make build` (see Pipeline.build_direct in
# app/pipeline.py) -- no make, shell, or Perl needed, so latexmk isn't
# either.
#
# Everything is assembled on an x86_64 Linux host, for all three targets:
# pip installs PySide6's wheels for the target platform (they're prebuilt,
# so nothing is compiled), and the TeX tree is put together once with
# TinyTeX's own Linux tlmgr: install the extra packages, then `tlmgr
# platform add` each target platform's binaries. Downloads are cached in
# dist/bundle-cache/; delete it to start fresh.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="$ROOT/dist/bundle-cache"

TINYTEX_VERSION="v2026.10"
PANDOC_VERSION="3.12.1"
PYTHON_VERSION="3.13.16"
# Beyond TinyTeX-1's set: tikz (pgf) and the T1-encoded Type 1 fonts
# fontenc's T1 needs (cm-super) -- without the latter TeX would fall back
# to generating bitmap fonts, which needs tools these bundles leave out.
TEX_PACKAGES="pgf cm-super"
# The platforms the TeX tree carries binaries for beyond x86_64-linux (its
# own, which the AppImage bundles); each bundle copies just its own
# bin/<platform>.
TEX_PLATFORMS="windows universal-darwin"
# python-build-standalone's relocatable CPython: the Linux and macOS
# bundles' Python, and (the Linux one) what runs pip for all three.
PBS_RELEASE="20261009" # the release carrying $PYTHON_VERSION
# PySide6-WebEngine's version; pip resolves the PySide6-Addons,
# PySide6-Essentials, and shiboken6 it goes with.
PYSIDE_VERSION="6.12.0.140"
TZDATA_VERSION="2026.5"
# chromium/deps/hunspell_dictionaries: the commit and file the en-US
# spellcheck dictionary comes from.
DICTIONARY_COMMIT="cee14e319bb7603a1157bb4d1e216be64ee82b77"
DICTIONARY_FILE="en-US-10-2.bdic"

APP_VERSION="$(sed -n 's/^  "version": "\(.*\)",$/\1/p' "$ROOT/app/package.json")"

mkdir -p "$CACHE"

download() { # url dest
  if [ ! -f "$2" ]; then
    echo "Downloading $(basename "$2")..."
    curl -fL --retry 3 -o "$2.part" "$1"
    mv "$2.part" "$2"
  fi
}

TEX_TREE="$CACHE/tinytex/.TinyTeX"

# Build (or reuse) the shared TeX tree. Rebuilt only when the TinyTeX
# version, package list, or platform list changes.
prepare_tex() {
  local stamp="$CACHE/tinytex.stamp" key="$TINYTEX_VERSION $TEX_PACKAGES $TEX_PLATFORMS"
  download "https://github.com/rstudio/tinytex-releases/releases/download/$TINYTEX_VERSION/TinyTeX-1-linux-x86_64-$TINYTEX_VERSION.tar.xz" \
    "$CACHE/TinyTeX-1-linux-$TINYTEX_VERSION.tar.xz"
  if [ "$(cat "$stamp" 2>/dev/null)" = "$key" ]; then return; fi
  echo "Preparing TeX tree..."
  rm -rf "$CACHE/tinytex" "$stamp"
  mkdir -p "$CACHE/tinytex"
  tar -xJf "$CACHE/TinyTeX-1-linux-$TINYTEX_VERSION.tar.xz" -C "$CACHE/tinytex"
  local tlmgr="$TEX_TREE/bin/x86_64-linux/tlmgr" platform
  "$tlmgr" update --self
  # shellcheck disable=SC2086
  "$tlmgr" install $TEX_PACKAGES
  for platform in $TEX_PLATFORMS; do "$tlmgr" platform add "$platform"; done
  echo "$key" > "$stamp"
}

# stage_texlive <dest> <platform>: the TeX tree with only <platform>'s
# binaries -- tlmgr's own package database and Perl (tlpkg/) aren't needed
# to run pdflatex.
stage_texlive() {
  rsync -a --exclude '/bin/' --exclude '/tlpkg/' "$TEX_TREE/" "$1/"
  mkdir -p "$1/bin"
  rsync -a "$TEX_TREE/bin/$2" "$1/bin/"
}

# stage_pipeline <dest>
stage_pipeline() {
  local f
  # (app/package.json: where the app reads its version from.)
  for f in app/*.py app/package.json app/web/* app/build-resources/* scripts/*.py settings/template.tex settings/page.yaml \
    md/notes-example.md yaml/notes-example.yaml assets/tux.jpg; do
    mkdir -p "$1/$(dirname "$f")"
    cp "$ROOT/$f" "$1/$f"
  done
}

# The Linux CPython, unpacked in the cache as the build's own Python.
BUILD_PYTHON_HOME="$CACHE/build-python-$PYTHON_VERSION-$PBS_RELEASE"
BUILD_PYTHON="$BUILD_PYTHON_HOME/python/bin/python3"
PBS_LINUX_TARBALL="$CACHE/cpython-$PYTHON_VERSION-$PBS_RELEASE-x86_64-unknown-linux-gnu.tar.gz"

prepare_build_python() {
  download "https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_RELEASE/cpython-$PYTHON_VERSION%2B$PBS_RELEASE-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz" \
    "$PBS_LINUX_TARBALL"
  if [ ! -x "$BUILD_PYTHON" ]; then
    mkdir -p "$BUILD_PYTHON_HOME"
    tar -xzf "$PBS_LINUX_TARBALL" -C "$BUILD_PYTHON_HOME"
  fi
}

# stage_pyside <site-packages dir> <pip platform tag> [more pip packages...]:
# PySide6 for that platform (its wheels come from pip's cache after the
# first build), minus the Qt modules the app doesn't use.
stage_pyside() {
  local site="$1" platform="$2"
  shift 2
  prepare_build_python
  echo "Installing PySide6 $PYSIDE_VERSION ($platform)..."
  mkdir -p "$site"
  PIP_CACHE_DIR="$CACHE/pip" "$BUILD_PYTHON" -m pip install --quiet --disable-pip-version-check \
    --target "$site" --platform "$platform" --python-version "${PYTHON_VERSION%.*}" \
    --only-binary=:all: --no-compile \
    "PySide6-WebEngine==$PYSIDE_VERSION" "$@"
  # pip's --target leaves console-script launchers behind; nothing uses them.
  rm -rf "${site:?}/bin"
  "$BUILD_PYTHON" "$ROOT/scripts/bundle_prune_qt.py" "$site"
}

# stage_dictionary <resources dir>
stage_dictionary() {
  local file="$CACHE/hunspell-$DICTIONARY_COMMIT-$DICTIONARY_FILE"
  if [ ! -f "$file" ]; then
    echo "Downloading $DICTIONARY_FILE..."
    curl -fL --retry 3 \
      "https://chromium.googlesource.com/chromium/deps/hunspell_dictionaries/+/$DICTIONARY_COMMIT/$DICTIONARY_FILE?format=TEXT" |
      base64 -d > "$file.part"
    mv "$file.part" "$file"
  fi
  mkdir -p "$1/qtwebengine_dictionaries"
  cp "$file" "$1/qtwebengine_dictionaries/en-US.bdic"
}

# write_notices <dest file> <python description> <python license file>
write_notices() {
  cat > "$1" <<EOF
Markdown Cornell Notes bundles the following third-party programs, each
distributed under its own license, unmodified, in the resources folder
next to this file.

pandoc $PANDOC_VERSION (resources/pandoc)
  Copyright (C) John MacFarlane and contributors.
  License: GNU GPL, version 2 or later -- see pandoc/COPYING* and
  pandoc/COPYRIGHT*.
  Source code: https://github.com/jgm/pandoc/releases/tag/$PANDOC_VERSION

TeX Live, via TinyTeX $TINYTEX_VERSION (resources/texlive)
  A collection of free software under various licenses -- see
  texlive/LICENSE.TL and texlive/LICENSE.CTAN.
  Source code: https://tug.org/texlive/ and https://github.com/rstudio/tinytex-releases

Python $PYTHON_VERSION, $2 (resources/python)
  Copyright (C) Python Software Foundation.
  License: PSF License Agreement -- see $3.
  Source code: https://www.python.org/downloads/source/

Qt 6 and Qt for Python (PySide6) $PYSIDE_VERSION (in resources/python's
site-packages, as PySide6 and shiboken6)
  Copyright (C) The Qt Company Ltd. and other contributors.
  License: GNU LGPL, version 3 (Qt WebEngine: LGPL v3 with parts under
  other licenses, including the Chromium project's BSD-style license) --
  see https://doc.qt.io/qt-6/licensing.html and
  https://doc.qt.io/qt-6/qtwebengine-licensing.html. The libraries are
  separate files that you may replace with your own builds.
  Source code: https://download.qt.io/official_releases/qt/ and
  https://download.qt.io/official_releases/QtForPython/

en-US spellcheck dictionary (resources/qtwebengine_dictionaries)
  Derived from SCOWL (http://wordlist.aspell.net/), via the Chromium
  project's hunspell_dictionaries -- see its README_en_US.txt for the
  copyright notices and (permissive) license terms:
  https://chromium.googlesource.com/chromium/deps/hunspell_dictionaries/+/$DICTIONARY_COMMIT/README_en_US.txt

CodeMirror 6 (compiled into pipeline/app/web/editor.js)
  Copyright (C) Marijn Haverbeke and others. License: MIT.
  Source code: https://github.com/codemirror

PDF.js (compiled into pipeline/app/web/pdfviewer.js, with its
pdf_viewer.css)
  Copyright (C) Mozilla Foundation. License: Apache License 2.0 --
  https://www.apache.org/licenses/LICENSE-2.0
  Source code: https://github.com/mozilla/pdf.js
EOF
}
