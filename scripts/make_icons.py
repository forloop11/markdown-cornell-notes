#!/usr/bin/env python3
"""Regenerate the app icon's Windows and macOS forms
(app/build-resources/icon.ico, icon.icns) from icon.png, for the installer
and .app the standalone builds make. Both are committed; run this again
only when icon.png changes.

Needs PySide6 (to scale the image) -- run it with the editor app's Python:

    app/.venv/bin/python scripts/make_icons.py
"""
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

RESOURCES = Path(__file__).resolve().parent.parent / "app" / "build-resources"

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
# icns entry type -> pixel size ("@2x" entries are the next size up).
ICNS_TYPES = [(b"icp4", 16), (b"icp5", 32), (b"icp6", 64), (b"ic07", 128), (b"ic08", 256), (b"ic09", 512),
              (b"ic11", 32), (b"ic12", 64), (b"ic13", 256), (b"ic14", 512)]  # fmt: skip


def png(image, size):
    scaled = image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    scaled.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(image, path):
    """An .ico holding each size as a PNG (which Windows Vista and later read)."""
    images = [(size, png(image, size)) for size in ICO_SIZES]
    offset = 6 + 16 * len(images)
    header, body = struct.pack("<HHH", 0, 1, len(images)), b""
    for size, data in images:
        # Width/height 0 means 256.
        header += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset + len(body))
        body += data
    path.write_bytes(header + body)


def write_icns(image, path):
    body = b""
    for kind, size in ICNS_TYPES:
        data = png(image, size)
        body += kind + struct.pack(">I", len(data) + 8) + data
    path.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)


def main():
    image = QImage(str(RESOURCES / "icon.png"))
    if image.isNull():
        raise SystemExit("Couldn't read icon.png.")
    write_ico(image, RESOURCES / "icon.ico")
    write_icns(image, RESOURCES / "icon.icns")


if __name__ == "__main__":
    main()
