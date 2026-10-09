# Shared by scripts/build_windows.sh and scripts/build_macos.sh (sourced,
# not run): pinned versions, the download cache, the TeX tree, and staging
# the pieces both platforms' bundles have in common.
#
# Every bundle carries, as electron-builder extraResources (see "build" in
# app/package.json):
#
#   pipeline/  scripts/, settings/template.tex, and the defaults `init`
#              copies (same file set as the .deb's)
#   python/    a self-contained CPython (stdlib only, which is all
#              scripts/ uses)
#   pandoc/    the pandoc binary
#   texlive/   a TinyTeX (minimal TeX Live) tree with that platform's
#              binaries and just the packages settings/template.tex needs
#
# The packaged app runs the build steps itself rather than `make build`
# (see Pipeline.buildDirect in app/lib/pipeline.js) -- no make, shell, or
# Perl needed, so latexmk isn't either.
#
# The TeX tree is assembled once, on an x86_64 Linux host, with TinyTeX's
# own Linux tlmgr: install the extra packages, then `tlmgr platform add`
# each target platform's binaries. Downloads are cached in
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
# Every platform the TeX tree carries binaries for; each bundle copies
# just its own bin/<platform>.
TEX_PLATFORMS="windows universal-darwin"
BUILDER_IMAGE="docker.io/electronuserland/builder:wine"

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
  for f in scripts/*.py settings/template.tex settings/page.yaml md/notes-example.md yaml/notes-example.yaml assets/tux.jpg; do
    mkdir -p "$1/$(dirname "$f")"
    cp "$ROOT/$f" "$1/$f"
  done
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
EOF
}

# run_builder <electron-builder args...>: electron-builder inside its
# container image (podman or docker), which has the Wine that editing a
# Windows .exe's icon and version info needs.
run_builder() {
  local container="${CONTAINER:-$(command -v podman || command -v docker || true)}"
  if [ -z "$container" ]; then
    echo "Needs podman or docker to run electron-builder's image ($BUILDER_IMAGE)." >&2
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
    npx electron-builder "$@"
}
