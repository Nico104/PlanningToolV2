from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut


def _set_view(mw, view_key: str) -> None:
    idx = mw.date_navigation_dock.view_cb.findData(view_key)
    if idx >= 0:
        mw.date_navigation_dock.view_cb.setCurrentIndex(idx)


def install_main_window_shortcuts(mw) -> None:
    # F5 refresh; Alt+Left/Alt+Right previous/next period; Ctrl+1 week; Ctrl+2 day;
    # Ctrl+3 month; Ctrl+N new Termin; Ctrl+Shift+S settings; Ctrl+I import;
    # Ctrl+Shift+K conflicts; Ctrl+E export; Ctrl+Shift+R reset layouts; Ctrl+T today;
    # Ctrl+Alt+T/L/S/R/F/G/H new Termin/LVA/Semester/Raum/Freier Tag/Geplantes Semester/Fachrichtung.
    # Focused calendar TerminCard: Delete/Backspace unassign; Ctrl+Delete/Ctrl+Backspace delete.
    mw.act_refresh.setShortcut(QKeySequence("F5"))
    mw.act_settings.setShortcut(QKeySequence("Ctrl+Shift+S"))
    mw.act_import.setShortcut(QKeySequence("Ctrl+I"))
    mw.act_konflikte.setShortcut(QKeySequence("Ctrl+Shift+K"))
    mw.act_export.setShortcut(QKeySequence("Ctrl+E"))
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
    bind("Ctrl+N", lambda: mw.create_data_editor_entity("termin"))
    bind("Ctrl+Alt+T", lambda: mw.create_data_editor_entity("termin"))
    bind("Ctrl+Alt+L", lambda: mw.create_data_editor_entity("lva"))
    bind("Ctrl+Alt+S", lambda: mw.create_data_editor_entity("semester"))
    bind("Ctrl+Alt+R", lambda: mw.create_data_editor_entity("room"))
    bind("Ctrl+Alt+F", lambda: mw.create_data_editor_entity("free_day"))
    bind("Ctrl+Alt+G", lambda: mw.create_data_editor_entity("planned_semester"))
    bind("Ctrl+Alt+H", lambda: mw.create_data_editor_entity("fachrichtung"))

    bind_planner("Delete", mw.unassign_focused_calendar_termin)
    bind_planner("Backspace", mw.unassign_focused_calendar_termin)
    bind_planner("Ctrl+Delete", mw.delete_focused_calendar_termin)
    bind_planner("Ctrl+Backspace", mw.delete_focused_calendar_termin)

    mw._shortcuts = shortcuts
