#!/usr/bin/env bash
# Builds the Linux editor app as an AppImage
# (dist/linux/Markdown-Cornell-Notes-<version>-x86_64.AppImage): one
# executable file that runs on most x86_64 distributions, bundling Python,
# Qt (PySide6), pandoc, and TeX so the user installs nothing else. See
# scripts/bundle_common.sh for what the bundle holds and how it's put
# together.
#
# Runs on an x86_64 Linux host; appimagetool (downloaded, like everything
# else here) packs the AppDir staged in dist/linux-stage/.
#
# Python here is python-build-standalone's relocatable CPython (built
# against an old glibc); pandoc's Linux build is a static binary; the TeX
# tree's own x86_64-linux binaries -- the ones its tlmgr runs with while
# the tree is assembled -- are what gets bundled. Qt's wheels are the
# newest of the lot: they need glibc 2.34 (see $PYSIDE_PLATFORM).
#
# The AppImage carries update information pointing at the .zsync file
# written next to it: publish both in the GitHub release, and
# AppImageUpdate and similar tools can update the app from the latest one.
#
# With MCN_STAGE_ONLY set, it stops once the bundle is staged
# (dist/linux-stage/AppDir/resources) -- the same Linux bundle the snap
# wraps (see snap/snapcraft.yaml).
#
# Usage: scripts/build_appimage.sh   (or `make appimage`)
set -euo pipefail
# shellcheck source=bundle_common.sh
source "$(dirname "$0")/bundle_common.sh"

APPDIR="$ROOT/dist/linux-stage/AppDir"
RES="$APPDIR/resources"
OUT="$ROOT/dist/linux"
PYSIDE_PLATFORM="manylinux_2_34_x86_64"
APPIMAGETOOL_VERSION="1.9.1"
APPIMAGE_RUNTIME_VERSION="20251108" # AppImage/type2-runtime: static, so no libfuse2 needed to mount
GITHUB_REPO="forloop11|markdown-cornell-notes" # owner|repo, as update information spells it

download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-linux-amd64.tar.gz" \
  "$CACHE/pandoc-$PANDOC_VERSION-linux-amd64.tar.gz"
# Only for pandoc's license files, which the Linux tarball doesn't include.
download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-windows-x86_64.zip" \
  "$CACHE/pandoc-$PANDOC_VERSION-windows.zip"
prepare_build_python
prepare_tex

echo "Staging resources..."
rm -rf "$ROOT/dist/linux-stage"
mkdir -p "$RES"/{pipeline,pandoc}

stage_texlive "$RES/texlive" x86_64-linux
stage_pipeline "$RES/pipeline"
stage_dictionary "$RES"

tar -xzf "$CACHE/pandoc-$PANDOC_VERSION-linux-amd64.tar.gz" -C "$RES/pandoc" --strip-components=1 "pandoc-$PANDOC_VERSION/bin"
unzip -q -j "$CACHE/pandoc-$PANDOC_VERSION-windows.zip" \
  "pandoc-$PANDOC_VERSION/COPYRIGHT.txt" "pandoc-$PANDOC_VERSION/COPYING.rtf" -d "$RES/pandoc"

# A regular CPython install: it adds the running script's directory to
# sys.path itself, so app/ and scripts/ find their own modules with no
# extra setup.
tar -xzf "$PBS_LINUX_TARBALL" -C "$RES"
stage_pyside "$RES/python/lib/python${PYTHON_VERSION%.*}/site-packages" "$PYSIDE_PLATFORM"

write_notices "$RES/THIRD-PARTY-NOTICES.txt" \
  "python-build-standalone $PBS_RELEASE (https://github.com/astral-sh/python-build-standalone)" \
  "python/lib/python${PYTHON_VERSION%.*}/LICENSE.txt"
cp "$ROOT/LICENSE" "$RES/LICENSE.txt"

if [ -n "${MCN_STAGE_ONLY:-}" ]; then
  echo "Staged $RES (MCN_STAGE_ONLY is set: not packing an AppImage)."
  exit 0
fi

download "https://github.com/AppImage/appimagetool/releases/download/$APPIMAGETOOL_VERSION/appimagetool-x86_64.AppImage" \
  "$CACHE/appimagetool-$APPIMAGETOOL_VERSION-x86_64.AppImage"
download "https://github.com/AppImage/type2-runtime/releases/download/$APPIMAGE_RUNTIME_VERSION/runtime-x86_64" \
  "$CACHE/appimage-runtime-$APPIMAGE_RUNTIME_VERSION-x86_64"

# The AppDir's own files: what runs, and how desktops show it.
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
# Starts the editor app with the Python bundled next to it.
here="$(dirname "$(readlink -f "$0")")"
exec "$here/resources/python/bin/python3" "$here/resources/pipeline/app/main.py" "$@"
EOF
chmod +x "$APPDIR/AppRun"
cat > "$APPDIR/markdown-cornell-notes.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Markdown Cornell Notes
Comment=Cornell-style meeting notes from Markdown, with a live PDF preview
Exec=AppRun
Icon=markdown-cornell-notes
Categories=Office;
StartupWMClass=markdown-cornell-notes
X-AppImage-Version=$APP_VERSION
EOF
cp "$ROOT/app/build-resources/icon.png" "$APPDIR/markdown-cornell-notes.png"
ln -s markdown-cornell-notes.png "$APPDIR/.DirIcon"

echo "Packing the AppImage..."
rm -rf "$OUT"
mkdir -p "$OUT"
APPIMAGE="$OUT/Markdown-Cornell-Notes-$APP_VERSION-x86_64.AppImage"
chmod +x "$CACHE/appimagetool-$APPIMAGETOOL_VERSION-x86_64.AppImage"
# --appimage-extract-and-run: appimagetool is itself an AppImage, and this
# way needs no FUSE on the build host. Run from $OUT, where it writes the
# .zsync file that -u (the update information) has it generate.
(cd "$OUT" && ARCH=x86_64 "$CACHE/appimagetool-$APPIMAGETOOL_VERSION-x86_64.AppImage" --appimage-extract-and-run \
  --no-appstream \
  --runtime-file "$CACHE/appimage-runtime-$APPIMAGE_RUNTIME_VERSION-x86_64" \
  -u "gh-releases-zsync|$GITHUB_REPO|latest|Markdown-Cornell-Notes-*-x86_64.AppImage.zsync" \
  "$APPDIR" "$APPIMAGE")

ls -lh "$OUT"
