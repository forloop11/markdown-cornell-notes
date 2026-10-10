#!/usr/bin/env python3
"""Print the per-file options scripts/build_macos.sh passes to `rcodesign
sign` for a Developer ID signature, one argument per line.

rcodesign applies its hardened-runtime flag and entitlements options only
to the bundle's own main executable unless told otherwise, file by file --
and this bundle's main executable is just a launcher. So this finds every
program inside the .app (Python, pandoc, the TeX binaries, Qt's WebEngine
helper) and names each one:

- all of them get the hardened runtime, which notarization requires of
  every executable;
- the ones that run the app itself -- Python, which loads Qt, and Qt's
  WebEngine helper, which runs Chromium -- also get the entitlements in
  macos_entitlements.plist.

Usage: macos_sign_scopes.py <path to .app> <entitlements plist>
"""
import struct
import sys
from pathlib import Path

MH_EXECUTE = 2
THIN_MAGICS = {b"\xcf\xfa\xed\xfe": "<", b"\xfe\xed\xfa\xcf": ">", b"\xce\xfa\xed\xfe": "<", b"\xfe\xed\xfa\xce": ">"}
FAT_MAGICS = {b"\xca\xfe\xba\xbe": 4, b"\xca\xfe\xba\xbf": 8}  # -> size of an arch entry's offset field


def is_program(path):
    """Whether `path` is a Mach-O executable (as opposed to a library, a
    plug-in, or not Mach-O at all).
    """
    with open(path, "rb") as f:
        head = f.read(32)
        if head[:4] in FAT_MAGICS and len(head) >= 20:
            # A universal binary: judge it by its first architecture.
            wide = FAT_MAGICS[head[:4]] == 8
            offset = struct.unpack(">Q" if wide else ">I", head[16 : 16 + (8 if wide else 4)])[0]
            f.seek(offset)
            head = f.read(16)
        order = THIN_MAGICS.get(head[:4])
        return order is not None and len(head) >= 16 and struct.unpack(order + "I", head[12:16])[0] == MH_EXECUTE


def needs_entitlements(path):
    return path.name.startswith("python3") or path.name == "QtWebEngineProcess"


def main():
    app, entitlements = Path(sys.argv[1]), sys.argv[2]
    main_executable = app / "Contents" / "MacOS"
    for path in sorted(app.rglob("*")):
        if path.is_symlink() or not path.is_file() or main_executable in path.parents or not is_program(path):
            continue
        scope = path.relative_to(app).as_posix()
        print("--code-signature-flags")
        print(f"{scope}:runtime")
        if needs_entitlements(path):
            print("--entitlements-xml-file")
            print(f"{scope}:{entitlements}")


if __name__ == "__main__":
    main()
