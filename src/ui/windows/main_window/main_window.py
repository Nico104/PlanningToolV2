from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QDialog, QMainWindow, QFileDialog, QMessageBox, QPushButton

from src.services.data_service import DataService

from src.ui.docks.termine_dock import TermineDock
from src.ui.docks.data_editor_dock import DataEditorDock
from src.ui.docks.conflicts_dock import ConflictsDock
from src.ui.docks.global_filter_dock import GlobalFilterDock
from src.ui.docks.date_navigation_dock import DateNavigationDock
from src.ui.utils.datetime_utils import date_to_qdate
from src.core.states import FilterState
from ...utils.crud_handlers import CrudHandlers
from .layout_manager import LayoutManager
from src.ui.planner.workspace import PlannerWorkspace
from ...dialogs import SettingsDialog
from src.ui.dialogs.konflikte_dialog import KonflikteDialog
from src.ui.dialogs.import_dialog import ImportDialog
from ...components.widgets.toast import Toast


class MainWindow(QMainWindow):
    """Main application window containing planner, docks etc...

    This class wires UI components, forwards CRUD operations, keeps filters in sync
    """

    def _apply_start_date(self, start_date) -> None:
        """Synchronize planner and navigation controls to the same start day/week"""

        monday = date_to_qdate(self.planner._align_to_monday(start_date))
        day_qdate = date_to_qdate(start_date)

        self.date_navigation_dock.view_cb.setCurrentIndex(
            self.date_navigation_dock.view_cb.findData("week")
        )
        self.date_navigation_dock.week_from.setDate(monday)
        self.date_navigation_dock.day_date.setDate(day_qdate)

        self.planner.view_cb.setCurrentIndex(self.planner.view_cb.findData("week"))
        self.planner.week_from.setDate(monday)
        self.planner.day_date.setDate(day_qdate)

    @staticmethod
    def _read_json(path: Path, default):
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _resolve_start_date_for_semester(self, semester_id: str):
        """given a semester id, what date should the UI jump to
        """

        sem_data = self._read_json(self.data_dir / "semester.json", {})
        sem_list = sem_data.get("semester", [])
        sem_obj = next((s for s in sem_list if s.get("id") == semester_id), None)
        if sem_obj and sem_obj.get("start"):
            try:
                return datetime.strptime(sem_obj["start"], "%Y-%m-%d").date()
            except Exception:
                pass

        termine_data = self._read_json(self.data_dir / "termine.json", {})
        termine = termine_data.get("termine", [])
        dates = []
        for t in termine:
            if t.get("semester_id") != semester_id:
                continue
            d = t.get("datum")
            if not d:
                continue
            try:
                dates.append(datetime.strptime(d, "%Y-%m-%d").date())
            except Exception:
                continue
        return min(dates) if dates else None

    def set_start_semester_and_reload(self, fachrichtung, semester):
        s = self.ds.load_settings()
        s["start_fachrichtung"] = fachrichtung
        s["start_semester"] = semester
        self.ds.save_settings(s)

        self.refresh_everything()

        start_date = self._resolve_start_date_for_semester(semester)
        if start_date:
            QTimer.singleShot(0, lambda: self._apply_start_date(start_date))

    def __init__(self, data_dir: Path):
        super().__init__()
        self.ds = DataService(data_dir)
        self.setWindowTitle("Planungstool")
        self.data_dir = data_dir

        self._build_menus()

        self.filter_state = FilterState()

        self.setDockOptions(
            QMainWindow.AllowTabbedDocks
            | QMainWindow.AllowNestedDocks
            | QMainWindow.AnimatedDocks
            | QMainWindow.GroupedDragging
        )

        self._setup_docks()

        self.crud = CrudHandlers(self)
        self.layout_mgr = LayoutManager(self)

        self._wire_signals()

        self.refresh_everything()
        self.layout_mgr.init_default()

        self.showMaximized()

    def open_settings(self) -> None:
        cur = self.ds.load_settings()
        old_data_path = cur.get("data_path", "")
        dlg = SettingsDialog(self, cur)
        if dlg.exec() != QDialog.Accepted or not dlg.result_settings:
            return

        s = cur
        s.update(dlg.result_settings)
        self.ds.save_settings(s)

        new_data_path = s.get("data_path", "")
        if new_data_path != old_data_path:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Gespeichert")
            msg.setText("Gespeichert. Für manche Einstellungen muss das Programm neu gestartet werden.")
            restart_btn = QPushButton("Neustart")
            ok_btn = msg.addButton(QMessageBox.Ok)
            msg.addButton(restart_btn, QMessageBox.AcceptRole)
            msg.setDefaultButton(ok_btn)
            msg.exec()
            if msg.clickedButton() == restart_btn:
                python = sys.executable
                subprocess.Popen([python] + sys.argv)
                sys.exit(0)
        else:
            Toast(self, "Gespeichert.", duration_ms=2500).show()
        self.refresh_everything()

    def _build_menus(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("Datei")
        self.act_refresh = QAction("Aktualisieren", self)
        self.act_refresh.triggered.connect(self.refresh_everything)
        file_menu.addAction(self.act_refresh)

        self.act_export = QAction("Exportieren…", self)
        self.act_export.triggered.connect(self.export_project)
        file_menu.addAction(self.act_export)

        self.act_import = QAction("Importieren…", self)
        self.act_import.triggered.connect(self.import_project)
        file_menu.addAction(self.act_import)

        self.view_menu = mb.addMenu("Ansicht")
        self.layout_menu = self.view_menu.addMenu("Layout")
        self.layout_group = QActionGroup(self)
        self.layout_group.setExclusive(True)
        self.act_save_layout = QAction("Aktuelles Layout speichern…", self)
        self.act_reset_layouts = QAction("Layouts zurücksetzen", self)

        tools_menu = mb.addMenu("Tools")
        self.act_settings = QAction("Settings…", self)
        self.act_settings.triggered.connect(self.open_settings)
        tools_menu.addAction(self.act_settings)

        self.act_konflikte = QAction("Konflikte…", self)
        self.act_konflikte.triggered.connect(self.open_konflikte_dialog)
        tools_menu.addAction(self.act_konflikte)

    def open_konflikte_dialog(self):
        conflicts_path = str(Path(__file__).resolve().parents[3] / "konflikte.json")
        dlg = KonflikteDialog(self, conflicts_path=conflicts_path)
        dlg.conflicts_changed.connect(self.refresh_conflicts)
        dlg.exec()

    def export_project(self) -> None:
        files = [
            "raeume.json",
            "lehrveranstaltungen.json",
            "termine.json",
            "semester.json",
            "fachrichtungen.json",
            "freie_tage.json",
            "geplante_semester.json",
        ]
        export_obj = {}
        for f in files:
            p = self.data_dir / f
            if p.exists():
                try:
                    export_obj[f] = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    export_obj[f] = p.read_text(encoding="utf-8")

        fn, _ = QFileDialog.getSaveFileName(
            self, "Export Datei speichern", str(self.data_dir), "JSON Files (*.json)"
        )
        if not fn:
            return
        try:
            Path(fn).write_text(
                json.dumps(export_obj, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            Toast(self, "Projekt exportiert.", duration_ms=2500).show()
        except Exception as e:
            QMessageBox.warning(self, "Export Fehler", f"Fehler beim Export: {e}")

    def import_project(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(
            self, "Import Datei öffnen", str(self.data_dir), "JSON Files (*.json)"
        )
        if not fn:
            return
        try:
            with open(fn, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Import Fehler", f"Fehler beim Lesen der Import-Datei: {e}")
            return

        normalized = {}
        known_keys = {
            "termine": "termine.json",
            "raeume": "raeume.json",
            "lehrveranstaltungen": "lehrveranstaltungen.json",
            "semester": "semester.json",
            "fachrichtungen": "fachrichtungen.json",
            "freie_tage": "freie_tage.json",
            "geplante_semester": "geplante_semester.json",
        }

        if isinstance(data, dict):
            if all(isinstance(k, str) and k.lower().endswith(".json") for k in data.keys()):
                normalized = data
            else:
                for k, target in known_keys.items():
                    if k in data:
                        normalized[target] = data[k] if isinstance(data[k], (dict, list)) else {k: data[k]}

                if not normalized:
                    for raw_key, val in data.items():
                        low = raw_key.lower()
                        for k, target in known_keys.items():
                            if k in low or (low.endswith(".json") and low.replace(".json", "") == k):
                                normalized[target] = val if isinstance(val, (dict, list)) else {k: val}

                if not normalized:
                    def search_and_map(obj):
                        if isinstance(obj, dict):
                            for kk, vv in obj.items():
                                if kk in known_keys:
                                    normalized[known_keys[kk]] = vv if isinstance(vv, (dict, list)) else {kk: vv}
                                else:
                                    search_and_map(vv)
                        elif isinstance(obj, list):
                            for it in obj:
                                search_and_map(it)

                    search_and_map(data)
        elif isinstance(data, list):
            normalized["termine.json"] = {"termine": data}
        else:
            QMessageBox.warning(self, "Import Fehler", "Unbekanntes Import-Format.")
            return

        if not normalized:
            QMessageBox.warning(self, "Import Fehler", "Keine importierbaren Daten gefunden.")
            return

        dlg = ImportDialog(self, self.data_dir, normalized)
        dlg.exec()
        Toast(self, "Import abgeschlossen.", duration_ms=3000).show()
        self.refresh_everything()

    def _setup_docks(self) -> None:
        self.global_filter_dock = GlobalFilterDock(self)
        self.global_filter_dock.setObjectName("dock_global_filters")
        self.addDockWidget(Qt.TopDockWidgetArea, self.global_filter_dock)

        self.date_navigation_dock = DateNavigationDock(self)
        self.date_navigation_dock.setObjectName("dock_date_navigation")
        self.addDockWidget(Qt.TopDockWidgetArea, self.date_navigation_dock)

        self.splitDockWidget(self.global_filter_dock, self.date_navigation_dock, Qt.Horizontal)

        self.planner = PlannerWorkspace(
            self,
            self.ds,
            on_data_changed=self.refresh_docks,
            global_filter_dock=self.date_navigation_dock,
        )
        self.setCentralWidget(self.planner)

        self.termine_dock = TermineDock(self)
        self.termine_dock.setObjectName("dock_termine")
        self.addDockWidget(Qt.LeftDockWidgetArea, self.termine_dock)

        self.conflicts_dock = ConflictsDock(self)
        self.conflicts_dock.setObjectName("dock_conflicts")
        self.addDockWidget(Qt.LeftDockWidgetArea, self.conflicts_dock)
        self.tabifyDockWidget(self.termine_dock, self.conflicts_dock)

        self.data_editor_dock = DataEditorDock(
            self,
            ds=self.ds,
            data_dir=self.data_dir,
            on_data_changed=self.refresh_everything,
        )
        self.data_editor_dock.setObjectName("dock_data_editor")
        self.tabifyDockWidget(self.termine_dock, self.data_editor_dock)
        self.termine_dock.raise_()

    def _wire_signals(self) -> None:
        self.termine_dock.termin_double_clicked.connect(self.crud.edit_termin_by_id)
        self.termine_dock.termin_delete_clicked.connect(self.crud.del_termin_by_id)
        self.termine_dock.termin_unassign_requested.connect(self._on_unassign_termin)
        self.termine_dock.termin_jump_requested.connect(self._on_jump_to_termin)

        self.conflicts_dock.conflict_items_highlight.connect(self.planner.highlight_termine)

        self.global_filter_dock.filtersChanged.connect(self._on_global_filters_changed)

        self.date_navigation_dock.navPrev.connect(self._on_nav_prev)
        self.date_navigation_dock.navNext.connect(self._on_nav_next)
        self.date_navigation_dock.viewChanged.connect(self._on_view_changed)
        self.date_navigation_dock.dayDateChanged.connect(self._on_day_date_changed)
        self.date_navigation_dock.weekFromChanged.connect(self._on_week_from_changed)

    def _on_global_filters_changed(self, fs: FilterState) -> None:
        """Apply global filter changes and optionally jump to semester start"""

        self.filter_state = fs

        self.planner.set_global_filter_state(fs)
        terms = self._compute_filtered_termine(fs)
        self.termine_dock.set_rows(terms, self.planner.state.lvas, self.planner.state.raeume)

        if fs.semester:
            start_date = self._resolve_start_date_for_semester(fs.semester)
            if start_date:
                self._apply_start_date(start_date)

    def _on_unassign_termin(self, tid: str):
        if self.planner.crud.unassign_termin(tid):
            self.refresh_everything()

    def _on_jump_to_termin(self, tid: str) -> None:
        self.planner.highlight_termine([tid])

    def _on_nav_prev(self) -> None:
        self.planner._shift_period(-1)

    def _on_nav_next(self) -> None:
        self.planner._shift_period(+1)

    def _on_view_changed(self, _view: str) -> None:
        self.planner._on_view_changed()

    def _on_day_date_changed(self, _date) -> None:
        self.planner.refresh(emit=False)

    def _on_week_from_changed(self, _date) -> None:
        self.planner.refresh(emit=False)

    def refresh_everything(self) -> None:
        self.planner.refresh(emit=True)

    def refresh_conflicts(self) -> None:
        self.conflicts_dock.initialize_detector(
            self.planner.state.lvas,
            self.planner.state.raeume,
            data_dir=self.data_dir,
        )
        self.conflicts_dock.refresh_conflicts(self.planner.state.termine)

    def refresh_docks(self) -> None:
        """Refresh dock data and option lists based on current planner state/filters"""
        lva_list = getattr(self.planner.state, "lvas", None) or []

        fach_data = self._read_json(self.data_dir / "fachrichtungen.json", {})
        fachrichtungen = fach_data.get("fachrichtungen", [])

        sem_data = self._read_json(self.data_dir / "semester.json", {})
        semester_list = [(s["id"], s["name"]) for s in sem_data.get("semester", [])]

        typ_list = [t.typ for t in getattr(self.planner.state, "termine", []) if getattr(t, "typ", None)]

        self.global_filter_dock.refresh_filter_options(
            fachrichtungen,
            semester_list,
            lva_list,
            self.planner.state.raeume,
            typ_list=typ_list,
            current=self.filter_state,
        )

        self.filter_state = FilterState(
            fachrichtung=self.global_filter_dock.fachrichtung_cb.currentData() or None,
            semester=self.global_filter_dock.semester_cb.currentData() or None,
            lva_id=self.global_filter_dock.lva_cb.currentData() or None,
            raum_id=self.global_filter_dock.room_cb.currentData() or None,
            typ=self.global_filter_dock.typ_cb.currentData() or None,
            dozent=self.global_filter_dock.dozent_cb.currentData() or None,
            geplante_semester=self.global_filter_dock.geplante_semester_cb.currentData() or None,
        )

        terms = self._compute_filtered_termine(self.filter_state)

        self.termine_dock.set_rows(terms, self.planner.state.lvas, self.planner.state.raeume)

        self.data_editor_dock.refresh_all()
        self.refresh_conflicts()

    def _compute_filtered_termine(self, fs: FilterState | None):
        """Return the filtered list of Termine for the given filter state
        """

        if fs:
            room = fs.raum_id
            q = (str(fs.lva_id).strip().lower() if fs.lva_id else "")
            typ = fs.typ
            dozent = fs.dozent
            semester_id = fs.semester
            geplante_semester = getattr(fs, "geplante_semester", None)
        else:
            filters = self.planner.current_filters()
            room = filters["raum_id"]
            q = filters["q"]
            typ = filters["typ"]
            dozent = filters["dozent"]
            semester_id = filters["semester_id"]
            geplante_semester = filters["geplante_semester"]

        terms = self.planner.state.filtered_termine(
            raum_id=room,
            q=q,
            typ=typ,
            dozent=dozent,
            semester_id=semester_id,
            geplante_semester=geplante_semester,
        )
        return terms