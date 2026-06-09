from pathlib import Path
from datetime import date, datetime, timedelta
from time import monotonic
import json
import subprocess
import sys
from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QDialog, QMainWindow, QFileDialog, QMessageBox, QPushButton

from ....services.data_service import DataService
from ....services.excel_exchange_service import (
    export_project_to_excel,
    export_terms_for_teachers_to_excel,
    export_week_calendar_to_excel,
    get_lva_export_options,
    get_teacher_export_semester_options,
    import_project_from_excel,
    import_tiss_rooms_from_excel,
)
from ....services.undo_service import UndoService
from ....services.semester_tools_service import copy_semester_termine, delete_semester_termine
from ....services.free_day_import_service import append_free_day_candidates
from ....services.semester_rules import semester_from_id, semester_id_for_date
from ....services.data_folder_service import (
    data_path_for_settings,
    load_settings,
    save_settings,
    validate_or_initialize_data_dir,
)
from ....core.models import Raum

from ...docks.termine_dock import TermineDock
from ...docks.data_editor_dock import DataEditorDock
from ...docks.conflicts_dock import ConflictsDock
from ...docks.global_filter_dock import GlobalFilterDock
from ...docks.date_navigation_dock import DateNavigationDock
from ...utils.datetime_utils import date_to_qdate, qdate_to_date
from ....core.states import FilterState
from ...utils.crud_handlers import CrudHandlers
from .layout_manager import LayoutManager
from .shortcuts import install_main_window_shortcuts
from ...planner.workspace import PlannerWorkspace
from ...planner.termincard import TerminCard as PlannerTerminCard
from ...dialogs import (
    SettingsDialog,
    TeacherExportDialog,
    SemesterToolsDialog,
    FreeDayImportDialog,
    TissRoomImportPreviewDialog,
)
from ...dialogs.konflikte_dialog import KonflikteDialog
from ...dialogs.import_dialog import ImportDialog
from ...components.widgets.toast import Toast


class MainWindow(QMainWindow):
    """Main application window containing planner, docks etc...

    This class wires UI components, forwards CRUD operations, keeps filters in sync
    """

    def _apply_start_date(self, start_date) -> None:
        """Synchronize planner and navigation controls to the same start day/week"""

        day_qdate = date_to_qdate(start_date)

        self.date_navigation_dock.day_date.setDate(day_qdate)
        self.date_navigation_dock.view_cb.setCurrentIndex(
            self.date_navigation_dock.view_cb.findData("week")
        )

    @staticmethod
    def _read_json(path: Path, default):
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[4]

    def _resolve_start_date_for_semester(self, semester_id: str):
        """given a semester id, what date should the UI jump to
        """

        sem_obj = semester_from_id(semester_id)
        if sem_obj:
            return sem_obj.start

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

    def _focused_calendar_termin_id(self) -> str | None:
        ref = PlannerTerminCard._focused_card_ref
        card = ref() if ref else None
        if card is None:
            return None
        tid = getattr(card, "termin_id", None)
        return str(tid) if tid else None

    def unassign_focused_calendar_termin(self) -> None:
        if self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        tid = self._focused_calendar_termin_id()
        if tid:
            self._on_unassign_termin(tid)

    def delete_focused_calendar_termin(self) -> None:
        if self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        tid = self._focused_calendar_termin_id()
        if tid and self.crud.del_termin_by_id(tid):
            self.refresh_everything()

    def __init__(self, data_dir: Path):
        super().__init__()
        self.ds = DataService(data_dir)
        self.undo_service = UndoService()
        self.undo_service.on_history_changed(self.update_undo_redo_actions)
        self.setWindowTitle("Planungstool")
        self.data_dir = data_dir
        self._previous_year_enabled = False
        self._previous_year_return_date: date | None = None
        self._last_history_read_only_toast_at = 0.0

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
        install_main_window_shortcuts(self)

        startup_settings = self.ds.load_settings()
        self.termine_dock.set_search_enabled(bool(startup_settings.get("show_termine_search", True)))

        self.refresh_everything()
        self.update_undo_redo_actions()
        self.layout_mgr.init_default()

        self.showMaximized()
        
        # Delayed refresh to fix initial card heights after startup layout (50ms not exact time, did not work with 0)
        QTimer.singleShot(50, self._refresh_planner_only)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        #refresh card heights
        QTimer.singleShot(120, self._refresh_planner_only)

    def _refresh_planner_only(self) -> None:
        self.planner.refresh(emit=False)

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
            Toast(self, "Einstellungen gespeichert.", duration_ms=2500).show()
        self.termine_dock.set_search_enabled(bool(s.get("show_termine_search", True)))
        self.refresh_everything()

    def create_new_project(self) -> None:
        project_root = self._project_root()
        folder = QFileDialog.getExistingDirectory(
            self,
            "Neues Projekt anlegen",
            str(self.data_dir.parent if self.data_dir else project_root),
        )
        if not folder:
            return

        target_dir = Path(folder).resolve()
        try:
            if target_dir.samefile(self.data_dir):
                QMessageBox.information(self, "Neues Projekt", "Dieser Ordner ist bereits geöffnet.")
                return
        except Exception:
            pass

        try:
            has_content = target_dir.exists() and any(target_dir.iterdir())
        except Exception as exc:
            QMessageBox.warning(self, "Neues Projekt", f"Ordner konnte nicht geprüft werden: {exc}")
            return

        if has_content:
            answer = QMessageBox.question(
                self,
                "Ordner ist nicht leer",
                "Der gewählte Ordner ist nicht leer. Vorhandene Projektdateien werden verwendet, "
                "fehlende Projektdateien werden angelegt. Fortfahren?",
            )
            if answer != QMessageBox.Yes:
                return

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            created_files, invalid_files = validate_or_initialize_data_dir(target_dir)
        except Exception as exc:
            QMessageBox.warning(self, "Neues Projekt", f"Projekt konnte nicht angelegt werden: {exc}")
            return

        if invalid_files:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Projektdateien ungültig")
            msg.setText("Der gewählte Ordner enthält ungültige Projektdateien.")
            msg.setInformativeText("Die Dateien wurden nicht überschrieben. Bitte wählen Sie einen anderen Ordner.")
            msg.setDetailedText("\n".join(invalid_files))
            msg.exec()
            return

        settings_path = project_root / "src" / "settings.json"
        settings = load_settings(settings_path)
        settings["data_path"] = data_path_for_settings(project_root, target_dir)
        save_settings(settings_path, settings)

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Neues Projekt")
        if created_files:
            msg.setText("Neues Projekt wurde angelegt. Für den Wechsel muss das Programm neu gestartet werden.")
        else:
            msg.setText("Projekt wurde ausgewählt. Für den Wechsel muss das Programm neu gestartet werden.")
        msg.setInformativeText(str(target_dir))
        restart_btn = QPushButton("Neustart")
        msg.addButton(QMessageBox.Ok)
        msg.addButton(restart_btn, QMessageBox.AcceptRole)
        msg.setDefaultButton(restart_btn)
        msg.exec()
        if msg.clickedButton() == restart_btn:
            python = sys.executable
            subprocess.Popen([python] + sys.argv)
            sys.exit(0)

    def _build_menus(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("Datei")
        self.act_new_project = QAction("Neues Projekt…", self)
        self.act_new_project.triggered.connect(self.create_new_project)
        file_menu.addAction(self.act_new_project)
        file_menu.addSeparator()

        self.act_new_termin = QAction("Neuer Termin…", self)
        self.act_new_termin.triggered.connect(self.create_termin)
        file_menu.addAction(self.act_new_termin)
        file_menu.addSeparator()

        self.act_refresh = QAction("Aktualisieren", self)
        self.act_refresh.triggered.connect(self.refresh_everything)
        file_menu.addAction(self.act_refresh)

        import_export_menu = file_menu.addMenu("Import/Export")

        self.act_import = QAction("Projekt importieren…", self)
        self.act_import.triggered.connect(self.import_project)
        import_export_menu.addAction(self.act_import)

        self.act_export = QAction("Projekt exportieren…", self)
        self.act_export.triggered.connect(self.export_project)
        import_export_menu.addAction(self.act_export)

        self.act_tiss_room_import = QAction("TISS-Raumliste importieren…", self)
        self.act_tiss_room_import.triggered.connect(self.import_tiss_room_list)
        import_export_menu.addAction(self.act_tiss_room_import)

        import_export_menu.addSeparator()
        self.act_export_teachers = QAction("Export für Lehrende…", self)
        self.act_export_teachers.triggered.connect(self.export_teacher_terms)
        import_export_menu.addAction(self.act_export_teachers)

        edit_menu = mb.addMenu("Bearbeiten")
        self.act_undo = QAction("Rückgängig", self)
        self.act_undo.triggered.connect(self.perform_undo)
        self.act_redo = QAction("Wiederholen", self)
        self.act_redo.triggered.connect(self.perform_redo)
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)

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

        tools_menu.addSeparator()
        self.act_free_day_import = QAction("Freie Tage importieren…", self)
        self.act_free_day_import.triggered.connect(self.open_free_day_import)
        tools_menu.addAction(self.act_free_day_import)

        self.act_semester_tools = QAction("Semester-Werkzeuge…", self)
        self.act_semester_tools.triggered.connect(self.open_semester_tools)
        tools_menu.addAction(self.act_semester_tools)

    def create_data_editor_entity(self, entity: str) -> None:
        if entity == "termin" and self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        self.data_editor_dock.create_entity(entity)

    def create_termin(self) -> None:
        if self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        current_date = self._current_calendar_date()
        if self.crud.add_termin(
            default_qdate=date_to_qdate(current_date),
            default_semester_id=self._semester_id_for_calendar_date(current_date),
        ):
            self.refresh_everything()

    def jump_to_today(self) -> None:
        today = QDate.currentDate()
        self.date_navigation_dock.day_date.setDate(today)
        self.planner.refresh(emit=False)

    def open_konflikte_dialog(self):
        conflicts_path = str(Path(__file__).resolve().parents[3] / "konflikte.json")
        dlg = KonflikteDialog(self, conflicts_path=conflicts_path)
        dlg.conflicts_changed.connect(self.refresh_conflicts)
        dlg.exec()

    def open_semester_tools(self) -> None:
        current_date = self._current_calendar_date()
        dlg = SemesterToolsDialog(
            self,
            termine=self.ds.load_termine(),
            lvas=self.ds.load_lvas(),
            default_semester_id=self._semester_id_for_calendar_date(current_date),
        )
        if dlg.exec() != QDialog.Accepted or not dlg.result_request:
            return

        request = dlg.result_request
        try:
            termine = self.ds.load_termine()
            if request.action == "copy" and request.source and request.target:
                updated, changed_count = copy_semester_termine(
                    termine,
                    source=request.source,
                    target=request.target,
                    lva_ids=request.lva_ids,
                    date_mode=request.date_mode,
                    copy_ausfall_daten=request.copy_ausfall_daten,
                )
                message = f"{changed_count} Termine nach {request.target.name} kopiert."
            elif request.action == "clear" and request.semester:
                updated, changed_count = delete_semester_termine(termine, request.semester.id)
                message = f"{changed_count} Termine aus {request.semester.name} gelöscht."
            else:
                return

            if changed_count <= 0:
                return

            self.undo_service.record_snapshot(self.ds)
            self.ds.save_termine(updated)
            self.refresh_everything()
            Toast(self, message, duration_ms=3000).show()
        except Exception as e:
            QMessageBox.warning(self, "Semester-Werkzeuge", f"Aktion konnte nicht ausgeführt werden: {e}")

    def open_free_day_import(self) -> None:
        default_from, default_to = self._default_free_day_import_range()
        dlg = FreeDayImportDialog(
            self,
            existing_items=self.ds.load_freie_tage(),
            default_from=default_from,
            default_to=default_to,
        )
        if dlg.exec() != QDialog.Accepted or not dlg.selected_candidates:
            return

        try:
            freie_tage = self.ds.load_freie_tage()
            updated, changed_count = append_free_day_candidates(freie_tage, dlg.selected_candidates)
            if changed_count <= 0:
                Toast(self, "Keine neuen freien Tage gespeichert.", duration_ms=2500).show()
                return

            self.undo_service.record_snapshot(self.ds)
            self.ds.save_freie_tage(updated)
            self.refresh_everything()
            Toast(self, f"{changed_count} freie Tage gespeichert.", duration_ms=3000).show()
        except Exception as e:
            QMessageBox.warning(self, "Freie Tage importieren", f"Freie Tage konnten nicht gespeichert werden: {e}")

    def _default_free_day_import_range(self) -> tuple[date, date]:
        year = self._current_calendar_date().year
        return date(year, 1, 1), date(year, 12, 31)

    def _current_calendar_date(self) -> date:
        return qdate_to_date(self.date_navigation_dock.day_date.date())

    def _semester_id_for_calendar_date(self, value: date) -> str:
        return semester_id_for_date(value)

    def export_project(self) -> None:
        default_name = f"Planungsdaten_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        files = [
            "raeume.json",
            "lehrveranstaltungen.json",
            "termine.json",
            "studienrichtungen.json",
            "freie_tage.json",
        ]
        export_obj = {}
        for f in files:
            p = self.data_dir / f
            if p.exists():
                try:
                    export_obj[f] = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    export_obj[f] = p.read_text(encoding="utf-8")

        fn, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Projekt exportieren",
            str(self.data_dir / default_name),
            "Excel Files (*.xlsx);;JSON Files (*.json)",
            "Excel Files (*.xlsx)",
        )
        if not fn:
            return
        try:
            out_path = Path(fn)
            if not out_path.suffix:
                if selected_filter.startswith("JSON"):
                    out_path = out_path.with_suffix(".json")
                else:
                    out_path = out_path.with_suffix(".xlsx")
            if out_path.suffix.lower() == ".xlsx":
                export_project_to_excel(self.data_dir, out_path)
            else:
                out_path.write_text(
                    json.dumps(export_obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            Toast(self, "Projekt exportiert.", duration_ms=2500).show()
        except Exception as e:
            QMessageBox.warning(self, "Export Fehler", f"Fehler beim Export: {e}")

    def import_tiss_room_list(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(
            self,
            "TISS-Raumliste importieren",
            str(self.data_dir),
            "Excel Files (*.xlsx)",
        )
        if not fn:
            return

        try:
            normalized = import_tiss_rooms_from_excel(Path(fn))
        except Exception as e:
            QMessageBox.warning(self, "TISS-Raumliste importieren", f"Raumliste konnte nicht gelesen werden: {e}")
            return

        rooms = normalized.get("raeume.json", {}).get("raeume", [])
        dlg = TissRoomImportPreviewDialog(self, rooms)
        if dlg.exec() != QDialog.Accepted:
            return

        selected_rooms = dlg.selected_rooms
        if not selected_rooms:
            Toast(self, "Keine Räume ausgewählt.", duration_ms=2500).show()
            return

        existing_rooms = self.ds.load_raeume()
        existing_by_id = {room.id: room for room in existing_rooms}
        room_order = [room.id for room in existing_rooms]

        new_count = 0
        update_count = 0
        for item in selected_rooms:
            room = Raum(
                id=str(item.get("id", "")).strip(),
                name=str(item.get("name", "")).strip(),
                kapazitaet=int(item.get("kapazitaet", 0)),
            )
            if not room.id or not room.name:
                continue
            if room.id in existing_by_id:
                if existing_by_id[room.id] != room:
                    update_count += 1
                existing_by_id[room.id] = room
            else:
                new_count += 1
                existing_by_id[room.id] = room
                room_order.append(room.id)

        changed_count = new_count + update_count
        if changed_count <= 0:
            Toast(self, "Keine neuen oder geänderten Räume importiert.", duration_ms=2500).show()
            return

        self.undo_service.record_snapshot(self.ds)
        self.ds.save_raeume([existing_by_id[room_id] for room_id in room_order])
        Toast(
            self,
            f"{changed_count} Räume importiert ({new_count} neu, {update_count} geändert).",
            duration_ms=3000,
        ).show()
        self.refresh_everything()

    def export_teacher_terms(self) -> None:
        try:
            lva_options = get_lva_export_options(self.data_dir)
            semester_options = get_teacher_export_semester_options(self.data_dir)
        except Exception as e:
            QMessageBox.warning(self, "Export Fehler", f"LVAs konnten nicht geladen werden: {e}")
            return

        if not lva_options:
            QMessageBox.warning(self, "Keine LVAs", "Keine LVAs gefunden.")
            return

        current_date = self._current_calendar_date()
        current_semester = semester_from_id(self._semester_id_for_calendar_date(current_date))
        default_from = current_semester.start if current_semester else current_date - timedelta(days=current_date.weekday())
        default_to = current_semester.end if current_semester else default_from + timedelta(days=6)
        dlg = TeacherExportDialog(
            lva_options,
            semester_options,
            default_from=default_from,
            default_to=default_to,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        selected_lva_ids = dlg.selected_lva_ids()
        selected_teachers = dlg.selected_teachers()
        selected_semesters = dlg.selected_semester_ids()
        export_format = dlg.selected_export_format()
        date_from, date_to = dlg.selected_date_range()
        include_weekend = dlg.selected_include_weekend()
        calendar_slot_minutes = dlg.selected_calendar_slot_minutes()

        if len(selected_lva_ids) == 1:
            export_name = selected_lva_ids[0]
        elif len(selected_lva_ids) <= 3:
            export_name = "_".join(selected_lva_ids)
        else:
            export_name = f"{len(selected_lva_ids)}_LVAs"
        if selected_semesters:
            semester_part = "_".join(selected_semesters) if len(selected_semesters) <= 2 else f"{len(selected_semesters)}_Semester"
            export_name = f"{export_name}_{semester_part}"
        export_name = f"{export_name}_{date_from:%Y-%m-%d}_bis_{date_to:%Y-%m-%d}"
        safe_export_name = "".join(
            char if char.isalnum() or char in (" ", "-", "_") else "_"
            for char in export_name
        ).strip().replace(" ", "_")
        export_prefix = "Wochenkalender" if export_format == "calendar" else "Termine"
        default_name = f"{export_prefix}_{safe_export_name}_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        fn, _ = QFileDialog.getSaveFileName(
            self,
            "Export für Lehrende speichern",
            str(self.data_dir / default_name),
            "Excel Files (*.xlsx)",
        )
        if not fn:
            return
        out_path = Path(fn)
        if not out_path.suffix:
            out_path = out_path.with_suffix(".xlsx")
        if out_path.suffix.lower() != ".xlsx":
            out_path = out_path.with_suffix(".xlsx")

        try:
            if export_format == "calendar":
                export_week_calendar_to_excel(
                    self.data_dir,
                    out_path,
                    date_from,
                    date_to,
                    teacher_filter=None,
                    semester_filter=selected_semesters,
                    lva_filter=selected_lva_ids,
                    include_weekend=include_weekend,
                    slot_minutes=calendar_slot_minutes,
                )
            else:
                export_terms_for_teachers_to_excel(
                    self.data_dir,
                    out_path,
                    teacher_filter=None,
                    semester_filter=selected_semesters,
                    lva_filter=selected_lva_ids,
                    date_from=date_from,
                    date_to=date_to,
                )
            Toast(self, "Export für Lehrende erstellt.", duration_ms=2500).show()
        except Exception as e:
            QMessageBox.warning(self, "Export Fehler", f"Fehler beim Export für Lehrende: {e}")

    def _normalize_import_payload(self, data):
        normalized = {}
        known_keys = {
            "termine": "termine.json",
            "raeume": "raeume.json",
            "lehrveranstaltungen": "lehrveranstaltungen.json",
            "studienrichtungen": "studienrichtungen.json",
            "freie_tage": "freie_tage.json",
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

        return normalized

    def import_project(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Projekt importieren",
            str(self.data_dir),
            "Excel/JSON Files (*.xlsx *.json);;Excel Files (*.xlsx);;JSON Files (*.json)",
        )
        if not fn:
            return

        in_path = Path(fn)
        try:
            if in_path.suffix.lower() == ".xlsx":
                normalized = import_project_from_excel(in_path)
            else:
                with open(fn, encoding="utf-8") as f:
                    data = json.load(f)
                normalized = self._normalize_import_payload(data)
        except Exception as e:
            QMessageBox.warning(self, "Import Fehler", f"Fehler beim Lesen der Import-Datei: {e}")
            return

        if not normalized:
            QMessageBox.warning(self, "Import Fehler", "Keine importierbaren Daten gefunden.")
            return

        dlg = ImportDialog(self, self.data_dir, normalized)
        if dlg.exec() != QDialog.Accepted:
            return
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
        # QTimer.singleShot(0, self._resize_top_docks_to_content)

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
            on_data_changed=self.refresh_everything,
        )
        self.data_editor_dock.setObjectName("dock_data_editor")
        self.tabifyDockWidget(self.termine_dock, self.data_editor_dock)
        self.termine_dock.raise_()

    def _wire_signals(self) -> None:
        self.termine_dock.termin_double_clicked.connect(self._edit_termin_by_id)
        self.termine_dock.termin_delete_clicked.connect(self._delete_termin_by_id)
        self.termine_dock.termin_unassign_requested.connect(self._on_unassign_termin)
        self.termine_dock.termin_jump_requested.connect(self._on_jump_to_termin)

        self.conflicts_dock.conflict_items_highlight.connect(self.planner.highlight_termine)

        self.global_filter_dock.filtersChanged.connect(self._on_global_filters_changed)

        self.date_navigation_dock.navPrev.connect(self._on_nav_prev)
        self.date_navigation_dock.navNext.connect(self._on_nav_next)
        self.date_navigation_dock.previousYearToggled.connect(self.set_previous_year_enabled)

    # def _resize_top_docks_to_content(self) -> None:
    #     filter_width = self.global_filter_dock.widget().sizeHint().width() + 8
    #     navigation_width = self.date_navigation_dock.widget().sizeHint().width() + 10
    #     self.resizeDocks(
    #         [self.global_filter_dock, self.date_navigation_dock],
    #         [max(filter_width, self.width() - navigation_width), navigation_width],
    #         Qt.Horizontal,
    #     )

    def _on_global_filters_changed(self, fs: FilterState) -> None:
        """Apply global filter changes and optionally jump to semester start"""

        self.filter_state = fs

        self.planner.set_global_filter_state(fs)
        terms = self._compute_filtered_termine(fs)
        self.termine_dock.set_rows(terms, self.planner.state.lvas, self.planner.state.raeume)

        if fs.semester:
            start_date = self._resolve_start_date_for_semester(fs.semester)
            if start_date:
                if self._previous_year_enabled:
                    start_date = self._previous_year_date_for(start_date)
                self._apply_start_date(start_date)

    def _on_unassign_termin(self, tid: str):
        if self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        if self.planner.crud.unassign_termin(tid):
            self.refresh_everything()

    def _edit_termin_by_id(self, tid: str) -> None:
        if self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        if self.crud.edit_termin_by_id(tid):
            self.refresh_everything()

    def _delete_termin_by_id(self, tid: str) -> None:
        if self._previous_year_enabled:
            self._show_history_read_only_toast()
            return
        if self.crud.del_termin_by_id(tid):
            self.refresh_everything()

    def _show_history_read_only_toast(self) -> None:
        now = monotonic()
        if now - self._last_history_read_only_toast_at < 1.2:
            return
        self._last_history_read_only_toast_at = now
        Toast(
            self,
            "Historie-Modus ist schreibgeschützt. Zum Bearbeiten Vorjahr ausschalten.",
            duration_ms=2500,
            kind="warning",
        ).show()

    def _on_jump_to_termin(self, tid: str) -> None:
        self.planner.highlight_termine([tid])

    def _on_nav_prev(self) -> None:
        self.planner._shift_period(-1)

    def _on_nav_next(self) -> None:
        self.planner._shift_period(+1)

    def previous_year_shortcut_mode(self) -> str:
        mode = str(self.ds.load_settings().get("previous_year_shortcut_mode", "hold")).strip().lower()
        return mode if mode in {"hold", "toggle"} else "hold"

    def toggle_previous_year(self) -> None:
        self.set_previous_year_enabled(not self._previous_year_enabled)

    def set_previous_year_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._previous_year_enabled:
            self._sync_previous_year_button()
            return

        current_date = self._current_calendar_date()
        self._previous_year_enabled = enabled
        self.planner.set_previous_year_enabled(enabled, refresh=False)
        self._apply_previous_year_read_only()
        if enabled:
            self._previous_year_return_date = current_date
            target_date = self._previous_year_date_for(current_date)
        else:
            target_date = self._previous_year_return_date or self._shift_year(current_date, 1)
            self._previous_year_return_date = None
        self.date_navigation_dock.day_date.setDate(date_to_qdate(target_date))
        self._sync_previous_year_button()
        self.planner.refresh(emit=False)

    def _apply_previous_year_read_only(self) -> None:
        read_only = bool(self._previous_year_enabled)
        self.act_new_termin.setEnabled(not read_only)
        if hasattr(self.termine_dock, "set_read_only"):
            self.termine_dock.set_read_only(read_only)
        if hasattr(self.data_editor_dock, "set_termine_read_only"):
            self.data_editor_dock.set_termine_read_only(read_only)

    def _previous_year_date_for(self, value: date) -> date:
        view = str(self.date_navigation_dock.view_cb.currentData())
        if view == "week":
            iso_year, iso_week, iso_weekday = value.isocalendar()
            target_year = iso_year - 1
            target_week = min(iso_week, self._weeks_in_iso_year(target_year))
            return self._iso_week_start(target_year, target_week) + timedelta(days=iso_weekday - 1)
        return self._shift_year(value, -1)

    @staticmethod
    def _weeks_in_iso_year(year: int) -> int:
        return date(year, 12, 28).isocalendar().week

    @staticmethod
    def _iso_week_start(year: int, week: int) -> date:
        jan4 = date(year, 1, 4)
        first_monday = jan4 - timedelta(days=jan4.weekday())
        return first_monday + timedelta(days=(week - 1) * 7)

    @staticmethod
    def _shift_year(value: date, years: int) -> date:
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            return value.replace(year=value.year + years, day=28)

    def _sync_previous_year_button(self) -> None:
        btn = self.date_navigation_dock.previous_year_btn
        btn.blockSignals(True)
        try:
            btn.setChecked(self._previous_year_enabled)
        finally:
            btn.blockSignals(False)
        btn.setToolTip(
            "Vorjahr ausblenden (Strg+Alt+V)"
            if self._previous_year_enabled
            else "Vorjahr anzeigen (Strg+Alt+V). Modus in den Einstellungen: gedrückt halten oder umschalten."
        )

    def refresh_everything(self) -> None:
        # self.planner.refresh(emit=True) einen callback mehr
        self.planner.refresh(emit=False)
        self.refresh_docks()

    def update_undo_redo_actions(self) -> None:
        self.act_undo.setEnabled(self.undo_service.can_undo())
        self.act_redo.setEnabled(self.undo_service.can_redo())

    def perform_undo(self) -> None:
        snapshot = self.undo_service.undo(self.ds)
        if snapshot is None:
            return
        self.undo_service.restore(self.ds, snapshot)
        self.refresh_everything()
        self.update_undo_redo_actions()
        Toast(self, "Rückgängig ausgeführt.", duration_ms=2500).show()

    def perform_redo(self) -> None:
        snapshot = self.undo_service.redo(self.ds)
        if snapshot is None:
            return
        self.undo_service.restore(self.ds, snapshot)
        self.refresh_everything()
        self.update_undo_redo_actions()
        Toast(self, "Wiederholen ausgeführt.", duration_ms=2500).show()

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

        studienrichtungen = self.ds.load_studienrichtungen()

        typ_list = [t.typ for t in getattr(self.planner.state, "termine", []) if getattr(t, "typ", None)]

        self.global_filter_dock.refresh_filter_options(
            studienrichtungen,
            [],
            lva_list,
            self.planner.state.raeume,
            studiensemester_list=self.ds.load_studiensemester(),
            typ_list=typ_list,
            current=self.filter_state,
        )

        self.filter_state = FilterState(
            studienrichtung=self.global_filter_dock.studienrichtung_cb.currentData() or None,
            semester=self.global_filter_dock.semester_selector.current_semester_id(),
            lva_id=self.global_filter_dock.lva_cb.currentData() or None,
            raum_id=self.global_filter_dock.room_cb.currentData() or None,
            typ=self.global_filter_dock.typ_cb.currentData() or None,
            dozent=self.global_filter_dock.dozent_cb.currentData() or None,
            studiensemester=self.global_filter_dock.studiensemester_cb.currentData() or None,
            zu_besprechen=bool(self.global_filter_dock.zu_besprechen_cb.isChecked()),
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
            lva_id = fs.lva_id
            typ = fs.typ
            dozent = fs.dozent
            studienrichtung = fs.studienrichtung
            semester_id = fs.semester
            studiensemester = getattr(fs, "studiensemester", None)
            zu_besprechen = bool(getattr(fs, "zu_besprechen", False))
        else:
            filters = self.planner.current_filters()
            room = filters["raum_id"]
            lva_id = filters["lva_id"]
            typ = filters["typ"]
            dozent = filters["dozent"]
            studienrichtung = filters["studienrichtung"]
            semester_id = filters["semester_id"]
            studiensemester = filters["studiensemester"]
            zu_besprechen = bool(filters.get("zu_besprechen", False))

        terms = self.planner.state.filtered_termine(
            raum_id=room,
            lva_id=lva_id,
            typ=typ,
            dozent=dozent,
            studienrichtung=studienrichtung,
            semester_id=semester_id,
            studiensemester=studiensemester,
            zu_besprechen=zu_besprechen,
        )
        return terms
