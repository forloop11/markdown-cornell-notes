#!/usr/bin/env bash
# Builds the macOS editor app for Apple Silicon as a zip
# (dist/macos/Markdown-Cornell-Notes-<version>-arm64-mac.zip, holding
# "Markdown Cornell Notes.app"), bundling Python, Qt (PySide6), pandoc,
# and TeX so the user installs nothing else. See scripts/bundle_common.sh
# for what the bundle holds and how it's put together.
#
# Runs on an x86_64 Linux host -- no Mac needed: the .app is a folder
# assembled here from prebuilt downloads, then signed with rcodesign (from
# apple-codesign, run here on Linux).
#
# Signing comes in two strengths:
#
# - By default the app is only ad-hoc signed. That's not an Apple
#   Developer ID signature, and the app isn't notarized, so Gatekeeper
#   blocks it on first launch until the user allows it (see
#   docs/installation.md).
# - With an Apple Developer account, set these (all paths to files kept
#   outside the repository) and it's signed with your Developer ID,
#   notarized by Apple, and stapled, so it opens without a warning:
#
#     MACOS_SIGN_P12                your "Developer ID Application"
#                                   certificate and its private key (.p12)
#     MACOS_SIGN_P12_PASSWORD_FILE  a file holding that .p12's password
#     MACOS_NOTARY_API_KEY          an App Store Connect API key, as the
#                                   JSON file `rcodesign
#                                   encode-app-store-connect-api-key` makes
#
#   docs/installation.md walks through getting each of them.
#
# The .app's own executable is a small launcher (scripts/macos_launcher.c,
# cross-compiled here with zig) that starts the bundled Python on
# app/main.py -- a compiled one, since a script can't be code signed as an
# .app's main executable.
#
# Python here is python-build-standalone's relocatable CPython: python.org
# has no embeddable build for macOS, and macOS no longer ships one. Qt's
# wheels set the minimum macOS version (see $PYSIDE_PLATFORM).
#
# Usage: scripts/build_macos.sh   (or `make macos`)
set -euo pipefail
# shellcheck source=bundle_common.sh
source "$(dirname "$0")/bundle_common.sh"

OUT="$ROOT/dist/macos"
APP="$OUT/Markdown Cornell Notes.app"
RES="$APP/Contents/Resources"
PYSIDE_PLATFORM="macosx_14_0_universal2"
MIN_MACOS="14.0"
RCODESIGN_VERSION="0.29.0"
ZIG_VERSION="0.13.0"

download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-arm64-macOS.zip" \
  "$CACHE/pandoc-$PANDOC_VERSION-arm64-macOS.zip"
# Only for pandoc's license files, which the macOS zip doesn't include.
download "https://github.com/jgm/pandoc/releases/download/$PANDOC_VERSION/pandoc-$PANDOC_VERSION-windows-x86_64.zip" \
  "$CACHE/pandoc-$PANDOC_VERSION-windows.zip"
download "https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_RELEASE/cpython-$PYTHON_VERSION%2B$PBS_RELEASE-aarch64-apple-darwin-install_only_stripped.tar.gz" \
  "$CACHE/cpython-$PYTHON_VERSION-$PBS_RELEASE-aarch64-apple-darwin.tar.gz"
download "https://github.com/indygreg/apple-platform-rs/releases/download/apple-codesign%2F$RCODESIGN_VERSION/apple-codesign-$RCODESIGN_VERSION-x86_64-unknown-linux-musl.tar.gz" \
  "$CACHE/apple-codesign-$RCODESIGN_VERSION.tar.gz"
download "https://ziglang.org/download/$ZIG_VERSION/zig-linux-x86_64-$ZIG_VERSION.tar.xz" "$CACHE/zig-$ZIG_VERSION.tar.xz"
prepare_build_python
prepare_tex

zig="$CACHE/zig-linux-x86_64-$ZIG_VERSION/zig"
[ -x "$zig" ] || tar -xJf "$CACHE/zig-$ZIG_VERSION.tar.xz" -C "$CACHE"
rcodesign="$CACHE/apple-codesign-$RCODESIGN_VERSION-x86_64-unknown-linux-musl/rcodesign"
[ -x "$rcodesign" ] || tar -xzf "$CACHE/apple-codesign-$RCODESIGN_VERSION.tar.gz" -C "$CACHE"

echo "Staging resources..."
rm -rf "$OUT"
mkdir -p "$APP/Contents/MacOS" "$RES"/{pipeline,pandoc}

stage_texlive "$RES/texlive" universal-darwin
stage_pipeline "$RES/pipeline"
stage_dictionary "$RES"

unzip -q "$CACHE/pandoc-$PANDOC_VERSION-arm64-macOS.zip" "pandoc-$PANDOC_VERSION-arm64/bin/*" -d "$RES"
mv "$RES/pandoc-$PANDOC_VERSION-arm64/bin" "$RES/pandoc/bin"
rmdir "$RES/pandoc-$PANDOC_VERSION-arm64"
unzip -q -j "$CACHE/pandoc-$PANDOC_VERSION-windows.zip" \
  "pandoc-$PANDOC_VERSION/COPYRIGHT.txt" "pandoc-$PANDOC_VERSION/COPYING.rtf" -d "$RES/pandoc"

# Unlike the Windows embeddable build, this is a regular CPython install:
# it adds the running script's directory to sys.path itself, so app/ and
# scripts/ find their own modules with no ._pth edit.
tar -xzf "$CACHE/cpython-$PYTHON_VERSION-$PBS_RELEASE-aarch64-apple-darwin.tar.gz" -C "$RES"
stage_pyside "$RES/python/lib/python${PYTHON_VERSION%.*}/site-packages" "$PYSIDE_PLATFORM"

write_notices "$RES/THIRD-PARTY-NOTICES.txt" \
  "python-build-standalone $PBS_RELEASE (https://github.com/astral-sh/python-build-standalone)" \
  "python/lib/python${PYTHON_VERSION%.*}/LICENSE.txt"
cp "$ROOT/LICENSE" "$RES/LICENSE.txt"
cp "$ROOT/app/build-resources/icon.icns" "$RES/icon.icns"

ZIG_GLOBAL_CACHE_DIR="$CACHE/zig-cache" ZIG_LOCAL_CACHE_DIR="$CACHE/zig-cache" \
  "$zig" cc -target "aarch64-macos.$MIN_MACOS" -O2 -Wall -Wextra \
  -o "$APP/Contents/MacOS/markdown-cornell-notes" "$ROOT/scripts/macos_launcher.c"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Markdown Cornell Notes</string>
  <key>CFBundleDisplayName</key><string>Markdown Cornell Notes</string>
  <key>CFBundleIdentifier</key><string>io.github.forloop11.markdown-cornell-notes</string>
  <key>CFBundleExecutable</key><string>markdown-cornell-notes</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleShortVersionString</key><string>$APP_VERSION</string>
  <key>CFBundleVersion</key><string>$APP_VERSION</string>
  <key>LSMinimumSystemVersion</key><string>$MIN_MACOS</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
  <key>LSArchitecturePriority</key><array><string>arm64</string></array>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSHumanReadableCopyright</key><string>Copyright © Todd C. Takala</string>
</dict>
</plist>
EOF

if [ -n "${MACOS_SIGN_P12:-}" ]; then
  echo "Signing with the Developer ID certificate in $MACOS_SIGN_P12..."
  if [ -z "${MACOS_SIGN_P12_PASSWORD_FILE:-}" ]; then
    echo "Set MACOS_SIGN_P12_PASSWORD_FILE to a file holding the password of $MACOS_SIGN_P12." >&2
    exit 1
  fi
  for file in "$MACOS_SIGN_P12" "$MACOS_SIGN_P12_PASSWORD_FILE"; do
    [ -f "$file" ] || { echo "No such file: $file" >&2; exit 1; }
  done
  # --for-notarization: the hardened runtime and a secure timestamp on
  # every signature, both of which Apple's notary service insists on (and
  # a check that the certificate is a Developer ID one).
  #
  # The hardened runtime blocks things Python and Qt's Chromium need
  # unless the entitlements file allows them. rcodesign applies both only
  # to the launcher unless each program inside is named, which is what
  # macos_sign_scopes.py's output does.
  entitlements="$ROOT/scripts/macos_entitlements.plist"
  mapfile -t scopes < <("$BUILD_PYTHON" "$ROOT/scripts/macos_sign_scopes.py" "$APP" "$entitlements")
  # MACOS_SIGN_EXTRA_ARGS: for trying the signing step with a certificate
  # Apple didn't issue (e.g. "--code-signature-flags runtime" in place of
  # the default, which insists on a Developer ID).
  # shellcheck disable=SC2086
  "$rcodesign" sign ${MACOS_SIGN_EXTRA_ARGS---for-notarization} \
    --p12-file "$MACOS_SIGN_P12" --p12-password-file "$MACOS_SIGN_P12_PASSWORD_FILE" \
    --entitlements-xml-file "$entitlements" \
    "${scopes[@]}" \
    "$APP"
  if [ -n "${MACOS_NOTARY_API_KEY:-}" ]; then
    [ -f "$MACOS_NOTARY_API_KEY" ] || { echo "No such file: $MACOS_NOTARY_API_KEY" >&2; exit 1; }
    echo "Submitting to Apple for notarization (usually a few minutes)..."
    # Uploads the app, waits for Apple's verdict, and staples the ticket
    # to the .app -- so it opens without a warning even offline. Stapling
    # comes before zipping: a zip itself can't carry a ticket.
    "$rcodesign" notary-submit --api-key-file "$MACOS_NOTARY_API_KEY" --staple "$APP"
  else
    echo "Signed but NOT notarized (MACOS_NOTARY_API_KEY isn't set): Gatekeeper will still warn." >&2
  fi
else
  echo "Ad-hoc signing (MACOS_SIGN_P12 isn't set: Gatekeeper will block the first launch)..."
  "$rcodesign" sign "$APP"
fi

zip_file="$OUT/Markdown-Cornell-Notes-$APP_VERSION-arm64-mac.zip"
# -y keeps symlinks (Qt's frameworks are full of them) as symlinks.
(cd "$OUT" && zip -qry "$zip_file" "Markdown Cornell Notes.app")
ls -lh "$zip_file"
