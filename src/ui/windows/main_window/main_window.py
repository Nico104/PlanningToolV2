from pathlib import Path
from datetime import date, datetime, timedelta
from time import monotonic
import csv
import json
import os
import re
import subprocess
import sys
from typing import Any
from PySide6.QtCore import Qt, QTimer, QDate, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ....services.data_service import DataService
from ....services.excel_exchange_service import (
    export_project_file_to_csv,
    export_project_to_excel,
    export_terms_for_teachers_to_excel,
    export_week_calendar_to_excel,
    get_lva_export_options,
    get_teacher_export_semester_options,
    import_lvas_from_excel,
    import_project_from_excel,
    import_project_file_from_csv,
    import_tiss_rooms_from_excel,
)
from ....services.default_catalog_service import DEFAULT_CATALOG_LABEL, load_default_catalog_payload
from ....services.import_merge_service import normalize_import_payload, payload_has_changes
from ....services.undo_service import UndoService
from ....services.semester_tools_service import copy_semester_termine, delete_semester_termine
from ....services.free_day_import_service import append_free_day_candidates
from ....services.semester_rules import (
    semester_for_kind_year,
    semester_from_id,
    semester_id_for_date,
)
from ....services.data_folder_service import (
    data_path_for_settings,
    load_settings,
    save_settings,
)
from ...docks.termine_dock import TermineDock
from ...docks.data_editor_dock import DataEditorDock
from ...docks.conflicts_dock import ConflictsDock
from ...docks.global_filter_dock import GlobalFilterDock
from ...docks.date_navigation_dock import DateNavigationDock
from ...utils.datetime_utils import date_to_qdate, qdate_to_date
from ...utils.project_folder_flow import prepare_project_folder, project_part_labels
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
    CatalogImportDialog,
    ProjectExportDialog,
    ExportFileOption,
)
from ...dialogs.import_dialog import ImportDialog
from ...components.widgets.toast import Toast
from ...components.widgets.action_dialog import ActionDialog, DialogAction


def restart_application() -> None:
    env = os.environ.copy()
    args = [sys.executable]
    if getattr(sys, "frozen", False):
        args.extend(sys.argv[1:])
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        env.pop("QT_PLUGIN_PATH", None)
        env.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
    else:
        args.extend(sys.argv)

    subprocess.Popen(
        args,
        cwd=str(
            Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
        ),
        env=env,
    )
    sys.exit(0)


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

    def _calendar_start_date_for_semester_filter(self, start_date: date) -> date:
        if start_date.weekday() >= 5:
            return start_date + timedelta(days=7 - start_date.weekday())
        return start_date

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
        """given a semester id, what date should the UI jump to"""

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
        self.termine_dock.set_search_enabled(
            bool(startup_settings.get("show_termine_search", True))
        )

        self.refresh_everything()
        self.update_undo_redo_actions()
        self.layout_mgr.init_default()

        self.showMaximized()

        # Delayed refresh to fix initial card heights after startup layout (50ms not exact time, did not work with 0)
        QTimer.singleShot(50, self._refresh_planner_only)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "global_filter_dock") and hasattr(self, "date_navigation_dock"):
            QTimer.singleShot(0, self._update_top_dock_layout)
        QTimer.singleShot(120, self._refresh_planner_only)

    def _refresh_planner_only(self) -> None:
        self.planner.refresh(emit=False)

    def open_settings(self, initial_tab: str = "general") -> None:
        cur = self.ds.load_settings()
        old_data_path = cur.get("data_path", "")
        old_theme = str(cur.get("theme", "light")).strip().lower()
        dlg = SettingsDialog(self, cur, initial_tab=initial_tab)
        if dlg.exec() != QDialog.Accepted or not dlg.result_settings:
            return

        s = cur
        s.update(dlg.result_settings)
        data_path_text = str(s.get("data_path", "")).strip()
        if data_path_text:
            data_path = Path(data_path_text).expanduser()
            if not data_path.is_absolute():
                QMessageBox.warning(
                    self, "Einstellungen", "Der Datenpfad muss ein absoluter Pfad sein."
                )
                return
            s["data_path"] = data_path_for_settings(data_path)
        else:
            s["data_path"] = ""
        self.ds.save_settings(s)

        new_data_path = s.get("data_path", "")
        new_theme = str(s.get("theme", "light")).strip().lower()
        if new_data_path != old_data_path or new_theme != old_theme:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Gespeichert")
            msg.setText("Gespeichert. Für diese Änderung muss das Programm neu gestartet werden.")
            restart_btn = QPushButton("Neustart")
            ok_btn = msg.addButton(QMessageBox.Ok)
            msg.addButton(restart_btn, QMessageBox.AcceptRole)
            msg.setDefaultButton(ok_btn)
            msg.exec()
            if msg.clickedButton() == restart_btn:
                restart_application()
        else:
            Toast(self, "Einstellungen gespeichert.", duration_ms=2500).show()
        self.termine_dock.set_search_enabled(bool(s.get("show_termine_search", True)))
        self.refresh_everything()
        self.refresh_conflicts()

    def _activate_project_folder(
        self,
        target_dir: Path,
        *,
        title: str,
        require_existing_project: bool = False,
        creating_new: bool = False,
    ) -> None:
        try:
            if target_dir.samefile(self.data_dir):
                QMessageBox.information(self, title, "Dieser Ordner ist bereits geöffnet.")
                return
        except Exception:
            pass

        created_files = prepare_project_folder(
            self,
            target_dir,
            title=title,
            require_existing_project=require_existing_project,
            creating_new=creating_new,
        )
        if created_files is None:
            return

        standard_data_imported = False
        if creating_new:
            standard_data_imported = self._offer_default_catalog_for_new_project(target_dir)

        settings = load_settings()
        settings["data_path"] = data_path_for_settings(target_dir)
        save_settings(settings)

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(title)
        if creating_new:
            msg.setText("Das neue Projekt ist vorbereitet.")
            info_text = (
                "Nach dem Neustart öffnet die App direkt diesen Projektordner:\n" f"{target_dir}"
            )
            if standard_data_imported:
                info_text += "\n\nAusgewählte Standarddaten wurden importiert."
            if created_files:
                info_text += "\n\nVorbereitete Bereiche:\n- " + "\n- ".join(
                    project_part_labels(created_files)
                )
        else:
            msg.setText("Der Projektordner wurde gespeichert.")
            info_text = (
                "Nach dem Neustart öffnet die App direkt diesen Projektordner:\n" f"{target_dir}"
            )
            if created_files:
                info_text += "\n\nErgänzte Bereiche:\n- " + "\n- ".join(
                    project_part_labels(created_files)
                )
        msg.setInformativeText(info_text)
        restart_btn = QPushButton("Neustart")
        msg.addButton(QMessageBox.Ok)
        msg.addButton(restart_btn, QMessageBox.AcceptRole)
        msg.setDefaultButton(restart_btn)
        msg.exec()
        if msg.clickedButton() == restart_btn:
            restart_application()

    def _offer_default_catalog_for_new_project(self, target_dir: Path) -> bool:
        dlg = ActionDialog(
            self,
            title="Standarddaten importieren",
            subtitle=(
                f"{DEFAULT_CATALOG_LABEL}. Die Daten enthalten Räume und LVAs für den "
                "Elektrotechnik-Bachelor-Katalog und können für das neue Projekt vorausgewählt werden."
            ),
            section_title="Standarddaten für das neue Projekt",
            actions=[
                DialogAction(
                    "select",
                    "Auswählen",
                    "Räume und LVAs in einer Vorschau auswählen. Räume können dort nach Gebäude gefiltert werden.",
                ),
                DialogAction(
                    "all",
                    "Alle Standarddaten importieren",
                    "Alle Räume und LVAs aus den Standarddaten direkt in das neue Projekt übernehmen.",
                ),
                DialogAction(
                    "skip",
                    "Ohne Standarddaten fortfahren",
                    "Das Projekt bleibt leer und Stammdaten können später importiert oder manuell angelegt werden.",
                ),
            ],
        )
        if dlg.exec() != QDialog.Accepted or dlg.result_key not in {"select", "all"}:
            return False

        try:
            normalized = load_default_catalog_payload()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Standarddaten importieren",
                f"Standarddaten konnten nicht gelesen werden: {e}",
            )
            return False

        if dlg.result_key == "all":
            return self._run_import_payload(
                normalized,
                success_text="Alle Standarddaten in neues Projekt importiert.",
                auto_import_new=True,
                data_dir=target_dir,
                refresh_after=False,
            )

        return self._select_catalog_import(
            normalized,
            title="Standarddaten importieren",
            subtitle=(
                f"{DEFAULT_CATALOG_LABEL}. Enthält Standardwerte für Räume und LVAs des "
                "Elektrotechnik-Bachelor-Katalogs. Importieren Sie Räume und LVAs getrennt; "
                "schließen Sie den Dialog, wenn Sie fertig sind."
            ),
            success_text="Standarddaten in neues Projekt importiert.",
            data_dir=target_dir,
            refresh_after=False,
        )

    def open_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Projekt öffnen",
            str(self.data_dir.parent if self.data_dir else self._project_root()),
        )
        if not folder:
            return

        self._activate_project_folder(
            Path(folder).resolve(),
            title="Projekt öffnen",
            require_existing_project=True,
        )

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
        self._activate_project_folder(
            target_dir,
            title="Neues Projekt",
            creating_new=True,
        )

    def _build_menus(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("Datei")
        self.act_new_project = QAction("Neues Projekt…", self)
        self.act_new_project.triggered.connect(self.create_new_project)
        file_menu.addAction(self.act_new_project)
        self.act_open_project = QAction("Projekt öffnen…", self)
        self.act_open_project.triggered.connect(self.open_project)
        file_menu.addAction(self.act_open_project)
        file_menu.addSeparator()

        self.act_new_termin = QAction("Neuer Termin…", self)
        self.act_new_termin.triggered.connect(self.create_termin)
        file_menu.addAction(self.act_new_termin)
        file_menu.addSeparator()

        self.act_refresh = QAction("Aktualisieren", self)
        self.act_refresh.triggered.connect(self.refresh_everything)
        file_menu.addAction(self.act_refresh)

        import_menu = file_menu.addMenu("Importieren")

        self.act_import = QAction("Importieren…", self)
        self.act_import.triggered.connect(self.import_data)
        import_menu.addAction(self.act_import)

        self.act_default_catalog_import = QAction("Standarddaten importieren…", self)
        self.act_default_catalog_import.triggered.connect(self.import_default_catalog)
        import_menu.addAction(self.act_default_catalog_import)

        export_menu = file_menu.addMenu("Exportieren")

        self.act_export = QAction("Daten exportieren…", self)
        self.act_export.triggered.connect(self.export_project)
        export_menu.addAction(self.act_export)

        self.act_export_teachers = QAction("Export für Lehrende…", self)
        self.act_export_teachers.triggered.connect(self.export_teacher_terms)
        export_menu.addAction(self.act_export_teachers)

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

        tools_menu = mb.addMenu("Werkzeuge")
        self.act_settings = QAction("Einstellungen…", self)
        self.act_settings.triggered.connect(lambda *_: self.open_settings())
        tools_menu.addAction(self.act_settings)

        self.act_konflikte = QAction("Konflikt-Einstellungen…", self)
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
        self.open_settings(initial_tab="conflicts")

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
                result = copy_semester_termine(
                    termine,
                    source=request.source,
                    target=request.target,
                    lva_ids=request.lva_ids,
                    date_mode=request.date_mode,
                    copy_ausfall_daten=request.copy_ausfall_daten,
                    freie_tage=self.ds.load_freie_tage(),
                    auto_cancel_target_free_days=request.auto_cancel_target_free_days,
                )
                updated = result.termine
                changed_count = result.created_count
                message = f"{changed_count} Termine nach {request.target.name} kopiert."
                if result.target_free_day_occurrences:
                    message += (
                        f" {result.target_free_day_occurrences} Vorkommen lagen auf freien Tagen."
                    )
                    if result.auto_cancelled_occurrences:
                        message += (
                            f" {result.auto_cancelled_occurrences} davon wurden als Ausfall markiert."
                        )
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
            QMessageBox.warning(
                self, "Semester-Werkzeuge", f"Aktion konnte nicht ausgeführt werden: {e}"
            )

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
            QMessageBox.warning(
                self, "Freie Tage importieren", f"Freie Tage konnten nicht gespeichert werden: {e}"
            )

    def _default_free_day_import_range(self) -> tuple[date, date]:
        year = self._current_calendar_date().year
        return date(year, 1, 1), date(year, 12, 31)

    def _current_calendar_date(self) -> date:
        return qdate_to_date(self.date_navigation_dock.day_date.date())

    def _semester_id_for_calendar_date(self, value: date) -> str:
        return semester_id_for_date(value)

    def _default_teacher_export_range(self, current_date: date) -> tuple[date, date]:
        if current_date.month >= 10:
            winter_year = current_date.year
        elif current_date.month <= 2:
            winter_year = current_date.year - 1
        else:
            winter_year = current_date.year - 1

        winter = semester_for_kind_year("WS", winter_year)
        summer = semester_for_kind_year("SS", winter_year + 1)
        return winter.start, summer.end

    def _show_export_finished_dialog(self, path: Path, text: str, details: str = "") -> None:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Export erstellt")
        msg.setText(text)
        if details:
            msg.setInformativeText(details)
        open_file_btn = QPushButton("Datei öffnen")
        open_folder_btn = QPushButton("Ordner öffnen")
        msg.addButton("Schließen", QMessageBox.RejectRole)
        msg.addButton(open_file_btn, QMessageBox.AcceptRole)
        msg.addButton(open_folder_btn, QMessageBox.ActionRole)
        msg.setDefaultButton(open_file_btn)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == open_file_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        elif clicked == open_folder_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    @staticmethod
    def _import_result_rows(
        counts_by_file: dict[str, dict[str, int]],
    ) -> tuple[dict[str, int], list[tuple[str, dict[str, int]]]]:
        labels = {
            "raeume.json": "Räume",
            "lehrveranstaltungen.json": "LVAs",
            "termine.json": "Termine",
            "studienrichtungen.json": "Studienrichtungen",
            "freie_tage.json": "Freie Zeiträume",
        }
        totals = {"new": 0, "changed": 0, "ignored": 0, "identical": 0, "skipped": 0}
        rows = []
        for file_name, counts in counts_by_file.items():
            row_counts = {
                "new": int(counts.get("new", 0)),
                "changed": int(counts.get("changed", 0)),
                "identical": int(counts.get("identical", 0)),
                "ignored": int(counts.get("ignored", 0)),
                "skipped": int(counts.get("skipped", 0)),
            }
            for key, value in row_counts.items():
                totals[key] += value
            if any(row_counts.values()):
                rows.append((labels.get(file_name, file_name), row_counts))
        return totals, rows

    def _import_result_summary(self, counts_by_file: dict[str, dict[str, int]]) -> tuple[str, str]:
        totals, rows = self._import_result_rows(counts_by_file)
        headline = f"{totals['new']} neu · {totals['changed']} geändert"
        if totals["ignored"]:
            headline += f" · {totals['ignored']} ignoriert"
        if totals["skipped"]:
            headline += f" · {totals['skipped']} übersprungen"
        if totals["identical"]:
            headline += f" · {totals['identical']} vorhanden"
        details = "\n".join(
            f"{label}: {counts['new']} neu, {counts['changed']} geändert, "
            f"{counts['identical']} vorhanden, {counts['ignored']} ignoriert, {counts['skipped']} übersprungen"
            for label, counts in rows
        )
        return headline, details

    def _show_import_finished_dialog(
        self, success_text: str, counts_by_file: dict[str, dict[str, int]]
    ) -> None:
        totals, rows = self._import_result_rows(counts_by_file)

        dlg = QDialog(self)
        dlg.setObjectName("AppDialog")
        dlg.setWindowTitle("Import abgeschlossen")
        dlg.setMinimumWidth(560)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QLabel("Import abgeschlossen")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        subtitle = QLabel(success_text)
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        summary = QFrame(dlg)
        summary.setObjectName("DialogSection")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setHorizontalSpacing(20)
        summary_layout.setVerticalSpacing(8)

        headers = ["Datenbereich", "Neu", "Geändert", "Vorhanden", "Ignoriert", "Übersprungen"]
        for column, text in enumerate(headers):
            label = QLabel(text)
            label.setObjectName("SettingsFieldLabel")
            if column > 0:
                label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            summary_layout.addWidget(label, 0, column)

        for row_index, (label_text, counts) in enumerate(rows, start=1):
            label = QLabel(label_text)
            label.setObjectName("SettingsHelp")
            summary_layout.addWidget(label, row_index, 0)
            for column, key in enumerate(
                ("new", "changed", "identical", "ignored", "skipped"), start=1
            ):
                value_label = QLabel(str(counts[key]))
                value_label.setObjectName("SettingsHelp")
                value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                summary_layout.addWidget(value_label, row_index, column)

        total_row = len(rows) + 1
        total_label = QLabel("Gesamt")
        total_label.setObjectName("SettingsFieldLabel")
        summary_layout.addWidget(total_label, total_row, 0)
        for column, key in enumerate(
            ("new", "changed", "identical", "ignored", "skipped"), start=1
        ):
            value_label = QLabel(str(totals[key]))
            value_label.setObjectName("SettingsFieldLabel")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            summary_layout.addWidget(value_label, total_row, column)

        root.addWidget(summary)

        if totals["skipped"]:
            warning = QLabel(
                "Übersprungene Einträge wurden nicht importiert, weil sie ungültig waren oder auf fehlende Stammdaten verwiesen."
            )
            warning.setObjectName("DialogSubtitle")
            warning.setWordWrap(True)
            root.addWidget(warning)

        buttons = QHBoxLayout()
        buttons.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(dlg.accept)
        buttons.addWidget(ok_btn)
        root.addLayout(buttons)

        dlg.exec()

    def export_project(self) -> None:
        options = self._project_export_file_options()
        dlg = ProjectExportDialog(self, options)
        if dlg.exec() != QDialog.Accepted:
            return

        selected_files = dlg.selected_files()
        if not selected_files:
            QMessageBox.warning(self, "Export Fehler", "Es wurde kein Datenbereich ausgewählt.")
            return

        export_format = dlg.selected_format()
        export_obj = self._read_project_export_payload(selected_files)
        if not export_obj:
            QMessageBox.warning(self, "Export Fehler", "Keine exportierbaren Daten gefunden.")
            return

        single_file_name = selected_files[0] if len(selected_files) == 1 else ""
        suffix = {"json": ".json", "xlsx": ".xlsx", "csv": ".csv"}.get(export_format, ".json")
        if single_file_name and export_format == "json":
            default_name = single_file_name
        elif single_file_name:
            default_name = Path(single_file_name).with_suffix(suffix).name
        else:
            default_name = f"Planungsdaten_{datetime.now().strftime('%Y-%m-%d')}{suffix}"

        fn, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Daten exportieren",
            str(self.data_dir / default_name),
            self._export_file_dialog_filter(export_format),
        )
        if not fn:
            return
        try:
            out_path = Path(fn)
            if not out_path.suffix:
                out_path = out_path.with_suffix(suffix)

            if export_format == "xlsx":
                export_project_to_excel(self.data_dir, out_path, selected_files)
            elif export_format == "csv":
                if not single_file_name:
                    QMessageBox.warning(
                        self,
                        "Export Fehler",
                        "CSV kann nur für eine einzelne Datei exportiert werden.",
                    )
                    return
                export_project_file_to_csv(self.data_dir, single_file_name, out_path)
            else:
                payload = export_obj[single_file_name] if single_file_name else export_obj
                out_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            summary = self._project_export_summary(export_obj)
            self._show_export_finished_dialog(
                out_path,
                "Daten exportiert.",
                summary,
            )
        except Exception as e:
            QMessageBox.warning(self, "Export Fehler", f"Fehler beim Export: {e}")

    @staticmethod
    def _export_file_dialog_filter(export_format: str) -> str:
        if export_format == "xlsx":
            return "Excel Files (*.xlsx)"
        if export_format == "csv":
            return "CSV Files (*.csv)"
        return "JSON Files (*.json)"

    def _read_project_export_payload(self, files: list[str]) -> dict[str, Any]:
        export_obj: dict[str, Any] = {}
        for f in files:
            p = self.data_dir / f
            if p.exists():
                try:
                    export_obj[f] = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    export_obj[f] = p.read_text(encoding="utf-8")
        return export_obj

    @staticmethod
    def _project_export_file_options() -> list[ExportFileOption]:
        return [
            ExportFileOption("termine.json", "Termine", "Geplante und ungeplante Termine."),
            ExportFileOption("raeume.json", "Räume", "Raumstammdaten."),
            ExportFileOption(
                "lehrveranstaltungen.json",
                "Lehrveranstaltungen",
                "LVA-Stammdaten inklusive Vortragende und Studiensemester.",
            ),
            ExportFileOption(
                "studienrichtungen.json",
                "Studienrichtungen",
                "Studienrichtungen/Stammdaten für Filter und Zuordnung.",
            ),
            ExportFileOption(
                "freie_tage.json",
                "Freie Tage",
                "Feiertage und vorlesungsfreie Zeiträume.",
            ),
        ]

    def _project_export_summary(self, export_obj: dict) -> str:
        labels = [
            ("raeume.json", "raeume", "Räume"),
            ("lehrveranstaltungen.json", "lehrveranstaltungen", "LVAs"),
            ("termine.json", "termine", "Termine"),
            ("studienrichtungen.json", "studienrichtungen", "Studienrichtungen"),
            ("freie_tage.json", "freie_tage", "freie Zeiträume"),
        ]
        parts = []
        for file_name, list_key, label in labels:
            content = export_obj.get(file_name)
            if not isinstance(content, dict):
                continue
            items = content.get(list_key, [])
            if isinstance(items, list):
                parts.append(f"{len(items)} {label}")
        return " · ".join(parts)

    @staticmethod
    def _import_payload_count(normalized: dict) -> int:
        total = 0
        for content in (normalized or {}).values():
            if isinstance(content, dict):
                for value in content.values():
                    if isinstance(value, list):
                        total += len(value)
        return total

    @staticmethod
    def _csv_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _csv_int(value: Any) -> int:
        try:
            return int(float(str(value or "").strip()))
        except Exception:
            return 0

    @staticmethod
    def _csv_semester_ids(value: Any) -> list[str]:
        text = str(value or "").strip()
        if not text:
            return []
        ids: list[str] = []
        for part in (item.strip() for item in re.split(r"[;,/]", text)):
            if not part:
                continue
            if part.casefold() in {
                "ohne semesterempfehlung",
                "ohne empfehlung",
                "none",
                "null",
                "-",
            }:
                continue
            semester_id = f"sem{part}" if part.isdigit() else part
            if semester_id not in ids:
                ids.append(semester_id)
        return ids

    @staticmethod
    def _normalize_csv_header(value: Any) -> str:
        text = str(value or "").strip().casefold()
        for src, repl in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
            text = text.replace(src, repl)
        return re.sub(r"[^a-z0-9]+", "", text)

    @classmethod
    def _csv_value(cls, row: dict[str, Any], *names: str) -> str:
        normalized = {cls._normalize_csv_header(key): value for key, value in row.items()}
        for name in names:
            value = normalized.get(cls._normalize_csv_header(name))
            if value is not None:
                return cls._csv_text(value)
        return ""

    @classmethod
    def _import_rooms_from_csv(cls, path: Path) -> dict:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rooms = []
        seen = set()
        for row in rows:
            room_id = cls._csv_value(
                row, "id", "raumnummer", "raumnr", "raumcode", "code", "nummer"
            )
            name = cls._csv_value(row, "name", "raum", "raumname", "bezeichnung", "raumbezeichnung")
            capacity_text = cls._csv_value(
                row, "kapazitaet", "kapazität", "plaetze", "plätze", "capacity"
            )
            if not room_id or not name or not capacity_text or room_id in seen:
                continue
            seen.add(room_id)
            entry = {
                "id": room_id,
                "name": name,
                "kapazitaet": cls._csv_int(capacity_text),
            }
            building = cls._csv_value(
                row, "gebaeude", "gebäude", "gebaeudekuerzel", "gebäudekürzel", "building"
            )
            address = cls._csv_value(row, "adresse", "anschrift", "address")
            if building:
                entry["gebaeude"] = building
                entry["__catalog_gebaeude"] = building
            if address:
                entry["__catalog_adresse"] = address
            rooms.append(entry)
        return {"raeume.json": {"raeume": rooms}} if rooms else {}

    @classmethod
    def _import_lvas_from_csv(cls, path: Path) -> dict:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        lvas = []
        seen = set()
        for row in rows:
            lva_id = cls._csv_value(row, "id", "lva", "lva nr", "lva-nr", "lva nummer", "nummer")
            name = cls._csv_value(row, "name", "lehrveranstaltung", "titel", "bezeichnung")
            if not lva_id or not name or lva_id in seen:
                continue
            seen.add(lva_id)
            teacher_name = cls._csv_value(
                row, "vortragende_name", "vortragender", "vortragende", "lehrperson", "dozent"
            )
            teacher_email = cls._csv_value(row, "vortragende_email", "email", "e-mail", "mail")
            teacher_email = teacher_email.split(";", 1)[0].strip()
            lvas.append(
                {
                    "id": lva_id,
                    "name": name,
                    "vortragende": {
                        "name": teacher_name,
                        "email": teacher_email,
                    },
                    "studiensemester": cls._csv_semester_ids(
                        cls._csv_value(row, "studiensemester", "semester")
                    ),
                    "studienrichtung": cls._csv_value(row, "studienrichtung", "studiengang")
                    or "ETIT",
                    "ects": cls._csv_value(row, "ects", "credit", "credits"),
                }
            )
        return {"lehrveranstaltungen.json": {"lehrveranstaltungen": lvas}} if lvas else {}

    def _show_import_intro(self) -> bool:
        info = QMessageBox(self)
        info.setIcon(QMessageBox.Information)
        info.setWindowTitle("Daten importieren")
        info.setText("Einzelne Listen oder ein vollständiges Projekt importieren.")
        info.setInformativeText(
            "Die App kann zwei Arten von Dateien importieren:\n\n"
            "1. Dateien aus dieser App\n"
            "- Ganzes Projekt: JSON oder Excel\n"
            "- Einzelner Projektbereich: JSON, Excel oder CSV\n"
            "  Beispiele: freie Tage, Räume, LVAs, Termine oder Studienrichtungen.\n"
            "  Praktisch z.B., um freie Tage zu exportieren, in Excel zu ergänzen und wieder zu importieren.\n"
            "  Diese Dateien passen automatisch, wenn sie über Exportieren erstellt wurden.\n\n"
            "2. Externe Tabellen\n"
            "- Raumliste als Excel oder CSV: benötigt Raumnummer, Raumname und Kapazität. Gebäude ist optional.\n"
            "- LVA-Liste als Excel oder CSV: benötigt LVA-Nr. und Bezeichnung. Optional sind Vortragende, "
            "E-Mail, ECTS, Studiensemester und Studienrichtung.\n"
            "  Die App erkennt gängige Spaltennamen. Wenn Pflichtspalten fehlen oder nicht erkannt werden, "
            "wird nichts importiert.\n\n"
            "Nach dem Auswählen zeigt die App eine Vorschau. Neue Einträge werden übernommen. "
            "Änderungen an bestehenden Einträgen werden vor dem Import geprüft. Einträge mit fehlenden "
            "oder ungültigen Verweisen werden übersprungen."
        )
        open_btn = QPushButton("Datei wählen")
        info.addButton(QMessageBox.Cancel)
        info.addButton(open_btn, QMessageBox.AcceptRole)
        info.setDefaultButton(open_btn)
        info.exec()
        return info.clickedButton() == open_btn

    def _detect_import_file(self, path: Path) -> tuple[dict, str, str, bool]:
        suffix = path.suffix.lower()
        if suffix == ".json":
            with path.open(encoding="utf-8-sig") as handle:
                normalized = normalize_import_payload(json.load(handle))
            return (
                normalized,
                "Planungsdaten erkannt",
                "JSON-Datei mit Projektstruktur aus dieser App.",
                False,
            )

        if suffix == ".xlsx":
            project_payload = import_project_from_excel(path)
            if self._import_payload_count(project_payload) > 0:
                return (
                    project_payload,
                    "Planungsdaten erkannt",
                    "Excel-Datei mit Projektstruktur aus dieser App.",
                    False,
                )
            try:
                room_payload = import_tiss_rooms_from_excel(path)
            except Exception:
                room_payload = {}
            if self._import_payload_count(room_payload) > 0:
                return (
                    room_payload,
                    "Raumliste erkannt",
                    "Aus der gewählten Excel-Datei erkannte Räume. Gebäude ist optional und kann im nächsten Schritt gefiltert werden.",
                    True,
                )
            lva_payload = import_lvas_from_excel(path)
            return (
                lva_payload,
                "LVA-Liste erkannt",
                "Aus der gewählten Excel-Datei erkannte LVAs. Erwartete Pflichtspalten: LVA-Nr. und Bezeichnung.",
                True,
            )

        if suffix == ".csv":
            room_payload = self._import_rooms_from_csv(path)
            if self._import_payload_count(room_payload) > 0:
                return (
                    room_payload,
                    "Raum-CSV erkannt",
                    "Erkannte Räume aus der CSV-Datei. Erwartete Pflichtspalten: Raumnummer, Raumname und Kapazität. Gebäude ist optional.",
                    True,
                )
            lva_payload = self._import_lvas_from_csv(path)
            if self._import_payload_count(lva_payload) > 0:
                return (
                    lva_payload,
                    "LVA-CSV erkannt",
                    "Erkannte LVAs aus der CSV-Datei. Pflichtspalten: LVA-Nr. und Bezeichnung. Optional: Vortragende, E-Mail, ECTS, Studiensemester und Studienrichtung.",
                    True,
                )
            project_csv_payload = import_project_file_from_csv(path)
            if self._import_payload_count(project_csv_payload) > 0:
                return (
                    project_csv_payload,
                    "Planungsdaten erkannt",
                    "CSV-Datei mit einem Projektbereich aus dieser App.",
                    False,
                )
            raise ValueError(
                "CSV-Format nicht erkannt. Räume benötigen Raumnummer, Raumname und Kapazität. "
                "LVAs benötigen mindestens LVA-Nr. und Bezeichnung. Exportierte Projekt-CSV-Dateien "
                "benötigen die Spalten aus dem App-Export."
            )

        raise ValueError("Dateityp nicht unterstützt. Bitte JSON, XLSX oder CSV wählen.")

    def import_data(self) -> None:
        if not self._show_import_intro():
            return

        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Daten importieren",
            str(self.data_dir),
            "Importdateien (*.json *.xlsx *.csv);;JSON Files (*.json);;Excel Files (*.xlsx);;CSV Files (*.csv)",
        )
        if not fn:
            return

        path = Path(fn)
        try:
            normalized, title, subtitle, needs_selection = self._detect_import_file(path)
        except Exception as e:
            QMessageBox.warning(
                self, "Import Fehler", f"Importdatei konnte nicht gelesen werden:\n{e}"
            )
            return

        if not normalized or self._import_payload_count(normalized) <= 0:
            QMessageBox.warning(self, "Import Fehler", "Keine importierbaren Daten gefunden.")
            return

        if needs_selection:
            self._select_catalog_import(
                normalized,
                title=title,
                subtitle=subtitle
                + " Die Auswahl wird anschließend über den normalen Import geprüft.",
                success_text="Daten importiert.",
            )
        else:
            self._run_import_payload(normalized, success_text=f"{title}.")

    def import_default_catalog(self) -> None:
        try:
            normalized = load_default_catalog_payload()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Standarddaten importieren",
                f"Standarddaten konnten nicht gelesen werden: {e}",
            )
            return

        self._select_catalog_import(
            normalized,
            title="Standarddaten importieren",
            subtitle=(
                f"{DEFAULT_CATALOG_LABEL}. Enthält Standardwerte für Räume und LVAs des "
                "Elektrotechnik-Bachelor-Katalogs. Wählen Sie einen Tab und importieren Sie Räume oder LVAs getrennt."
            ),
            success_text="Standarddaten importiert.",
        )

    def _select_catalog_import(
        self,
        normalized: dict,
        *,
        title: str,
        subtitle: str,
        success_text: str,
        data_dir: Path | None = None,
        refresh_after: bool = True,
    ) -> bool:
        if not normalized:
            QMessageBox.warning(self, title, "Keine importierbaren Daten gefunden.")
            return False

        target_dir = Path(data_dir or self.data_dir)
        dlg = CatalogImportDialog(self, target_dir, normalized, title=title, subtitle=subtitle)
        imported_any = False

        def handle_import(selected: dict) -> None:
            nonlocal imported_any
            if not selected:
                Toast(self, "Keine Einträge ausgewählt.", duration_ms=2500).show()
                return
            busy_text = (
                "Räume werden importiert..."
                if "raeume.json" in selected
                else "LVAs werden importiert..."
            )
            dlg.set_busy(True, busy_text)
            try:
                imported = self._run_import_payload(
                    selected,
                    success_text=success_text,
                    auto_import_new=True,
                    data_dir=target_dir,
                    refresh_after=False,
                    show_success_toast=False,
                )
                if imported:
                    imported_any = True
                    dlg.refresh_statuses()
                    headline, _details = self._import_result_summary(
                        getattr(self, "_last_import_counts", {})
                    )
                    Toast(self, f"Import: {headline}", duration_ms=3000).show()
            finally:
                dlg.set_busy(False)

        dlg.import_requested.connect(handle_import)
        dlg.exec()
        if imported_any and refresh_after:
            self.refresh_everything()
        return imported_any

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
        default_from, default_to = self._default_teacher_export_range(current_date)
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
        export_term_count = dlg.selected_term_count()
        export_lva_count = dlg.selected_lva_count_with_terms()
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
            semester_part = (
                "_".join(selected_semesters)
                if len(selected_semesters) <= 2
                else f"{len(selected_semesters)}_Semester"
            )
            export_name = f"{export_name}_{semester_part}"
        export_name = f"{export_name}_{date_from:%Y-%m-%d}_bis_{date_to:%Y-%m-%d}"
        safe_export_name = (
            "".join(
                char if char.isalnum() or char in (" ", "-", "_") else "_" for char in export_name
            )
            .strip()
            .replace(" ", "_")
        )
        export_prefix = "Wochenkalender" if export_format == "calendar" else "Termine"
        default_name = (
            f"{export_prefix}_{safe_export_name}_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        )
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
            term_label = "Termin" if export_term_count == 1 else "Termine"
            lva_label = "LVA" if export_lva_count == 1 else "LVAs"
            self._show_export_finished_dialog(
                out_path,
                "Export für Lehrende erstellt.",
                f"{export_term_count} {term_label} aus {export_lva_count} {lva_label}.",
            )
        except Exception as e:
            QMessageBox.warning(self, "Export Fehler", f"Fehler beim Export für Lehrende: {e}")

    def _run_import_payload(
        self,
        normalized: dict,
        *,
        success_text: str = "Import abgeschlossen.",
        auto_import_new: bool = False,
        data_dir: Path | None = None,
        refresh_after: bool = True,
        show_success_toast: bool = True,
    ) -> bool:
        if not normalized:
            QMessageBox.warning(self, "Import Fehler", "Keine importierbaren Daten gefunden.")
            return False

        target_dir = Path(data_dir or self.data_dir)
        try:
            is_current_project = target_dir.resolve() == self.data_dir.resolve()
        except Exception:
            is_current_project = target_dir == self.data_dir

        if payload_has_changes(target_dir, normalized) and is_current_project:
            self.undo_service.record_snapshot(self.ds)

        dlg = ImportDialog(self, target_dir, normalized, auto_import_new=auto_import_new)
        if dlg.exec() != QDialog.Accepted:
            return False
        self._last_import_counts = dlg.result_counts
        self._last_import_reference_warnings = dlg.reference_warnings
        if show_success_toast:
            self._show_import_finished_dialog(success_text, dlg.result_counts)
        if refresh_after:
            self.refresh_everything()
        return True

    def import_project(self) -> None:
        self.import_data()

    def _setup_docks(self) -> None:
        self.global_filter_dock = GlobalFilterDock(self)
        self.global_filter_dock.setObjectName("dock_global_filters")
        self.addDockWidget(Qt.TopDockWidgetArea, self.global_filter_dock)

        self.date_navigation_dock = DateNavigationDock(self)
        self.date_navigation_dock.setObjectName("dock_date_navigation")
        self.addDockWidget(Qt.TopDockWidgetArea, self.date_navigation_dock)

        self._update_top_dock_layout()
        QTimer.singleShot(0, self._update_top_dock_layout)

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

    def _update_top_dock_layout(self) -> None:
        filter_widget = self.global_filter_dock.widget()
        navigation_widget = self.date_navigation_dock.widget()
        if filter_widget is None or navigation_widget is None:
            return

        navigation_width_hint = (
            self.date_navigation_dock.preferred_inline_width()
            if hasattr(self.date_navigation_dock, "preferred_inline_width")
            else navigation_widget.sizeHint().width()
        )
        self.splitDockWidget(self.global_filter_dock, self.date_navigation_dock, Qt.Horizontal)
        navigation_width = min(navigation_width_hint + 12, max(420, self.width() // 2))
        filter_width = max(240, self.width() - navigation_width)
        self.resizeDocks(
            [self.global_filter_dock, self.date_navigation_dock],
            [filter_width, navigation_width],
            Qt.Horizontal,
        )

    def _on_global_filters_changed(self, fs: FilterState) -> None:
        """Apply global filter changes and optionally jump to semester start"""

        self.filter_state = fs

        self.planner.set_global_filter_state(fs)
        terms = self._termine_for_dock(fs)
        self.termine_dock.set_rows(terms, self.planner.state.lvas, self.planner.state.raeume)

        settings = self.ds.load_settings()
        if fs.semester and bool(settings.get("jump_to_semester_start_on_filter", True)):
            start_date = self._resolve_start_date_for_semester(fs.semester)
            if start_date:
                start_date = self._calendar_start_date_for_semester_filter(start_date)
                if self._previous_year_enabled:
                    start_date = self._previous_year_date_for(start_date)
                self._apply_start_date(start_date)
        self.refresh_conflicts()

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
        saved = self.crud.edit_termin_by_id(tid)
        jump_to_id = getattr(self.crud, "last_jump_to_termin_id", None)
        if jump_to_id:
            self.planner.jump_to_termin(str(jump_to_id))
            return
        if saved:
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
        self.planner.jump_to_termin(tid)

    def _on_nav_prev(self) -> None:
        self.planner._shift_period(-1)

    def _on_nav_next(self) -> None:
        self.planner._shift_period(+1)

    def previous_year_shortcut_mode(self) -> str:
        mode = (
            str(self.ds.load_settings().get("previous_year_shortcut_mode", "hold")).strip().lower()
        )
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
        visible_termin_ids = None
        settings = self.ds.load_settings()
        if bool(settings.get("filter_conflicts_with_global_filters", True)):
            visible_termin_ids = {
                str(t.id) for t in self._compute_filtered_termine(self.filter_state)
            }
        self.conflicts_dock.refresh_conflicts(
            self.planner.state.termine,
            visible_termin_ids=visible_termin_ids,
        )

    def refresh_docks(self) -> None:
        """Refresh dock data and option lists based on current planner state/filters"""
        lva_list = getattr(self.planner.state, "lvas", None) or []

        studienrichtungen = self.ds.load_studienrichtungen()

        typ_list = [
            t.typ for t in getattr(self.planner.state, "termine", []) if getattr(t, "typ", None)
        ]

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
            gebaeude=self.global_filter_dock.building_cb.currentData() or None,
            raum_id=self.global_filter_dock.room_cb.currentData() or None,
            typ=self.global_filter_dock.typ_cb.currentData() or None,
            dozent=self.global_filter_dock.dozent_cb.currentData() or None,
            studiensemester=self.global_filter_dock.studiensemester_cb.currentData() or None,
            zu_besprechen=bool(self.global_filter_dock.zu_besprechen_cb.isChecked()),
        )

        terms = self._termine_for_dock(self.filter_state)

        self.termine_dock.set_rows(terms, self.planner.state.lvas, self.planner.state.raeume)

        self.data_editor_dock.refresh_all()
        self.refresh_conflicts()

    def _termine_for_dock(self, fs: FilterState | None):
        settings = self.ds.load_settings()
        if bool(settings.get("filter_termine_list_with_global_filters", True)):
            return self._compute_filtered_termine(fs)
        return list(getattr(self.planner.state, "termine", []) or [])

    def _compute_filtered_termine(self, fs: FilterState | None):
        """Return the filtered list of Termine for the given filter state"""

        if fs:
            room = fs.raum_id
            building = getattr(fs, "gebaeude", None)
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
            building = filters.get("gebaeude")
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
        if building and not room:
            room_by_id = {str(r.id): r for r in self.planner.state.raeume}
            terms = [
                t
                for t in terms
                if str(getattr(room_by_id.get(str(t.raum_id)), "gebaeude", "") or "").strip()
                == building
            ]
        return terms
