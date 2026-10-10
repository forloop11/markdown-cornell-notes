"""The file explorer down the window's left side: assets/ as a tree, for
managing the files notes link to with ![alt](assets/...) -- add, move (by
dragging), rename, delete. The app bar's hamburger button shows and hides
it.

The tree only displays what's on disk (a QFileSystemModel, which also
notices changes made outside the app); every change goes through api.py,
so names are sanitized and can't lead outside assets/.
"""
from pathlib import Path

from PySide6.QtCore import QDir, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFileIconProvider,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QTreeView,
    QVBoxLayout,
)

import theme
from api import IMAGE_SUFFIXES
from pipeline import PipelineError
from widgets import NameDialog, icon_button, label


class AssetIcons(QFileIconProvider):
    """The app's own folder and file icons, in the current palette --
    rather than the desktop icon theme's, which a standalone build may not
    find.
    """

    def icon(self, info):
        is_folder = info.isDir() if hasattr(info, "isDir") else info == QFileIconProvider.IconType.Folder
        return theme.icon("folder", "primary") if is_folder else theme.icon("file", "muted")


class AssetsTree(QTreeView):
    """The tree itself. Dropping files on it -- dragged from within the
    tree, or in from a file manager -- is reported through `dropped`
    rather than acted on, so the explorer can do the move through the api.
    """

    dropped = Signal(list, str)  # (local file paths, the folder path they landed on)

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setAnimated(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _files(self, event):
        return [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]

    def folder_at(self, position):
        """The folder a drop at `position` lands in: the folder under the
        pointer, the folder holding the file under it, or assets/ itself.
        """
        model = self.model()
        index = self.indexAt(position)
        if not index.isValid():
            return model.rootPath()
        return model.filePath(index) if model.isDir(index) else model.filePath(index.parent())

    def dragEnterEvent(self, event):
        if self._files(event):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self._files(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = self._files(event)
        if files:
            event.acceptProposedAction()
            self.dropped.emit(files, self.folder_at(event.position().toPoint()))


class AssetsExplorer(QFrame):
    changed = Signal()  # something under assets/ changed (here or outside the app)
    failed = Signal(str)  # an operation's error message

    def __init__(self):
        super().__init__()
        self.setObjectName("explorer")
        self.setMinimumWidth(180)
        self.api = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QFrame()
        head.setObjectName("explorer-head")
        row = QHBoxLayout(head)
        row.setContentsMargins(14, 8, 8, 8)
        row.setSpacing(4)
        self._title = label("ASSETS", "pane-tag")
        row.addWidget(self._title, 1)
        row.addWidget(icon_button("folder-plus", "New folder", lambda: self.create_folder(self.target_dir())))
        row.addWidget(icon_button("upload", "Add files…", lambda: self.choose_files(self.target_dir())))
        layout.addWidget(head)

        self.model = QFileSystemModel(self)
        self.model.setReadOnly(True)
        self.model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self.refresh_icons()
        self.tree = AssetsTree()
        self.tree.setModel(self.model)
        for column in range(1, self.model.columnCount()):
            self.tree.hideColumn(column)
        self.tree.dropped.connect(self.drop)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.doubleClicked.connect(self._double_clicked)
        # Ctrl+C on the selected file: its link, ready to paste into the editor.
        copy = QShortcut(QKeySequence.StandardKey.Copy, self.tree, context=Qt.ShortcutContext.WidgetShortcut)
        copy.activated.connect(self._copy_selected)
        rename = QShortcut(QKeySequence(Qt.Key.Key_F2), self.tree, context=Qt.ShortcutContext.WidgetShortcut)
        rename.activated.connect(self._rename_selected)
        layout.addWidget(self.tree, 1)

        self._hint = label("", "explorer-hint")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)
        self._set_hint()

        # One `changed` for a burst of file-system events (a folder of
        # files dropped in arrives as many).
        self._notify = QTimer(self)
        self._notify.setSingleShot(True)
        self._notify.setInterval(250)
        self._notify.timeout.connect(self.changed)
        for signal in (self.model.rowsInserted, self.model.rowsRemoved, self.model.fileRenamed):
            signal.connect(lambda *_: self._notify.start())

    def set_count(self, count):
        """Show how many files assets/ holds, folders and all."""
        self._title.setText(f"ASSETS ({count})")

    def refresh_icons(self):
        """Redraw the tree's icons (the light/dark palette changed)."""
        self._icons = AssetIcons()
        self.model.setIconProvider(self._icons)

    # --- Where things are -----------------------------------------------------

    def set_api(self, api):
        """Show `api`'s project's assets/ (if the project has one)."""
        self.api = api
        root = str(api.pipeline.assets_dir)
        self.model.setRootPath(root)
        self.tree.setRootIndex(self.model.index(root))

    def _assets_dir(self):
        return self.api.pipeline.assets_dir

    def subdir(self, path):
        """`path` (a folder under assets/) as the api names it: relative to
        assets/, "" for assets/ itself.
        """
        relative = Path(path).relative_to(self._assets_dir()).as_posix()
        return "" if relative == "." else relative

    def selected_paths(self):
        return [self.model.filePath(index) for index in self.tree.selectionModel().selectedRows(0)]

    def target_dir(self):
        """Where a new folder or added files go: the selected folder, the
        folder holding the selected file, or assets/ itself.
        """
        paths = self.selected_paths()
        if len(paths) != 1:
            return str(self._assets_dir())
        return paths[0] if Path(paths[0]).is_dir() else str(Path(paths[0]).parent)

    # --- Operations -----------------------------------------------------------

    def _run(self, call):
        """Run an api operation, reporting its errors (the listing it
        returns isn't needed: the tree watches the folder itself).
        Returns whether it went through.
        """
        try:
            listing = call()
        except PipelineError as err:
            self.failed.emit(str(err))
            return False
        except OSError as err:
            self.failed.emit(f"Unexpected error: {err}")
            return False
        for error in (listing or {}).get("errors", []):
            self.failed.emit(error)
        self._notify.start()
        return True

    def create_folder(self, folder):
        subdir = self.subdir(folder)
        dialog = NameDialog(
            self,
            "New folder",
            f"Folder name (in {_display(subdir)}/)",
            "Create",
            lambda name: self.api.create_asset_folder(subdir, name),
        )
        if dialog.exec():
            self.tree.expand(self.model.index(folder))
            self._notify.start()

    def choose_files(self, folder):
        subdir = self.subdir(folder)
        paths, _ = QFileDialog.getOpenFileNames(self, f"Add files to {_display(subdir)}")
        if paths:
            self.add_files(paths, folder)

    def add_files(self, paths, folder):
        subdir = self.subdir(folder)
        if self._run(lambda: self.api.add_assets(subdir, paths)):
            self.tree.expand(self.model.index(folder))

    def rename(self, path, new_name=None):
        """Rename the file or folder at `path` -- asking for the new name
        unless one is given. Links to it in notes aren't rewritten.
        """
        parent, name = self.subdir(str(Path(path).parent)), Path(path).name
        is_folder = Path(path).is_dir()
        operation = self.api.rename_asset_folder if is_folder else self.api.rename_asset
        if new_name is not None:
            self._run(lambda: operation(parent, name, new_name))
            return
        dialog = NameDialog(
            self,
            "Rename folder" if is_folder else "Rename file",
            "New name",
            "Rename",
            lambda new: operation(parent, name, new),
            text=name,
        )
        if dialog.exec():
            self._notify.start()

    def _rename_selected(self):
        paths = self.selected_paths()
        if len(paths) == 1:
            self.rename(paths[0])

    def delete(self, paths):
        """Delete the files and folders at `paths`, after asking."""
        names = [Path(p).name for p in paths]
        folders = [p for p in paths if Path(p).is_dir()]
        what = f"“{names[0]}”" if len(names) == 1 else f"these {len(names)} items"
        text = f"Delete {what}?" if not folders else f"Delete {what}, and everything inside?"
        box = QMessageBox(QMessageBox.Icon.Warning, "Delete", text, parent=self)
        delete = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(box.addButton(QMessageBox.StandardButton.Cancel))
        box.exec()
        if box.clickedButton() is not delete:
            return
        for path in paths:
            parent, name = self.subdir(str(Path(path).parent)), Path(path).name
            if path in folders:
                self._run(lambda: self.api.delete_asset_folder(parent, name))
            else:
                self._run(lambda: self.api.delete_asset(parent, name))

    def drop(self, paths, folder):
        """Files dropped on `folder`: ones already under assets/ move
        there, ones from anywhere else are copied in.
        """
        assets, dest = self._assets_dir(), self.subdir(folder)
        outside = []
        for path in map(Path, paths):
            if assets not in path.parents:
                outside.append(str(path))
            elif path.is_dir():
                self.failed.emit(f"{path.name} is a folder; only files can be moved.")
            elif path.parent != Path(folder):
                self._run(lambda: self.api.move_assets(self.subdir(str(path.parent)), [path.name], dest))
        if outside:
            self.add_files(outside, folder)
        self.tree.expand(self.model.index(folder))

    def copy_path(self, path):
        """Put the path a note would link to (assets/...) on the clipboard."""
        self._copy(_display(self.subdir(path)))

    def markdown_link(self, path):
        """The Markdown that links a note to the file or folder at `path`,
        relative to the project as the build expects: an image embed
        (![name](assets/...)) for an image, a plain link for anything else.
        """
        target = _display(self.subdir(path))
        # Only names from outside the app can hold these; <...> keeps the
        # link's target in one piece.
        if any(c in target for c in " ()"):
            target = f"<{target}>"
        text = Path(path).stem if Path(path).is_file() else Path(path).name
        text = text.replace("[", "\\[").replace("]", "\\]")
        image = Path(path).suffix.lower() in IMAGE_SUFFIXES and Path(path).is_file()
        return f"{'!' if image else ''}[{text}]({target})"

    def copy_link(self, path):
        """Put a ready-to-paste Markdown link to `path` on the clipboard."""
        self._copy(self.markdown_link(path))

    def _copy(self, text):
        QGuiApplication.clipboard().setText(text)
        self._set_hint(f"Copied {text}")
        QTimer.singleShot(2000, self._set_hint)

    def _set_hint(self, text=None):
        self._hint.setText(
            text or "Double-click a file to copy a link to paste into your notes. Drag files here to add or move them."
        )

    def _copy_selected(self):
        paths = self.selected_paths()
        if paths:
            self._copy("\n".join(self.markdown_link(path) for path in paths))

    # --- Mouse ----------------------------------------------------------------

    def _double_clicked(self, index):
        if not self.model.isDir(index):
            self.copy_link(self.model.filePath(index))

    def _context_menu(self, position):
        index = self.tree.indexAt(position)
        clicked = self.model.filePath(index) if index.isValid() else None
        selected = self.selected_paths()
        # A right-click outside the selection acts on what was clicked.
        targets = selected if clicked in selected else ([clicked] if clicked else [])
        folder = self.tree.folder_at(position)

        menu = QMenu(self)
        if len(targets) == 1:
            target = targets[0]
            menu.addAction("Copy Markdown Link", lambda: self.copy_link(target))
            menu.addAction("Copy Path", lambda: self.copy_path(target))
            menu.addAction("Rename…", lambda: self.rename(target))
        if targets:
            menu.addAction("Delete…", lambda: self.delete(targets))
            menu.addSeparator()
        menu.addAction("New Folder…", lambda: self.create_folder(folder))
        menu.addAction("Add Files…", lambda: self.choose_files(folder))
        menu.addSeparator()
        menu.addAction("Show in File Manager", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
        menu.popup(self.tree.viewport().mapToGlobal(position))


def _display(subdir):
    return f"assets/{subdir}" if subdir else "assets"
