#!/usr/bin/env bash
# Builds the Windows installer for the editor app (dist/windows/
# Markdown-Cornell-Notes-Setup-<version>.exe, an NSIS per-user installer),
# bundling Python (the official embeddable build), pandoc, and TeX so the
# user installs nothing else. See scripts/bundle_common.sh for what the
# bundle holds and how the TeX tree is built.
#
# Runs on an x86_64 Linux host with podman or docker: electron-builder
# runs in its electronuserland/builder:wine image, whose Wine sets the
# .exe's icon and version info.
#
# Usage: scripts/build_windows.sh   (or `make windows`)
set -euo pipefail
# shellcheck source=bundle_common.sh
source "$(dirname "$0")/bundle_common.sh"

STAGE="$ROOT/dist/windows-stage"

download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-windows-x86_64.zip" \
  "$CACHE/pandoc-$PANDOC_VERSION-windows.zip"
download "https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-embed-amd64.zip" \
  "$CACHE/python-$PYTHON_VERSION-embed.zip"
prepare_tex

echo "Staging resources..."
rm -rf "$STAGE"
mkdir -p "$STAGE"/{pipeline,python,pandoc}

stage_texlive "$STAGE/texlive" windows
stage_pipeline "$STAGE/pipeline"

unzip -q -j "$CACHE/pandoc-$PANDOC_VERSION-windows.zip" \
  "pandoc-$PANDOC_VERSION/pandoc.exe" "pandoc-$PANDOC_VERSION/COPYRIGHT.txt" "pandoc-$PANDOC_VERSION/COPYING.rtf" \
  -d "$STAGE/pandoc"

unzip -q "$CACHE/python-$PYTHON_VERSION-embed.zip" -d "$STAGE/python"
# The embeddable build's ._pth file replaces sys.path outright -- so it no
# longer includes the running script's own directory, which scripts/ needs
# to import simple_yaml. Add that directory (relative to python.exe).
pth=("$STAGE"/python/python*._pth)
printf '%s\r\n' '..\pipeline\scripts' >> "${pth[0]}"

cp "$ROOT/LICENSE" "$STAGE/LICENSE.txt"
write_notices "$STAGE/THIRD-PARTY-NOTICES.txt" "embeddable distribution" "python/LICENSE.txt"

run_builder --win nsis --x64 --publish never

ls -lh "$ROOT"/dist/windows/*.exe
