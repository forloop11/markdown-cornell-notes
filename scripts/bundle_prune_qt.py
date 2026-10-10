#!/usr/bin/env python3
"""Strip a pip-installed PySide6 down to what the editor app (app/) uses,
for the standalone builds (see bundle_common.sh): Qt Widgets, Svg,
WebChannel, and WebEngine with the modules those link against stay; the
rest of Qt -- 3D, Charts, Multimedia, Quick Controls, the Designer and
Linguist tools, QML modules, ... -- goes, which roughly halves the install.

Works by name, on all three platforms' layouts: Linux and macOS keep Qt
under PySide6/Qt/ (libQt6Charts.so.6, QtCharts.framework), Windows right in
PySide6/ (Qt6Charts.dll); the Python modules are QtCharts.abi3.so/.pyd
everywhere.

Afterwards it checks that nothing kept still names a library that went
(see dangling_references), and fails if so -- on a platform the build host
can't run, that's the only warning a wrong DROP_FAMILIES entry gives.

Usage: bundle_prune_qt.py <site-packages directory>
"""
import re
import shutil
import sys
from pathlib import Path

# Qt module families the app doesn't use, as name prefixes after "Qt"/"Qt6".
# Deliberately a list of what goes, not of what stays: a module missing
# from it only costs size, where a wrongly dropped one breaks the app.
DROP_FAMILIES = [
    "3D", "Bluetooth", "CanvasPainter", "Charts", "DataVisualization", "Designer", "EglF", "FFmpegStub",
    "Graphs", "Help", "HttpServer", "Labs", "Location", "Lottie", "Multimedia", "NetworkAuth", "Nfc", "Pdf",
    "PositioningQuick", "QmlCompiler", "QmlCore", "QmlDesignSupport", "QmlLocalStorage", "QmlNetwork",
    "QmlXmlListModel", "Quick3D", "QuickControls2", "QuickDialogs2", "QuickEffects", "QuickLayouts",
    "QuickNativeStyle", "QuickParticles", "QuickShapes", "QuickTemplates2", "QuickTest", "QuickTimeline", "QuickVectorImage",
    "RemoteObjects", "Scxml", "Sensors", "SerialBus", "SerialPort", "ShaderTools", "SpatialAudio", "Sql",
    "StateMachine", "Test", "TextToSpeech", "UiTools", "VirtualKeyboard", "WaylandCompositor",
    "WaylandEglCompositor", "WebChannelQuick", "WebEngineQuick", "WebSockets", "WebView",
]  # fmt: skip
FAMILY_RE = re.compile(r"(?:lib)?Qt6?(?:%s)" % "|".join(DROP_FAMILIES))
# The FFmpeg libraries Qt Multimedia ships (WebEngine has its own built in).
FFMPEG_RE = re.compile(r"(?:lib)?(?:avcodec|avformat|avutil|swresample|swscale)[-.]")

# Development tools, by name with any .exe/.app suffix removed.
DROP_TOOLS = {
    "assistant", "balsam", "balsamui", "designer", "linguist", "lrelease", "lupdate", "qmlformat", "qmllint",
    "qmlls", "qsb", "svgtoqml", "qmlcachegen", "qmlimportscanner", "qmltyperegistrar", "rcc", "uic",
}  # fmt: skip
DROP_DIRS = {"doc", "glue", "include", "typesystems", "scripts", "QtAsyncio", "examples", "cmake", "qml", "metatypes"}
DROP_PLUGIN_DIRS = {
    "assetimporters", "canbus", "designer", "egldeviceintegrations", "geometryloaders", "geoservices",
    "multimedia", "position", "qmltooling", "renderers", "renderplugins", "sceneparsers", "scxmldatamodel",
    "sensors", "sqldrivers", "texttospeech", "vectorimageformats", "wayland-graphics-integration-server",
    "webview",
}  # fmt: skip
# Plugins that load a dropped module: the PDF image format, the EGLFS
# platforms, the virtual keyboard input method.
DROP_PLUGINS_RE = re.compile(r"(?:lib)?q(?:pdf|eglfs|minimalegl|tvirtualkeyboardplugin)\.")
# Translations of the tools and modules dropped above; Qt's own, and
# WebEngine's (translations/qtwebengine_locales), stay.
DROP_TRANSLATIONS_RE = re.compile(
    r"(?:assistant|designer|linguist|qtconnectivity|qtdeclarative|qtlocation|qtmultimedia|qtserialport|qtwebsockets)_"
)


def unwanted(path):
    name = path.name
    stem = name.split(".")[0]
    if path.is_dir() and not path.is_symlink():
        if name in DROP_DIRS or (stem.lower() in DROP_TOOLS and name.endswith(".app")):
            return True
        if path.parent.name == "plugins" and name in DROP_PLUGIN_DIRS:
            return True
        return name.endswith(".framework") and FAMILY_RE.match(name) is not None
    if FAMILY_RE.match(name) or FFMPEG_RE.match(name):
        return True
    if stem.lower() in DROP_TOOLS and path.suffix in ("", ".exe"):
        return True
    if path.parent.parent.name == "plugins" and DROP_PLUGINS_RE.match(name):
        return True
    if path.parent.name == "translations" and DROP_TRANSLATIONS_RE.match(name):
        return True
    return name.endswith(".pyi") or name == "py.typed"


def prune(directory):
    for path in sorted(directory.iterdir()):
        if unwanted(path):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        elif path.is_dir() and not path.is_symlink():
            prune(path)


# How a binary names a Qt library it loads: libQt6Charts.so.6 (Linux),
# Qt6Charts.dll (Windows), QtCharts.framework (macOS).
REFERENCE_RE = re.compile(
    rb"(?:libQt6(?:%(f)s)\w*\.so\.6|Qt6(?:%(f)s)\w*\.dll|Qt(?:%(f)s)\w*\.framework)" % {b"f": "|".join(DROP_FAMILIES).encode()}
)
BINARY_SUFFIXES = {".so", ".dylib", ".dll", ".pyd", ".exe", ""}


def dangling_references(directory):
    """(file, library name) for every kept binary under `directory` that
    names a dropped Qt library.
    """
    found = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if path.suffix not in BINARY_SUFFIXES and ".so." not in path.name:
            continue
        with open(path, "rb") as f:
            if f.read(4) not in (b"\x7fELF", b"MZ\x90\x00", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
                continue
            data = f.read()
        for name in sorted({match.group().decode() for match in REFERENCE_RE.finditer(data)}):
            found.append((path.relative_to(directory), name))
    return found


def main():
    pyside = Path(sys.argv[1]) / "PySide6"
    if not pyside.is_dir():
        sys.exit(f"No PySide6 in {sys.argv[1]}.")
    prune(pyside)
    dangling = dangling_references(pyside)
    if dangling:
        for path, name in dangling:
            print(f"{path} needs {name}, which DROP_FAMILIES removed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
