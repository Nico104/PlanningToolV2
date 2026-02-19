from pathlib import Path
from types import SimpleNamespace
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QTabWidget

from ...core.models import Lehrveranstaltung, Raum, Semester, Termin
from ..utils.crud_handlers import CrudHandlers
from ..components.widgets.editor_tab_widget import EditorTab, make_item, selected_id
from ..utils.datetime_utils import fmt_date, fmt_time



class DataEditorDock(QDockWidget):
    """
    Ein Dock für Daten: LVA, Räume, Semester, Freie Tage
    Keine Inline-Edits
    """

    def __init__(self, parent, ds, data_dir: Path, on_data_changed=None):
        super().__init__("Data Editor", parent)
        self.setAllowedAreas(Qt.AllDockWidgetAreas)

        self.ds = ds
        self.data_dir = data_dir
        self.on_data_changed = on_data_changed

        wrap = QWidget(self)
        root = QVBoxLayout(wrap)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.tabs = QTabWidget(wrap)
        root.addWidget(self.tabs, 1)

        # Tabs
        self.tab_lva = EditorTab("LVA", ["ID", "Name", "Vortragende", "E-Mail", "Typen"], self.tabs)
        self.tab_rooms = EditorTab("Räume", ["ID", "Name", "Kapazität"], self.tabs)
        self.tab_sem = EditorTab("Semester", ["ID", "Name", "Start", "Ende"], self.tabs)
        self.tab_free = EditorTab("Freie Tage", ["Art", "Datum", "Von", "Bis", "Beschreibung"], self.tabs)
        self.tab_termine = EditorTab(
            "Termine",
            ["ID", "Datum", "Von", "Bis", "Typ", "LVA", "Raum", "Semester", "Gruppe"],
            self.tabs
        )
        
        self.tabs.addTab(self.tab_termine, "Termine")

        self.tabs.addTab(self.tab_lva, "LVAs")
        self.tabs.addTab(self.tab_rooms, "Räume")
        self.tabs.addTab(self.tab_sem, "Semester")
        self.tabs.addTab(self.tab_free, "Freie Tage")

        self.setWidget(wrap)

        # Connect tab change signal to refresh Termine tab
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._crud = CrudHandlers(
            ds=self.ds,
            parent=self,
            planner=SimpleNamespace(refresh=self._refresh_and_notify),
            lva_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_lva.table)),
            room_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_rooms.table)),
            sem_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_sem.table)),
            termin_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_termine.table)),
            freie_tage_dock=SimpleNamespace(selected_row=lambda: self.tab_free.table.currentRow()),
            data_dir=self.data_dir,
        )

        self.tab_lva.add_clicked.connect(self._crud.add_lva)
        self.tab_lva.edit_clicked.connect(self._crud.edit_lva)
        self.tab_lva.delete_clicked.connect(self._crud.del_lva)

        self.tab_rooms.add_clicked.connect(self._crud.add_room)
        self.tab_rooms.edit_clicked.connect(self._crud.edit_room)
        self.tab_rooms.delete_clicked.connect(self._crud.del_room)

        self.tab_sem.add_clicked.connect(self._crud.add_semester)
        self.tab_sem.edit_clicked.connect(self._crud.edit_semester)
        self.tab_sem.delete_clicked.connect(self._crud.del_semester)

        self.tab_free.add_clicked.connect(self._crud.add_freie_tage)
        self.tab_free.edit_clicked.connect(self._crud.edit_freie_tage)
        self.tab_free.delete_clicked.connect(self._crud.del_freie_tage)
        
        self.tab_termine.add_clicked.connect(self._crud.add_termin)
        self.tab_termine.edit_clicked.connect(self._crud.edit_termin)
        self.tab_termine.delete_clicked.connect(self._crud.del_termin)

    def _on_tab_changed(self, index):
        # Only trigger refresh if switching from another tab to Termine
        if self.tabs.widget(index) == self.tab_termine:
            if self.on_data_changed:
                self.on_data_changed()


    def refresh_all(self) -> None:
        self._refresh_lvas()
        self._refresh_rooms()
        # self._refresh_semester()  # removed, no global semester info anymore
        self._refresh_freie_tage()
        self._refresh_termine()

    # Refresh tables
    def _refresh_lvas(self) -> None:
        lvas: List[Lehrveranstaltung] = self.ds.load_lvas()
        rows = [
            [
                l.id,
                l.name,
                getattr(l.vortragende, "name", ""),
                getattr(l.vortragende, "email", ""),
                ", ".join(getattr(l, "typ", []) or []),
            ]
            for l in lvas
        ]
        self._fill_table(self.tab_lva.table, rows)

    def _refresh_rooms(self) -> None:
        rooms: List[Raum] = self.ds.load_raeume()
        rows = [[r.id, r.name, str(r.kapazitaet)] for r in rooms]
        self._fill_table(self.tab_rooms.table, rows)

    # def _refresh_semester(self) -> None:
    #     # No global semester info anymore
    #     pass

    def _refresh_freie_tage(self) -> None:
        freie = self._crud.read_freie_tage()
        rows = []
        for it in freie:
            if "datum" in it and it.get("datum"):
                art = "single"
                datum = str(it.get("datum", ""))
                von = ""
                bis = ""
            else:
                art = "range"
                datum = ""
                von = str(it.get("von_datum", ""))
                bis = str(it.get("bis_datum", ""))
            beschr = str(it.get("beschreibung", ""))
            rows.append([art, datum, von, bis, beschr])
        self._fill_table(self.tab_free.table, rows)
        
    def _refresh_termine(self) -> None:
        def safe_date(d) -> str:
            try:
                return fmt_date(d) if d else ""
            except Exception:
                return str(d) if d is not None else ""

        def safe_time(t) -> str:
            try:
                return fmt_time(t) if t else ""
            except Exception:
                return str(t) if t is not None else ""

        termine: List[Termin] = self.ds.load_termine()
        rows = []
        for tm in termine:
            start_zeit = getattr(tm, "start_zeit", None)
            end_zeit = tm.get_end_time() if hasattr(tm, "get_end_time") else None
            rows.append([
                getattr(tm, "id", ""),
                safe_date(getattr(tm, "datum", None)),
                safe_time(start_zeit),
                safe_time(end_zeit),
                getattr(tm, "typ", ""),
                getattr(tm, "lva_id", ""),
                getattr(tm, "raum_id", ""),
                getattr(tm, "semester_id", ""),
                getattr(tm, "gruppe", "") or "",
            ])
        self._fill_table(self.tab_termine.table, rows)



    def _refresh_and_notify(self) -> None:
        self.refresh_all()
        if self.on_data_changed:
            self.on_data_changed()

    def _fill_table(self, table, rows: List[List[object]]) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for row_vals in rows:
            row = table.rowCount()
            table.insertRow(row)
            for c, v in enumerate(row_vals):
                table.setItem(row, c, make_item(str(v)))
        table.setSortingEnabled(True)
        table.resizeColumnsToContents()


