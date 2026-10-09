#!/usr/bin/env bash
# Builds the macOS editor app for Apple Silicon as a zip
# (dist/macos/Markdown-Cornell-Notes-<version>-arm64-mac.zip, holding
# "Markdown Cornell Notes.app"), bundling Python, pandoc, and TeX so the
# user installs nothing else. See scripts/bundle_common.sh for what the
# bundle holds and how the TeX tree is built.
#
# Runs on an x86_64 Linux host with podman or docker -- no Mac needed:
# electron-builder assembles the .app in its container image, then
# rcodesign (from apple-codesign, run here on Linux) ad-hoc signs every
# executable in it. Apple Silicon refuses to run unsigned code at all, so
# that signature is required; but it's not an Apple Developer ID
# signature, and the app isn't notarized, so Gatekeeper still blocks it
# on first launch until the user allows it (see docs/installation.md).
#
# Python here is python-build-standalone's relocatable CPython: python.org
# has no embeddable build for macOS, and macOS no longer ships one.
#
# Usage: scripts/build_macos.sh   (or `make macos`)
set -euo pipefail
# shellcheck source=bundle_common.sh
source "$(dirname "$0")/bundle_common.sh"

STAGE="$ROOT/dist/macos-stage"
OUT="$ROOT/dist/macos"
PBS_RELEASE="20261009" # python-build-standalone release carrying $PYTHON_VERSION
RCODESIGN_VERSION="0.29.0"

download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-arm64-macOS.zip" \
  "$CACHE/pandoc-$PANDOC_VERSION-arm64-macOS.zip"
# Only for pandoc's license files, which the macOS zip doesn't include.
download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-windows-x86_64.zip" \
  "$CACHE/pandoc-$PANDOC_VERSION-windows.zip"
download "https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_RELEASE/cpython-$PYTHON_VERSION%2B$PBS_RELEASE-aarch64-apple-darwin-install_only_stripped.tar.gz" \
  "$CACHE/cpython-$PYTHON_VERSION-$PBS_RELEASE-aarch64-apple-darwin.tar.gz"
download "https://github.com/indygreg/apple-platform-rs/releases/download/apple-codesign%2F$RCODESIGN_VERSION/apple-codesign-$RCODESIGN_VERSION-x86_64-unknown-linux-musl.tar.gz" \
  "$CACHE/apple-codesign-$RCODESIGN_VERSION.tar.gz"
prepare_tex

rcodesign="$CACHE/apple-codesign-$RCODESIGN_VERSION-x86_64-unknown-linux-musl/rcodesign"
[ -x "$rcodesign" ] || tar -xzf "$CACHE/apple-codesign-$RCODESIGN_VERSION.tar.gz" -C "$CACHE"

echo "Staging resources..."
rm -rf "$STAGE"
mkdir -p "$STAGE"/{pipeline,pandoc}

stage_texlive "$STAGE/texlive" universal-darwin
stage_pipeline "$STAGE/pipeline"

unzip -q "$CACHE/pandoc-$PANDOC_VERSION-arm64-macOS.zip" "pandoc-$PANDOC_VERSION-arm64/bin/*" -d "$STAGE"
mv "$STAGE/pandoc-$PANDOC_VERSION-arm64/bin" "$STAGE/pandoc/bin"
rm -rf "$STAGE/pandoc-$PANDOC_VERSION-arm64"
unzip -q -j "$CACHE/pandoc-$PANDOC_VERSION-windows.zip" \
  "pandoc-$PANDOC_VERSION/COPYRIGHT.txt" "pandoc-$PANDOC_VERSION/COPYING.rtf" -d "$STAGE/pandoc"

# Unlike the Windows embeddable build, this is a regular CPython install:
# it adds the running script's directory to sys.path itself, so scripts/
# finds simple_yaml with no ._pth edit.
tar -xzf "$CACHE/cpython-$PYTHON_VERSION-$PBS_RELEASE-aarch64-apple-darwin.tar.gz" -C "$STAGE"

write_notices "$STAGE/THIRD-PARTY-NOTICES.txt" \
  "python-build-standalone $PBS_RELEASE (https://github.com/astral-sh/python-build-standalone)" \
  "python/lib/python3.13/LICENSE.txt"

rm -rf "$OUT"
run_builder --mac dir --arm64 --publish never -c.directories.output=../dist/macos

app_dir="$OUT/mac-arm64/Markdown Cornell Notes.app"
echo "Ad-hoc signing..."
"$rcodesign" sign "$app_dir"

version="$(sed -n 's/^  "version": "\(.*\)",$/\1/p' "$ROOT/app/package.json")"
zip_file="$OUT/Markdown-Cornell-Notes-$version-arm64-mac.zip"
# -y keeps symlinks (the Electron framework is full of them) as symlinks.
(cd "$OUT/mac-arm64" && zip -qry "$zip_file" "Markdown Cornell Notes.app")
ls -lh "$zip_file"
