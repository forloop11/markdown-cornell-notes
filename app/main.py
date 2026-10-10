#!/usr/bin/env python3
"""The Cornell notes editor app: one window (window.py) over a project
directory. A PySide6 (Qt) desktop app; see ../docs/editor-app.md.

Run from a checkout or an installed package (`make app`), the project is
the directory the app was launched from. The standalone builds (Windows
installer, macOS app, Linux AppImage -- see ../scripts/build_windows.sh,
build_macos.sh, build_appimage.sh) have no such directory, so they keep
their project in Documents/Cornell Notes -- or wherever File > Open
Project Folder last pointed -- and run the bundled Python, pandoc, and TeX
from their resources folder.

Usage: python3 app/main.py [Qt/Chromium options, e.g. --no-sandbox]
"""
import os
import sys
from pathlib import Path

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QLocale, QSettings, QStandardPaths, Qt
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtWebEngineCore import QWebEngineProfile
    from PySide6.QtWidgets import QApplication
except ImportError as err:
    app_dir = Path(__file__).resolve().parent
    sys.exit(
        f"The editor app needs PySide6 with Qt WebEngine ({err}).\n"
        "Install it into a virtual environment that `make app` will find:\n"
        f"  python3 -m venv {app_dir / '.venv'}\n"
        f"  {app_dir / '.venv' / 'bin' / 'pip'} install -r {app_dir / 'requirements.txt'}\n"
        "or, for a PySide6 installed elsewhere: make app APP_PYTHON=/path/to/python"
    )

import theme
from pipeline import REPO_ROOT
from window import APP_NAME, MainWindow

APP_DIR = Path(__file__).resolve().parent
# In a standalone build the pipeline (REPO_ROOT: scripts/, settings/, this
# app) sits in a resources folder next to the programs it runs -- see
# scripts/bundle_common.sh.
RESOURCES = REPO_ROOT.parent


def is_packaged():
    return (RESOURCES / "texlive").is_dir() and (RESOURCES / "pandoc").is_dir()


def packaged_tools():
    """How the standalone build reaches its bundled helper programs, laid
    out per platform (the bundled Python is the one running this).
    """
    windows = sys.platform == "win32"
    tex_platform = {"win32": "windows", "darwin": "universal-darwin"}.get(sys.platform, "x86_64-linux")
    return {
        "path_dirs": [
            RESOURCES / "pandoc" if windows else RESOURCES / "pandoc" / "bin",
            RESOURCES / "texlive" / "bin" / tex_platform,
        ],
        "direct_build": True,
    }


def spellcheck_dictionaries():
    """Where Qt WebEngine's spellcheck dictionaries (<language>.bdic
    files) are, if anywhere: the standalone builds ship one, and a
    qtwebengine_dictionaries folder in the app's data directory adds or
    replaces languages. Returns (folder, [languages]) or None.
    """
    data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    for folder in (
        os.environ.get("QTWEBENGINE_DICTIONARIES_PATH"),
        Path(data_dir) / "qtwebengine_dictionaries",
        RESOURCES / "qtwebengine_dictionaries",
    ):
        languages = sorted(p.stem for p in Path(folder).glob("*.bdic")) if folder else []
        if languages:
            return str(folder), languages
    return None


def enable_spellcheck(dictionaries):
    """Underline misspellings in the editor, in the system's language if
    there's a dictionary for it, else in every language there is one for.
    """
    _, languages = dictionaries
    system = QLocale.system().bcp47Name()
    preferred = [lang for lang in languages if lang == system or lang.split("-")[0] == system.split("-")[0]]
    profile = QWebEngineProfile.defaultProfile()
    profile.setSpellCheckLanguages(preferred[:1] or languages)
    profile.setSpellCheckEnabled(True)


def main():
    QCoreApplication.setOrganizationName("markdown-cornell-notes")
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    # Before the web engine starts: it reads this once.
    dictionaries = spellcheck_dictionaries()
    if dictionaries:
        os.environ["QTWEBENGINE_DICTIONARIES_PATH"] = dictionaries[0]

    # Matches the desktop entry (markdown-cornell-notes.desktop), so
    # desktops match the running window to it.
    QGuiApplication.setDesktopFileName("markdown-cornell-notes")
    if sys.platform == "win32":
        # Its own taskbar identity (and so the window's icon there), rather
        # than being grouped under Python's.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("io.github.forloop11.markdown-cornell-notes")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_DIR / "build-resources" / "icon.png")))
    theme.apply(app, QSettings().value("appearance", "system"))
    if dictionaries:
        enable_spellcheck(dictionaries)

    if is_packaged():
        remembered = QSettings().value("projectRoot", "")
        options = {"packaged": True, "api_options": {"tools": packaged_tools()}}
        if remembered and Path(remembered).is_dir():
            window = MainWindow(remembered, **options)
        else:
            documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
            window = MainWindow(Path(documents) / "Cornell Notes", scaffold_if_missing=True, **options)
    else:
        # Same "operate on CWD" model as the CLI: `make app` (or the
        # installed `markdown-cornell-notes app`) runs from the project
        # directory.
        window = MainWindow(Path.cwd())
    window.show()
    # One window per project, so closing it ends the app, macOS included.
    code = app.exec()
    # The window's web pages have to be gone before Qt tears down the
    # profile they use.
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    sys.exit(code)


if __name__ == "__main__":
    main()
