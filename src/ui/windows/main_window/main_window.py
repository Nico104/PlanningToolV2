from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QDialog, QMainWindow

from src.services.data_service import DataService

from src.ui.docks.termine_dock import TermineDock
from src.ui.docks.data_editor_dock import DataEditorDock
from src.ui.docks.conflicts_dock import ConflictsDock
from src.ui.docks.global_filter_dock import GlobalFilterDock
from src.core.states import FilterState
from ...utils.crud_handlers import CrudHandlers
from .layout_manager import LayoutManager
from src.ui.planner.workspace import PlannerWorkspace
from ...dialogs import SettingsDialog
from src.ui.dialogs.konflikte_dialog import KonflikteDialog
import os

class MainWindow(QMainWindow):
    def set_start_semester_and_reload(self, fachrichtung, semester):
        # Update settings.json with new start_fachrichtung and start_semester
        s = self.ds.load_settings()
        s["start_fachrichtung"] = fachrichtung
        s["start_semester"] = semester
        self.ds.save_settings(s)

        # Update window title (no semester/fachrichtung shown)
        self.setWindowTitle("Planungstool")
        self.refresh_everything()

        # After reload, jump to the semester start date from termine.json, but delay until UI is updated
        from PySide6.QtCore import QTimer
        def set_semester_start_date():
            settings = self.ds.load_settings()
            fachrichtung = settings.get("start_fachrichtung", "ETIT")
            semester = settings.get("start_semester", "SS26")
            filebase = f"{semester.lower()}_termine.json"
            path = self.data_dir / "Studiengang" / fachrichtung / filebase
            import json
            from datetime import datetime
            from src.ui.utils.datetime_utils import date_to_qdate
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                # Try to get semester start from object, else use earliest termin
                sem_obj = data.get("semester", {})
                start_str = sem_obj.get("start")
                start_date = None
                if start_str:
                    start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
                else:
                    # fallback: use earliest termin date
                    termine = data.get("termine", [])
                    dates = [datetime.strptime(t["datum"], "%Y-%m-%d").date() for t in termine if t.get("datum")]
                    if dates:
                        start_date = min(dates)
                if start_date:
                    self.global_filter_dock.view_cb.setCurrentIndex(self.global_filter_dock.view_cb.findData("week"))
                    self.global_filter_dock.week_from.setDate(date_to_qdate(self.planner._align_to_monday(start_date)))
                    self.global_filter_dock.day_date.setDate(date_to_qdate(start_date))
                    self.planner.view_cb.setCurrentIndex(self.planner.view_cb.findData("week"))
                    self.planner.week_from.setDate(date_to_qdate(self.planner._align_to_monday(start_date)))
                    self.planner.day_date.setDate(date_to_qdate(start_date))
            except Exception as e:
                print(f"Semester date switch error: {e}")
        QTimer.singleShot(0, set_semester_start_date)

    def __init__(self, data_dir: Path):
        super().__init__()
        self.ds = DataService(data_dir)
        self.setWindowTitle("Planungstool")
        self.data_dir = data_dir
        self.ds = DataService(data_dir)
        

        # self.setCentralWidget(QWidget())

        
        self._build_menus()

        self.filter_state = FilterState()

        # Dock options
        self.setDockOptions(
            QMainWindow.AllowTabbedDocks |
            QMainWindow.AllowNestedDocks |
            QMainWindow.AnimatedDocks |
            QMainWindow.GroupedDragging
        )

        # Docks
        self._setup_docks()

       
        self.crud = CrudHandlers(self)
        self.layout_mgr = LayoutManager(self)

      
        self._wire_signals()

        # initial refresh
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
        import sys, subprocess
        from PySide6.QtWidgets import QMessageBox, QPushButton
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
            QMessageBox.information(self, "Gespeichert", "Gespeichert.")
        self.refresh_everything()

    def _build_menus(self) -> None:
        mb = self.menuBar()


        #Datei Menu
        file_menu = mb.addMenu("Datei")
        self.act_refresh = QAction("Aktualisieren", self)
        self.act_refresh.triggered.connect(self.refresh_everything)
        file_menu.addAction(self.act_refresh)

        # Removed dynamic Semester/Fachrichtung menu. All data is now always shown; filtering is handled by global filters.

        #Ansicht Menu
        self.view_menu = mb.addMenu("Ansicht")
        self.layout_menu = self.view_menu.addMenu("Layout")
        self.layout_group = QActionGroup(self)
        self.layout_group.setExclusive(True)
        self.act_save_layout = QAction("Aktuelles Layout speichern…", self)
        self.act_reset_layouts = QAction("Layouts zurücksetzen", self)

        #Tools Menu
        tools_menu = mb.addMenu("Tools")
        self.act_settings = QAction("Settings…", self)
        self.act_settings.triggered.connect(self.open_settings)
        tools_menu.addAction(self.act_settings)

        # Konflikte
        self.act_konflikte = QAction("Konflikte…", self)
        self.act_konflikte.triggered.connect(self.open_konflikte_dialog)
        tools_menu.addAction(self.act_konflikte)
        
        
    def open_konflikte_dialog(self):
        conflicts_path = os.path.join("data", "konflikte.json")
        dlg = KonflikteDialog(self, conflicts_path=conflicts_path)
        dlg.conflicts_changed.connect(self.refresh_conflicts)
        dlg.exec()

    


        
    def _setup_docks(self) -> None:
        self.global_filter_dock = GlobalFilterDock(self)
        self.global_filter_dock.setObjectName("dock_global_filters")
        self.addDockWidget(Qt.TopDockWidgetArea, self.global_filter_dock)

        self.planner = PlannerWorkspace(self, self.ds, on_data_changed=self.refresh_docks, global_filter_dock=self.global_filter_dock)
        self.setCentralWidget(self.planner)
      

        self.termine_dock = TermineDock(self)
        self.termine_dock.setObjectName("dock_termine")
        self.addDockWidget(Qt.LeftDockWidgetArea, self.termine_dock)

        # Conflicts dock
        self.conflicts_dock = ConflictsDock(self)
        self.conflicts_dock.setObjectName("dock_conflicts")
        self.addDockWidget(Qt.LeftDockWidgetArea, self.conflicts_dock)
        self.tabifyDockWidget(self.termine_dock, self.conflicts_dock)

        # Data Editor dock
        self.data_editor_dock = DataEditorDock(self, ds=self.ds, data_dir=self.data_dir, on_data_changed=self.refresh_docks)
        self.data_editor_dock.setObjectName("dock_data_editor")
        self.tabifyDockWidget(self.termine_dock, self.data_editor_dock)
        self.termine_dock.raise_()

        # Könnte Probleme mit anderen Layouts machen!
 #       total_width = self.width()
 #       left = int(total_width * 0.80)
 #       right = int(total_width * 0.18) 
 #       self.resizeDocks([
 #           self.termine_dock,
 #           self.conflicts_dock
 #       ], [left, right], Qt.Horizontal)

    def _wire_signals(self) -> None:
        # Termine
        self.termine_dock.termin_double_clicked.connect(self.crud.edit_termin_by_id)
        self.termine_dock.termin_delete_clicked.connect(self.crud.del_termin_by_id)
        
        self.termine_dock.termin_unassign_requested.connect(self._on_unassign_termin)

        # Conflicts
        self.conflicts_dock.conflict_items_highlight.connect(self.planner.highlight_termine)

        # LVA dock
        # self.lva_dock.edit_clicked.connect(self.crud.edit_lva)
        # self.lva_dock.delete_clicked.connect(self.crud.del_lva)

        # Room dock
        # self.room_dock.edit_clicked.connect(self.crud.edit_room)
        # self.room_dock.delete_clicked.connect(self.crud.del_room)

        # Semester dock
        # self.sem_dock.edit_clicked.connect(self.crud.edit_semester)
        # self.sem_dock.delete_clicked.connect(self.crud.del_semester)
        # Global filters
        self.global_filter_dock.filtersChanged.connect(self._on_global_filters_changed)

        self.global_filter_dock.navPrev.connect(self._on_nav_prev)
        self.global_filter_dock.navNext.connect(self._on_nav_next)
        self.global_filter_dock.viewChanged.connect(self._on_view_changed)
        self.global_filter_dock.dayDateChanged.connect(self._on_day_date_changed)
        self.global_filter_dock.weekFromChanged.connect(self._on_week_from_changed)

    def _on_global_filters_changed(self, fs: FilterState) -> None:
        self.filter_state = fs

        self.planner.set_global_filter_state(fs)
        terms = self._compute_filtered_termine(fs)
        self.termine_dock.set_rows(terms, self.planner.state.lvas, self.planner.state.raeume)

        # Jump to semester start date if a semester is selected
        if fs.semester:
            import json
            from datetime import datetime
            from src.ui.utils.datetime_utils import date_to_qdate
            semester_path = os.path.join(os.getcwd(), "data", "semester.json")
            try:
                with open(semester_path, encoding="utf-8") as f:
                    sem_data = json.load(f)
                sem_list = sem_data.get("semester", [])
                sem_obj = next((s for s in sem_list if s["id"] == fs.semester), None)
                if sem_obj and sem_obj.get("start"):
                    start_date = datetime.strptime(sem_obj["start"], "%Y-%m-%d").date()
                    self.global_filter_dock.view_cb.setCurrentIndex(self.global_filter_dock.view_cb.findData("week"))
                    self.global_filter_dock.week_from.setDate(date_to_qdate(self.planner._align_to_monday(start_date)))
                    self.global_filter_dock.day_date.setDate(date_to_qdate(start_date))
                    self.planner.view_cb.setCurrentIndex(self.planner.view_cb.findData("week"))
                    self.planner.week_from.setDate(date_to_qdate(self.planner._align_to_monday(start_date)))
                    self.planner.day_date.setDate(date_to_qdate(start_date))
            except Exception as e:
                print(f"Semester filter jump error: {e}")

    
    def _on_unassign_termin(self, tid: str):
        if self.planner.crud.unassign_termin(tid):
            self.refresh_everything()

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
            self.planner.state.raeume
        )
        self.conflicts_dock.refresh_conflicts(self.planner.state.termine)

        
    def refresh_docks(self) -> None:
        # always use central filter_state
        terms = self._compute_filtered_termine(self.filter_state)

        # keep global filter dock in sync with available data
        lva_list = getattr(self.planner.state, "lvas", None) or []
        # Gather all fachrichtungen from fachrichtungen.json
        import os
        import json
        fachrichtungen_path = os.path.join(os.getcwd(), "data", "fachrichtungen.json")
        fachrichtungen = []
        if os.path.isfile(fachrichtungen_path):
            with open(fachrichtungen_path, encoding="utf-8") as f:
                fach_data = json.load(f)
            fachrichtungen = fach_data.get("fachrichtungen", [])

        # Gather all semesters from semester.json (id and name)
        semester_path = os.path.join(os.getcwd(), "data", "semester.json")
        semester_list = []
        if os.path.isfile(semester_path):
            import json
            with open(semester_path, encoding="utf-8") as f:
                sem_data = json.load(f)
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

        self.termine_dock.set_rows(terms, self.planner.state.lvas, self.planner.state.raeume)

        # Data editor dock refresh
        self.data_editor_dock.refresh_all()

        # Refresh conflicts (use all termine, not filtered)
        self.refresh_conflicts()

    def _compute_filtered_termine(self, fs: FilterState | None):
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

