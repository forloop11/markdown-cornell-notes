#!/usr/bin/env bash
# Builds the Linux editor app as an AppImage
# (dist/linux/Markdown-Cornell-Notes-<version>-x86_64.AppImage): one
# executable file that runs on most x86_64 distributions, bundling Python,
# pandoc, and TeX so the user installs nothing else. See
# scripts/bundle_common.sh for what the bundle holds and how the TeX tree
# is built.
#
# Runs on an x86_64 Linux host with podman or docker; electron-builder
# runs in the same container image as the Windows and macOS builds.
#
# Python here is python-build-standalone's relocatable CPython (built
# against an old glibc, so it runs on old and new distributions alike);
# pandoc's Linux build is a static binary; the TeX tree's own x86_64-linux
# binaries -- the ones its tlmgr runs with while the tree is assembled --
# are what gets bundled.
#
# Usage: scripts/build_appimage.sh   (or `make appimage`)
set -euo pipefail
# shellcheck source=bundle_common.sh
source "$(dirname "$0")/bundle_common.sh"

STAGE="$ROOT/dist/linux-stage"
OUT="$ROOT/dist/linux"
PBS_RELEASE="20261009" # python-build-standalone release carrying $PYTHON_VERSION

download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-linux-amd64.tar.gz" \
  "$CACHE/pandoc-$PANDOC_VERSION-linux-amd64.tar.gz"
# Only for pandoc's license files, which the Linux tarball doesn't include.
download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-windows-x86_64.zip" \
  "$CACHE/pandoc-$PANDOC_VERSION-windows.zip"
download "https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_RELEASE/cpython-$PYTHON_VERSION%2B$PBS_RELEASE-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz" \
  "$CACHE/cpython-$PYTHON_VERSION-$PBS_RELEASE-x86_64-unknown-linux-gnu.tar.gz"
prepare_tex

echo "Staging resources..."
rm -rf "$STAGE"
mkdir -p "$STAGE"/{pipeline,pandoc}

stage_texlive "$STAGE/texlive" x86_64-linux
stage_pipeline "$STAGE/pipeline"

tar -xzf "$CACHE/pandoc-$PANDOC_VERSION-linux-amd64.tar.gz" -C "$STAGE/pandoc" --strip-components=1 "pandoc-$PANDOC_VERSION/bin"
unzip -q -j "$CACHE/pandoc-$PANDOC_VERSION-windows.zip" \
  "pandoc-$PANDOC_VERSION/COPYRIGHT.txt" "pandoc-$PANDOC_VERSION/COPYING.rtf" -d "$STAGE/pandoc"

# A regular CPython install: it adds the running script's directory to
# sys.path itself, so scripts/ finds simple_yaml with no extra setup.
tar -xzf "$CACHE/cpython-$PYTHON_VERSION-$PBS_RELEASE-x86_64-unknown-linux-gnu.tar.gz" -C "$STAGE"

write_notices "$STAGE/THIRD-PARTY-NOTICES.txt" \
  "python-build-standalone $PBS_RELEASE (https://github.com/astral-sh/python-build-standalone)" \
  "python/lib/python3.13/LICENSE.txt"

rm -rf "$OUT"
run_builder --linux AppImage --x64 --publish never -c.directories.output=../dist/linux

ls -lh "$OUT"/*.AppImage
