from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
)


def _set_view(mw, view_key: str) -> None:
    idx = mw.date_navigation_dock.view_cb.findData(view_key)
    if idx >= 0:
        mw.date_navigation_dock.view_cb.setCurrentIndex(idx)


class _PreviousYearShortcutFilter(QObject):
    def __init__(self, mw):
        super().__init__(mw)
        self._mw = mw
        self._hold_active = False
        self._hold_previous_state = False

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            return self._handle_key_press(event)
        if event.type() == QEvent.Type.KeyRelease:
            return self._handle_key_release(event)
        if event.type() in (QEvent.Type.ApplicationDeactivate, QEvent.Type.WindowDeactivate):
            self._restore_hold_state()
        return False

    def _handle_key_press(self, event) -> bool:
        if event.isAutoRepeat() or event.key() != Qt.Key.Key_V:
            return False
        if event.modifiers() != (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            return False
        if self._editable_widget_has_focus():
            return False

        if self._mw.previous_year_shortcut_mode() == "toggle":
            self._mw.toggle_previous_year()
            return True

        if not self._hold_active:
            self._hold_active = True
            self._hold_previous_state = bool(getattr(self._mw, "_previous_year_enabled", False))
            self._mw.set_previous_year_enabled(True)
        return True

    def _handle_key_release(self, event) -> bool:
        if event.isAutoRepeat() or event.key() != Qt.Key.Key_V or not self._hold_active:
            return False
        self._restore_hold_state()
        return True

    def _restore_hold_state(self) -> None:
        if not self._hold_active:
            return
        self._hold_active = False
        self._mw.set_previous_year_enabled(self._hold_previous_state)

    @staticmethod
    def _editable_widget_has_focus() -> bool:
        widget = QApplication.focusWidget()
        editable_types = (QLineEdit, QTextEdit, QPlainTextEdit)
        while widget is not None:
            if isinstance(widget, editable_types):
                return True
            widget = widget.parentWidget()
        return False


def install_main_window_shortcuts(mw) -> None:
    # F5 refresh; Alt+Left/Alt+Right previous/next period; Ctrl+1 week; Ctrl+2 day;
    # Ctrl+3 month; Ctrl+N new Termin; Ctrl+Shift+S settings; Ctrl+I import;
    # Ctrl+Shift+K conflict settings tab; Ctrl+E export; Ctrl+Shift+R reset layouts; Ctrl+T today;
    # Ctrl+Alt+T/L/R/F/H new Termin/LVA/Raum/Freier Tag/Studienrichtung.
    # Ctrl+Alt+V: previous-year view, either hold or toggle depending on settings.
    # Focused calendar TerminCard: Delete/Backspace unassign; Ctrl+Delete/Ctrl+Backspace delete.
    mw.act_refresh.setShortcut(QKeySequence("F5"))
    mw.act_settings.setShortcut(QKeySequence("Ctrl+Shift+S"))
    mw.act_import.setShortcut(QKeySequence("Ctrl+I"))
    mw.act_konflikte.setShortcut(QKeySequence("Ctrl+Shift+K"))
    mw.act_export.setShortcut(QKeySequence("Ctrl+E"))
    mw.act_new_termin.setShortcut(QKeySequence("Ctrl+N"))
    mw.act_reset_layouts.setShortcut(QKeySequence("Ctrl+Shift+R"))
    mw.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
    mw.act_redo.setShortcut(QKeySequence("Ctrl+Y"))

    shortcuts = []

    def bind(seq, handler) -> None:
        sc = QShortcut(QKeySequence(seq), mw)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(handler)
        shortcuts.append(sc)

    def bind_planner(seq, handler) -> None:
        for target in (mw.planner.day_table, mw.planner.week_table, mw.planner.month_table):
            sc = QShortcut(QKeySequence(seq), target)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(handler)
            shortcuts.append(sc)

    bind("Alt+Left", mw._on_nav_prev)
    bind("Alt+Right", mw._on_nav_next)
    bind("Ctrl+1", lambda: _set_view(mw, "week"))
    bind("Ctrl+2", lambda: _set_view(mw, "day"))
    bind("Ctrl+3", lambda: _set_view(mw, "month"))
    bind("Ctrl+T", mw.jump_to_today)
    bind("Ctrl+Alt+T", mw.create_termin)
    bind("Ctrl+Alt+L", lambda: mw.create_data_editor_entity("lva"))
    bind("Ctrl+Alt+R", lambda: mw.create_data_editor_entity("room"))
    bind("Ctrl+Alt+F", lambda: mw.create_data_editor_entity("free_day"))
    bind("Ctrl+Alt+H", lambda: mw.create_data_editor_entity("studienrichtung"))

    bind_planner("Delete", mw.unassign_focused_calendar_termin)
    bind_planner("Backspace", mw.unassign_focused_calendar_termin)
    bind_planner("Ctrl+Delete", mw.delete_focused_calendar_termin)
    bind_planner("Ctrl+Backspace", mw.delete_focused_calendar_termin)

    previous_year_filter = _PreviousYearShortcutFilter(mw)
    app = QApplication.instance()
    if app is not None:
        app.installEventFilter(previous_year_filter)
    mw._previous_year_shortcut_filter = previous_year_filter
    mw._shortcuts = shortcuts
