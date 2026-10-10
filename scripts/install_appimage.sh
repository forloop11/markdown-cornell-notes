#!/bin/sh
# Installs the AppImage `make appimage` built (dist/linux/) for the current
# user: copies it to ~/Applications, and adds an application-menu entry and
# icon for it. Nothing here needs root. `uninstall` removes all three again;
# notes (in Documents/Cornell Notes, or wherever they're kept) are never
# touched.
#
# Usage: scripts/install_appimage.sh [install|uninstall]
#        (or `make install-appimage` / `make uninstall-appimage`)
# APPIMAGE_DIR overrides where the AppImage itself goes.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPIMAGE_DIR="${APPIMAGE_DIR:-$HOME/Applications}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
# Named after the app's desktop file name (see app/main.py), so desktops
# match the running window to this entry.
DESKTOP_FILE="$DATA_HOME/applications/markdown-cornell-notes.desktop"
ICON_FILE="$DATA_HOME/icons/hicolor/512x512/apps/markdown-cornell-notes.png"

refresh_menus() {
  update-desktop-database "$DATA_HOME/applications" 2> /dev/null || true
  gtk-update-icon-cache -q -t "$DATA_HOME/icons/hicolor" 2> /dev/null || true
}

case "${1:-install}" in
  install)
    # The newest build, if several versions are lying around.
    source_file="$(ls -t "$ROOT"/dist/linux/Markdown-Cornell-Notes-*-x86_64.AppImage 2> /dev/null | head -n 1)"
    if [ -z "$source_file" ]; then
      echo "No AppImage in dist/linux/ -- run 'make appimage' first." >&2
      exit 1
    fi
    target="$APPIMAGE_DIR/$(basename "$source_file")"
    mkdir -p "$APPIMAGE_DIR" "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")"
    # Copy, then rename into place: replacing the file a running copy was
    # started from is safe that way.
    cp "$source_file" "$target.new"
    chmod +x "$target.new"
    mv "$target.new" "$target"
    cp "$ROOT/app/build-resources/icon.png" "$ICON_FILE"
    cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Type=Application
Name=Markdown Cornell Notes
Comment=Cornell-style meeting notes from Markdown, with a live PDF preview
Exec="$target" %U
Icon=markdown-cornell-notes
Terminal=false
Categories=Office;
StartupWMClass=markdown-cornell-notes
DESKTOP
    refresh_menus
    echo "Installed $target"
    ;;
  uninstall)
    if [ -f "$DESKTOP_FILE" ]; then
      # The entry says which AppImage it was installed with.
      installed="$(sed -n 's/^Exec="\(.*\)" %U$/\1/p' "$DESKTOP_FILE")"
      case "$installed" in
        */Markdown-Cornell-Notes-*-x86_64.AppImage) rm -f "$installed" ;;
      esac
    fi
    rm -f "$DESKTOP_FILE" "$ICON_FILE"
    refresh_menus
    echo "Uninstalled Markdown Cornell Notes (your notes are untouched)."
    ;;
  *)
    echo "Usage: $0 [install|uninstall]" >&2
    exit 2
    ;;
esac
