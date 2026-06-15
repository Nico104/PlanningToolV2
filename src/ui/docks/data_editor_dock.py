from types import SimpleNamespace
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QTabWidget

from ...core.models import Lehrveranstaltung, Raum, Termin
from ..utils.crud_handlers import CrudHandlers
from ..components.widgets.editor_tab_widget import EditorTab, make_item, selected_id
from ..utils.datetime_utils import fmt_date, fmt_time



class DataEditorDock(QDockWidget):
    """
    Dock widget with tabbed CRUD editors for master data:
    LVAs, rooms, terms, free days, and Studienrichtungen.
    """

    def __init__(self, parent, ds, on_data_changed=None):
        super().__init__("Dateneditor", parent)
        self.setAllowedAreas(Qt.AllDockWidgetAreas)

        self.ds = ds
        self.on_data_changed = on_data_changed

        wrap = QWidget(self)
        root = QVBoxLayout(wrap)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.tabs = QTabWidget(wrap)
        root.addWidget(self.tabs, 1)

        # Tabs
        self.tab_lva = EditorTab(
            "LVA",
            ["LVA-Nr.", "Name", "ECTS", "Vortragende", "E-Mail", "Studiensemester", "Studienrichtung"],
            self.tabs,
            id_column=0,
        )
        self.tab_studienrichtung = EditorTab("Studienrichtungen", ["ID", "Name"], self.tabs, id_column=0)
        self.tab_rooms = EditorTab("Räume", ["Raumnummer", "Raum", "Kapazität"], self.tabs, id_column=0)
        self.tab_free = EditorTab(
            "Freie Tage",
            ["Typ", "Art", "Datum", "Von", "Bis", "Beschreibung", "ID"],
            self.tabs,
            id_column=6,
        )
        self.tab_termine = EditorTab(
            "Termine",
            [
                "Name", "Datum", "Datum bis", "Periodizität", "Von", "Bis", "Typ",
                "LVA-Nr.", "Raum", "Semester", "Gruppe", "Zu besprechen", "Hinweis", "ID",
            ],
            self.tabs,
            id_column=13,
        )
        self.tabs.addTab(self.tab_termine, "Termine")

        self.tabs.addTab(self.tab_lva, "LVAs")
        self.tabs.addTab(self.tab_rooms, "Räume")
        self.tabs.addTab(self.tab_free, "Freie Tage")
        self.tabs.addTab(self.tab_studienrichtung, "Studienrichtungen")

        self.setWidget(wrap)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._crud = CrudHandlers(
            ds=self.ds,
            parent=self,
            planner=SimpleNamespace(refresh=self._refresh_and_notify),
            lva_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_lva.table)),
            studienrichtung_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_studienrichtung.table)),
            room_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_rooms.table)),
            termin_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_termine.table)),
            freie_tage_dock=SimpleNamespace(selected_id=lambda: selected_id(self.tab_free.table)),
            undo_service=getattr(parent, "undo_service", None),
        )

        self.tab_free.table.setColumnHidden(6, True)

        self.tab_lva.add_clicked.connect(self._crud.add_lva)
        self.tab_lva.edit_clicked.connect(self._crud.edit_lva)
        self.tab_lva.delete_clicked.connect(self._crud.del_lva)

        self.tab_studienrichtung.add_clicked.connect(self._crud.add_studienrichtung)
        self.tab_studienrichtung.edit_clicked.connect(self._crud.edit_studienrichtung)
        self.tab_studienrichtung.delete_clicked.connect(self._crud.del_studienrichtung)

        self.tab_rooms.add_clicked.connect(self._crud.add_room)
        self.tab_rooms.edit_clicked.connect(self._crud.edit_room)
        self.tab_rooms.delete_clicked.connect(self._crud.del_room)

        self.tab_free.add_clicked.connect(self._crud.add_freie_tage)
        self.tab_free.edit_clicked.connect(self._crud.edit_freie_tage)
        self.tab_free.delete_clicked.connect(self._crud.del_freie_tage)
        
        self.tab_termine.add_clicked.connect(self._crud.add_termin_from_data_editor)
        self.tab_termine.edit_clicked.connect(self._crud.edit_termin_from_data_editor)
        self.tab_termine.delete_clicked.connect(self._crud.del_termin)

    def set_termine_read_only(self, read_only: bool) -> None:
        self.tab_termine.set_actions_enabled(not bool(read_only))

    def _on_tab_changed(self, index):
        # when the user opens the Termine tab, make sure it reflects the latest planner state, but don’t trigger a global refresh on every tab switch
        if self.tabs.widget(index) == self.tab_termine:
            if self.on_data_changed:
                self.on_data_changed()

    def create_entity(self, entity: str) -> None:
        entity_map = {
            "termin": self.tab_termine,
            "lva": self.tab_lva,
            "room": self.tab_rooms,
            "free_day": self.tab_free,
            "studienrichtung": self.tab_studienrichtung,
        }

        tab = entity_map.get(entity)
        if tab is None:
            return
        if entity == "termin" and hasattr(tab, "_actions_enabled") and not tab._actions_enabled:
            return

        self.show()
        self.raise_()
        self.tabs.setCurrentWidget(tab)
        tab.btn_add.click()


    def refresh_all(self) -> None:
        self._refresh_lvas()
        self._refresh_studienrichtungen()
        self._refresh_rooms()
        self._refresh_freie_tage()
        self._refresh_termine()

    # Refresh tables
    def _refresh_lvas(self) -> None:
        lvas: List[Lehrveranstaltung] = self.ds.load_lvas()
        semester_data = self.ds.load_studiensemester()
        sem_id_to_name = {
            str(s.get("id", "")).strip(): str(s.get("name", "")).strip()
            for s in semester_data
            if str(s.get("id", "")).strip()
        }

        rows = [
            [
                l.id,
                l.name,
                getattr(l, "ects", ""),
                getattr(l.vortragende, "name", ""),
                getattr(l.vortragende, "email", ""),
                " / ".join([sem_id_to_name.get(sid, sid) for sid in getattr(l, "studiensemester", [])]),
                getattr(l, "studienrichtung", ""),
            ]
            for l in lvas
        ]
        self._fill_table(self.tab_lva.table, rows)

    def _refresh_rooms(self) -> None:
        rooms: List[Raum] = self.ds.load_raeume()
        rows = [[r.id, r.name, str(r.kapazitaet)] for r in rooms]
        self._fill_table(self.tab_rooms.table, rows)

    def _refresh_studienrichtungen(self) -> None:
        studienrichtungen = self.ds.load_studienrichtungen()
        rows = []
        for f in studienrichtungen:
            if isinstance(f, dict):
                rows.append([str(f.get("id", "")), str(f.get("name", ""))])
            else:
                txt = str(f)
                rows.append([txt, txt])
        self._fill_table(self.tab_studienrichtung.table, rows)


    def _refresh_freie_tage(self) -> None:
        freie = self.ds.load_freie_tage()
        rows = []
        for it in freie:
            typ = str(it.get("typ", ""))
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
            rows.append([typ, art, datum, von, bis, beschr, str(it.get("id", ""))])
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
        lva_by_id = {str(l.id): l for l in self.ds.load_lvas()}
        rows = []
        for tm in termine:
            start_zeit = getattr(tm, "start_zeit", None)
            end_zeit = tm.get_end_time() if hasattr(tm, "get_end_time") else None
            gruppe = getattr(tm, "gruppe", None)
            if gruppe and getattr(gruppe, 'name', None):
                name = getattr(gruppe, 'name', '')
                groesse = getattr(gruppe, 'groesse', None)
                if groesse is not None and str(groesse) != '':
                    gruppe_str = f"{name} ({groesse})"
                else:
                    gruppe_str = f"{name}"
            else:
                gruppe_str = ""
            termin_name = str(getattr(tm, "name", "") or "").strip()
            if not termin_name:
                lva_id = str(getattr(tm, "lva_id", "") or "").strip()
                lva = lva_by_id.get(lva_id)
                lva_name = str(getattr(lva, "name", "") or "").strip()
                typ = str(getattr(tm, "typ", "") or "").strip()
                parts = [p for p in (typ, lva_name or lva_id) if p]
                termin_name = " - ".join(parts) if parts else "(ohne Name)"
            rows.append([
                termin_name,
                safe_date(getattr(tm, "datum", None)),
                safe_date(getattr(tm, "datum_bis", None)),
                getattr(tm, "periodizitaet", "") or "",
                safe_time(start_zeit),
                safe_time(end_zeit),
                getattr(tm, "typ", ""),
                getattr(tm, "lva_id", ""),
                getattr(tm, "raum_id", ""),
                getattr(tm, "semester_id", ""),
                gruppe_str,
                "Ja" if bool(getattr(tm, "zu_besprechen", False)) else "Nein",
                getattr(tm, "besprechungshinweis", ""),
                getattr(tm, "id", ""),
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


