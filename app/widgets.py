"""Small building blocks for the editor window (window.py): cards, chips,
message bars, labeled fields, and the name prompt.
"""
import re

from PySide6.QtCore import QEvent, QPoint, Qt, QTime, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import theme
from pipeline import PipelineError


def button(text="", kind=None, icon=None, tooltip=None, on_click=None):
    """A QPushButton styled as `kind` (see theme.py: "primary", "danger",
    "small", "link").
    """
    btn = QPushButton(text)
    if kind:
        btn.setProperty("kind", kind)
    if icon:
        theme.set_icon(btn, icon, "primary_text" if kind == "primary" else "danger" if kind == "danger" else "text")
    if tooltip:
        btn.setToolTip(tooltip)
    if on_click:
        btn.clicked.connect(lambda: on_click())
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def icon_button(icon, tooltip, on_click=None, color="text"):
    """A square, icon-only button, its icon drawn in the palette's `color`."""
    btn = QToolButton()
    btn.setProperty("kind", "icon")
    theme.set_icon(btn, icon, color)
    btn.setToolTip(tooltip)
    btn.setAccessibleName(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click:
        btn.clicked.connect(lambda: on_click())
    return btn


def label(text="", name=None, selectable=False):
    """A QLabel with object name `name` (what theme.py's rules match on)."""
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    if selectable:
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


def field(caption, widget):
    """`widget` under a small caption, as one form field."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    cap = label(caption, "field-label")
    cap.setBuddy(widget)
    layout.addWidget(cap)
    layout.addWidget(widget)
    widget.setAccessibleName(caption)
    return box


def set_tone(widget, tone):
    """Switch which of theme.py's `tone` rules styles `widget`."""
    if widget.property("tone") != tone:
        widget.setProperty("tone", tone)
        theme.repolish(widget)


class WrapBar(QFrame):
    """A bar holding a `left` and a `right` group side by side -- or, when
    it's too narrow for both, with `right` on a second row.
    """

    def __init__(self, left, right, margins=(24, 9, 24, 9), spacing=8):
        super().__init__()
        self._left, self._right = left, right
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(*margins)
        self._grid.setHorizontalSpacing(spacing * 2)
        self._grid.setVerticalSpacing(spacing)
        self._grid.setColumnStretch(0, 1)
        self._wrapped = None
        self._arrange(False)

    def _arrange(self, wrapped):
        if wrapped == self._wrapped:
            return
        self._wrapped = wrapped
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self._grid.addWidget(self._left, 0, 0, left)
        self._grid.addWidget(self._right, 1 if wrapped else 0, 0 if wrapped else 1, right)

    def _fits(self, width):
        margins = self._grid.contentsMargins()
        needed = self._left.sizeHint().width() + self._right.sizeHint().width() + self._grid.horizontalSpacing()
        return needed <= width - margins.left() - margins.right()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange(not self._fits(event.size().width()))

    def event(self, event):
        # A group changed size (a chip appeared, a label changed): re-check the fit.
        if event.type() == QEvent.Type.LayoutRequest:
            self._arrange(not self._fits(self.width()))
        return super().event(event)


class Chip(QLabel):
    """A small rounded status label ("Build succeeded", ...)."""

    def __init__(self, text="", tone=None, tooltip=None):
        super().__init__(text)
        self.setProperty("kind", "chip")
        if tone:
            self.setProperty("tone", tone)
        if tooltip:
            self.setToolTip(tooltip)


class MessageBar(QFrame):
    """A dismissible error or warning line."""

    def __init__(self, text, tone="error"):
        super().__init__()
        self.setProperty("kind", "msg")
        self.setProperty("tone", tone)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 6, 6)
        text_label = label(text, selectable=True)
        text_label.setWordWrap(True)
        layout.addWidget(text_label, 1)
        dismiss = QToolButton()
        dismiss.setProperty("kind", "plain")
        dismiss.setText("×")
        dismiss.setAccessibleName("Dismiss")
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.clicked.connect(self.dismiss)
        layout.addWidget(dismiss)

    def dismiss(self):
        self.setParent(None)
        self.deleteLater()


class Card(QFrame):
    """A bordered section with a title row that folds its body away."""

    toggled = Signal(bool)

    def __init__(self, title, body, expanded=True):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)

        self._header = QPushButton()
        self._header.setObjectName("card-header")
        self._header.setFlat(True)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.clicked.connect(lambda: self.set_expanded(not self.expanded))
        row = QHBoxLayout(self._header)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(8)
        self._arrow = QLabel()
        self._title = label(title, "card-title")
        self._hint = label("", "summary-hint")
        self._hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self._arrow)
        row.addWidget(self._title)
        row.addWidget(self._hint, 1)
        self._header.setMinimumHeight(26)
        layout.addWidget(self._header)

        self._body = body
        layout.addWidget(body)
        self.expanded = None
        self.set_expanded(expanded)

    def set_title(self, title):
        self._title.setText(title)
        self._header.setAccessibleName(title)

    def set_hint(self, text):
        """The one-line recap shown beside the title while folded."""
        self._hint_text = text
        self._hint.setText("" if self.expanded else text)

    def set_expanded(self, expanded):
        if expanded == self.expanded:
            return
        self.expanded = expanded
        self._body.setVisible(expanded)
        theme.set_icon(self._arrow, "chevron-down" if expanded else "chevron-right", "muted", 14)
        self._hint.setText("" if expanded else getattr(self, "_hint_text", ""))
        self.toggled.emit(expanded)


class TimePicker(QFrame):
    """The panel a TimeField opens: a column of hours beside a column of
    minutes, with buttons for the current time and for no time at all.
    """

    picked = Signal(str)  # "" (cleared) or "HH:MM"

    MINUTE_STEP = 5

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("time-picker")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(8)

        columns = QHBoxLayout()
        columns.setSpacing(8)
        self.hours = self._column(columns, "Hour", [f"{hour:02d}" for hour in range(24)])
        self.minutes = self._column(columns, "Minute", [f"{m:02d}" for m in range(0, 60, self.MINUTE_STEP)])
        layout.addLayout(columns)
        # An hour alone is a time on the hour, so the field follows along
        # as soon as one is picked; a minute completes the time.
        self.hours.itemClicked.connect(lambda _: self._emit())
        self.minutes.itemClicked.connect(lambda _: (self._emit(), self.close()))

        buttons = QHBoxLayout()
        buttons.addWidget(button("Clear", "link", on_click=lambda: (self.picked.emit(""), self.close())))
        buttons.addStretch(1)
        buttons.addWidget(button("Now", "small", on_click=self._pick_now))
        layout.addLayout(buttons)

    def _column(self, layout, caption, entries):
        box = QVBoxLayout()
        box.setSpacing(4)
        box.addWidget(label(caption, "field-label"))
        column = QListWidget()
        column.addItems(entries)
        column.setAccessibleName(caption)
        column.setFixedSize(72, 196)
        column.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        box.addWidget(column)
        layout.addLayout(box)
        return column

    def show_time(self, value):
        """Select `value` ("HH:MM", or "" for none) in the columns. Minutes
        between the steps select the step before them.
        """
        hour, minute = (int(part) for part in value.split(":")) if value else (None, None)
        for column, row in ((self.hours, hour), (self.minutes, None if minute is None else minute // self.MINUTE_STEP)):
            column.setCurrentRow(-1 if row is None else row)
            if row is not None:
                column.scrollToItem(column.item(row), QListWidget.ScrollHint.PositionAtCenter)
        if value == "":
            # Nothing chosen yet: open on the working day rather than midnight.
            self.hours.scrollToItem(self.hours.item(9), QListWidget.ScrollHint.PositionAtTop)

    def pick(self, hour=None, minute=None):
        """Choose an hour and/or minute, as clicking them would."""
        if hour is not None:
            self.hours.setCurrentRow(hour)
        if minute is not None:
            self.minutes.setCurrentRow(minute // self.MINUTE_STEP)
        self._emit()

    def _emit(self):
        hour = self.hours.currentRow()
        if hour < 0:
            if self.minutes.currentRow() < 0:
                return
            # A minute picked first: assume the hour the panel opened on.
            hour = 9
            self.hours.setCurrentRow(hour)
        minute = max(self.minutes.currentRow(), 0) * self.MINUTE_STEP
        self.picked.emit(f"{hour:02d}:{minute:02d}")

    def _pick_now(self):
        now = QTime.currentTime()
        self.picked.emit(f"{now.hour():02d}:{now.minute():02d}")
        self.close()


class TimeField(QLineEdit):
    """A time of day: picked from the panel its clock button (or the Down
    key) opens, or typed as HH:MM -- or left blank. `changed` fires with
    the committed value ("" or "HH:MM").
    """

    changed = Signal(str)
    _TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")

    def __init__(self):
        super().__init__()
        self.setPlaceholderText("--:--")
        self._value = ""
        self._picker = None
        self._clock = self.addAction(theme.icon("clock", "muted"), QLineEdit.ActionPosition.TrailingPosition)
        self._clock.setToolTip("Pick a time")
        self._clock.triggered.connect(self.open_picker)
        self.editingFinished.connect(self._commit)

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        self.setText(value)

    def picker(self):
        """The picker panel, made the first time it's needed."""
        if self._picker is None:
            self._picker = TimePicker(self)
            self._picker.picked.connect(self._picked)
        return self._picker

    def open_picker(self):
        picker = self.picker()
        picker.show_time(self._value)
        picker.adjustSize()
        picker.move(self.mapToGlobal(QPoint(0, self.height() + 2)))
        picker.show()

    def _picked(self, value):
        self.setText(value)
        self._commit()

    def _commit(self):
        text = self.text().strip()
        match = self._TIME_RE.fullmatch(text)
        if match and int(match[1]) < 24 and int(match[2]) < 60:
            text = f"{int(match[1]):02d}:{match[2]}"
        elif text:
            # Not a time: back to the last one that was.
            self.setText(self._value)
            return
        self.setText(text)
        if text != self._value:
            self._value = text
            self.changed.emit(text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Down:
            self.open_picker()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event):
        # The clock is drawn in the palette's colors; redraw it when they change.
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange) and hasattr(self, "_clock"):
            self._clock.setIcon(theme.icon("clock", "muted"))
        super().changeEvent(event)


class ChoiceField(QComboBox):
    """One of a long list of `options`, found by typing any part of it --
    or left blank. Text that isn't an option snaps back to the last valid
    choice. `changed` fires with the committed value.
    """

    changed = Signal(str)

    def __init__(self, options, placeholder=""):
        super().__init__()
        self._options = set(options)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.addItem("")
        self.addItems(options)
        self.setMaxVisibleItems(14)
        completer = self.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(completer.CompletionMode.PopupCompletion)
        self.lineEdit().setPlaceholderText(placeholder)
        self._value = ""
        self.activated.connect(lambda _: self._commit())
        self.lineEdit().editingFinished.connect(self._commit)
        completer.activated.connect(lambda _: self._commit())

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        self.setEditText(value)

    def _commit(self):
        text = self.currentText().strip()
        if text and text not in self._options:
            self.setEditText(self._value)
            return
        if text != self._value:
            self._value = text
            self.changed.emit(text)


class NameDialog(QDialog):
    """Ask for a name, and keep asking until `accept_name(name)` takes it:
    a PipelineError it raises (taken, empty, ...) is shown under the field
    instead of closing the dialog.
    """

    def __init__(self, parent, title, caption, action, accept_name, text="", placeholder=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        self._accept_name = accept_name
        self.result_value = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        self._input = QLineEdit(text)
        self._input.setPlaceholderText(placeholder)
        self._input.selectAll()
        layout.addWidget(field(caption, self._input))
        self._error = label("", "error-text")
        self._error.setWordWrap(True)
        self._error.hide()
        layout.addWidget(self._error)

        buttons = QDialogButtonBox()
        ok = buttons.addButton(action, QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setProperty("kind", "primary")
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        try:
            self.result_value = self._accept_name(self._input.text())
        except PipelineError as err:
            self._error.setText(str(err))
            self._error.show()
            self._input.setFocus()
            return
        self.accept()
