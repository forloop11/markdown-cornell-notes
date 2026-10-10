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
# Also writes the .AppImage.zsync file to publish next to the AppImage in
# its GitHub release, which is what lets AppImageUpdate update it.
#
# Usage: scripts/build_appimage.sh   (or `make appimage`)
set -euo pipefail
# shellcheck source=bundle_common.sh
source "$(dirname "$0")/bundle_common.sh"

STAGE="$ROOT/dist/linux-stage"
OUT="$ROOT/dist/linux"
PBS_RELEASE="20261009" # python-build-standalone release carrying $PYTHON_VERSION
GITHUB_REPO="forloop11|markdown-cornell-notes" # owner|repo, as update information spells it

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

# Update information, which electron-builder leaves out: where
# AppImageUpdate and similar tools look for a newer version -- the .zsync
# file published next to the AppImage in the latest GitHub release. It
# goes in the runtime's reserved .upd_info section, as appimagetool -u
# writes it; the .zsync has to be made after that, from the final file.
APPIMAGE="$(basename "$OUT"/*.AppImage)"
UPDATE_INFO="gh-releases-zsync|$GITHUB_REPO|latest|Markdown-Cornell-Notes-*-x86_64.AppImage.zsync"
echo "Embedding update information and writing $APPIMAGE.zsync..."
# shellcheck disable=SC2016 # expanded by the container's shell
run_in_builder bash -euo pipefail -c '
  cd /project/dist/linux
  read -r offset size < <(readelf -S -W "$1" | sed "s/^ *\[ *[0-9]*\] *//" | awk "\$1 == \".upd_info\" { print \$4, \$5 }")
  if [ -z "${offset:-}" ] || [ "${#2}" -ge "$((16#$size))" ]; then
    echo "No .upd_info section (or too small a one) in $1." >&2
    exit 1
  fi
  printf %s "$2" | dd of="$1" bs=1 seek="$((16#$offset))" conv=notrunc status=none
  apt-get -qq update && apt-get -qq install -y zsync >/dev/null
  zsyncmake -u "$1" -o "$1.zsync" "$1"
' bash "$APPIMAGE" "$UPDATE_INFO"

ls -lh "$OUT"/*.AppImage "$OUT"/*.zsync
