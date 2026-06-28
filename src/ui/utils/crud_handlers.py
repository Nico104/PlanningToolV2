from dataclasses import replace
from datetime import date, time
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QDialog, QMessageBox

from ...services.free_day_id_service import free_day_entry_key
from ...services.id_service import next_id
from ...services.termin_occurrence_service import occurrence_date_from_id, source_termin_id
from ...services.undo_service import UndoService
from ..dialogs import LVADialog, RaumDialog
from ...core.models import SerienAusnahme, Studiensemester, Termin
from ..components.widgets.editor_tab_widget import selected_id
from ..dialogs.freie_tage_dialog import FreieTageDialog
from ..dialogs.studienrichtung_dialog import StudienrichtungDialog
from ..dialogs.lva_termin_dialog import LVATerminDialog
from ..components.widgets.action_dialog import ActionDialog, DialogAction
from ..components.widgets.delete_dialog import DeleteDialog
from ..components.widgets.toast import Toast


class CrudHandlers:
    """Centralises all CRUD (create, read, update, delete) operations for the data editor tabs"""

    def _record_undo_snapshot(self) -> None:
        if self.undo_service and self.ds:
            self.undo_service.record_snapshot(self.ds)

    def _show_toast(self, message: str, duration_ms: int = 2500) -> None:
        target = self.parent or self.mw
        if target is None:
            return
        Toast(target, message, duration_ms=duration_ms).show()

    @staticmethod
    def _count_message(count: int, singular: str, plural: str, action: str) -> str:
        label = singular if count == 1 else plural
        return f"{count} {label} {action}."

    @staticmethod
    def _upsert_by_id(items, item, old_id: Optional[str] = None):
        if not item:
            return items
        target_id = old_id or item.id
        if any(existing.id == target_id for existing in items):
            return [item if existing.id == target_id else existing for existing in items]
        if any(existing.id == item.id for existing in items):
            return [item if existing.id == item.id else existing for existing in items]
        return [*items, item]

    @staticmethod
    def _termin_uses_room(termin: Termin, room_id: str) -> bool:
        if str(getattr(termin, "raum_id", "")) == room_id:
            return True
        return any(
            str(getattr(item, "raum_id", "") or "") == room_id
            for item in (getattr(termin, "serien_ausnahmen", []) or [])
        )

    def add_studienrichtung(self) -> None:
        studienrichtungen = self.ds.load_studienrichtungen()
        dlg = StudienrichtungDialog(self.parent, None)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        new_item = dlg.result
        new_id = str(new_item.get("id", "")).strip()
        if any(str(f.get("id", "")).strip() == new_id for f in studienrichtungen):
            QMessageBox.warning(self.parent, "Fehler", f"ID '{new_id}' existiert bereits.")
            return

        studienrichtungen.append({"id": new_id, "name": str(new_item.get("name", "")).strip()})
        self._record_undo_snapshot()
        self.ds.save_studienrichtungen(studienrichtungen)
        if self.planner:
            self.planner.refresh()
        if hasattr(self.parent, "_refresh_studienrichtungen"):
            self.parent._refresh_studienrichtungen()
        self._show_toast("Studienrichtung gespeichert.")

    def edit_studienrichtung(self) -> None:
        studienrichtungen = self.ds.load_studienrichtungen()
        if not self.studienrichtung_dock:
            return

        selected_id = self.studienrichtung_dock.selected_id()
        if not selected_id:
            return

        row = next(
            (
                i
                for i, f in enumerate(studienrichtungen)
                if str(f.get("id", "")).strip() == selected_id
            ),
            None,
        )
        if row is None:
            return

        cur = studienrichtungen[row]
        dlg = StudienrichtungDialog(self.parent, cur)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        new_item = dlg.result
        new_id = str(new_item.get("id", "")).strip()
        if new_id != selected_id and any(
            str(f.get("id", "")).strip() == new_id for f in studienrichtungen
        ):
            QMessageBox.warning(self.parent, "Fehler", f"ID '{new_id}' existiert bereits.")
            return

        studienrichtungen[row] = {"id": new_id, "name": str(new_item.get("name", "")).strip()}
        self._record_undo_snapshot()
        self.ds.save_studienrichtungen(studienrichtungen)
        if self.planner:
            self.planner.refresh()
        if hasattr(self.parent, "_refresh_studienrichtungen"):
            self.parent._refresh_studienrichtungen()
        self._show_toast("Studienrichtung gespeichert.")

    def del_studienrichtung(self) -> None:
        studienrichtungen = self.ds.load_studienrichtungen()
        if not self.studienrichtung_dock:
            return

        selected_id = self.studienrichtung_dock.selected_id()
        if not selected_id:
            return

        row = next(
            (
                i
                for i, f in enumerate(studienrichtungen)
                if str(f.get("id", "")).strip() == selected_id
            ),
            None,
        )
        if row is None:
            return

        cur = studienrichtungen[row]
        affected_lvas = [
            l
            for l in self.ds.load_lvas()
            if str(getattr(l, "studienrichtung", "")).strip() == selected_id
        ]
        detail = f"Studienrichtung: {cur.get('name') or selected_id}"
        if affected_lvas:
            detail += f"\n{len(affected_lvas)} LVA(s) behalten ihre Termine; die Studienrichtung wird dort geleert."

        if (
            DeleteDialog(
                self.parent,
                "Diese Studienrichtung wird aus den Stammdaten entfernt.",
                detail=detail,
                title="Studienrichtung löschen",
            ).exec()
            != QDialog.Accepted
        ):
            return

        studienrichtungen.pop(row)
        self._record_undo_snapshot()
        self.ds.save_studienrichtungen(studienrichtungen)
        if affected_lvas:
            self.ds.save_lvas(
                [
                    (
                        replace(l, studienrichtung="")
                        if str(getattr(l, "studienrichtung", "")).strip() == selected_id
                        else l
                    )
                    for l in self.ds.load_lvas()
                ]
            )
        if self.planner:
            self.planner.refresh()
        if hasattr(self.parent, "_refresh_studienrichtungen"):
            self.parent._refresh_studienrichtungen()
        self._show_toast("Studienrichtung gelöscht.")

    def read_studiensemester_models(self) -> List[Studiensemester]:
        models: List[Studiensemester] = []
        for item in self.ds.load_studiensemester():
            try:
                models.append(Studiensemester(**item))
            except Exception:
                continue
        return models

    def __init__(
        self,
        mw=None,
        *,
        ds=None,
        parent=None,
        planner=None,
        lva_dock=None,
        studienrichtung_dock=None,
        room_dock=None,
        termin_dock=None,
        freie_tage_dock=None,
        undo_service: Optional[UndoService] = None,
    ):
        self.mw = mw
        self.ds = ds or (mw.ds if mw else None)
        self.parent = parent or mw
        self.planner = planner or (mw.planner if mw else None)
        self.lva_dock = lva_dock or (getattr(mw, "lva_dock", None) if mw else None)
        self.studienrichtung_dock = studienrichtung_dock or (
            getattr(mw, "studienrichtung_dock", None) if mw else None
        )
        self.room_dock = room_dock or (getattr(mw, "room_dock", None) if mw else None)
        self.termin_dock = termin_dock or (getattr(mw, "termine_dock", None) if mw else None)
        self.freie_tage_dock = freie_tage_dock
        self.undo_service = undo_service or (getattr(mw, "undo_service", None) if mw else None)
        self.last_jump_to_termin_id: Optional[str] = None

    def edit_termin_by_id(self, tid: str) -> bool:
        self.last_jump_to_termin_id = None
        termine = self.ds.load_termine()
        source_id = source_termin_id(tid)
        cur = next((t for t in termine if t.id == source_id), None)
        if not cur:
            return False

        dlg = LVATerminDialog(
            self.parent,
            lvas=self.ds.load_lvas(),
            raeume=self.ds.load_raeume(),
            studiensemester=self.read_studiensemester_models(),
            studienrichtungen=self.ds.load_studienrichtungen(),
            termin=cur,
            settings=self.ds.load_settings(),
            new_id=source_id,
        )
        dialog_result = dlg.exec()
        jump_to_id = getattr(dlg, "jump_to_termin_id", None)
        if jump_to_id:
            self.last_jump_to_termin_id = str(jump_to_id)
            return False

        if dialog_result != QDialog.Accepted or not dlg.result:
            return False

        if isinstance(dlg.result, list):
            existing_ids = {t.id for t in termine if t.id != source_id}
            duplicate_id = next((t.id for t in dlg.result if t.id in existing_ids), None)
            if duplicate_id:
                QMessageBox.warning(
                    self.parent, "Fehler", f"Termin-ID '{duplicate_id}' existiert bereits."
                )
                return False
            out = [t for t in termine if t.id != source_id]
            out.extend(dlg.result)
        else:
            out = [t for t in termine if t.id != source_id]
            out.append(dlg.result)
        lvas = self._upsert_by_id(
            self.ds.load_lvas(),
            getattr(dlg, "result_lva", None),
            getattr(dlg, "source_lva_id", None),
        )
        rooms = self._upsert_by_id(
            self.ds.load_raeume(),
            getattr(dlg, "result_raum", None),
            getattr(dlg, "source_raum_id", None),
        )
        self._record_undo_snapshot()
        self.ds.save_lvas(lvas)
        self.ds.save_raeume(rooms)
        self.ds.save_termine(out)
        self.planner.refresh()
        self._show_toast("Termin gespeichert.")
        return True

    def add_freie_tage(self, year: Optional[int] = None) -> None:
        freie = self.ds.load_freie_tage()
        dlg = FreieTageDialog(self.parent, None)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        item = dict(dlg.result)
        item_key = free_day_entry_key(item)
        if item_key and any(free_day_entry_key(existing) == item_key for existing in freie):
            QMessageBox.warning(self.parent, "Fehler", "Dieser freie Zeitraum existiert bereits.")
            return
        freie.append(item)
        self._record_undo_snapshot()
        self.ds.save_freie_tage(freie)
        self.planner.refresh()
        self._show_toast("Freier Tag gespeichert.")

    def edit_freie_tage(self, year: Optional[int] = None) -> None:
        selected_key = self._selected_freie_tage_key()
        if not selected_key:
            return

        freie = self.ds.load_freie_tage()
        row = next(
            (i for i, item in enumerate(freie) if free_day_entry_key(item) == selected_key), None
        )
        if row is None:
            return

        cur = freie[row]
        dlg = FreieTageDialog(self.parent, cur)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        item = dict(dlg.result)
        item_key = free_day_entry_key(item)
        if item_key and any(
            idx != row and free_day_entry_key(existing) == item_key
            for idx, existing in enumerate(freie)
        ):
            QMessageBox.warning(self.parent, "Fehler", "Dieser freie Zeitraum existiert bereits.")
            return
        freie[row] = item
        self._record_undo_snapshot()
        self.ds.save_freie_tage(freie)
        self.planner.refresh()
        self._show_toast("Freier Tag gespeichert.")

    def del_freie_tage(self, year: Optional[int] = None) -> None:
        selected_key = self._selected_freie_tage_key()
        if not selected_key:
            return

        if (
            DeleteDialog(
                self.parent,
                "Dieser freie Zeitraum wird aus dem Projekt entfernt.",
                title="Freien Zeitraum löschen",
            ).exec()
            != QDialog.Accepted
        ):
            return

        freie = self.ds.load_freie_tage()
        row = next(
            (i for i, item in enumerate(freie) if free_day_entry_key(item) == selected_key), None
        )
        if row is None:
            return

        freie.pop(row)
        self._record_undo_snapshot()
        self.ds.save_freie_tage(freie)
        self.planner.refresh()
        self._show_toast("Freier Tag gelöscht.")

    def add_termin(self, default_qdate=None, default_semester_id: Optional[str] = None) -> bool:
        dlg = LVATerminDialog(
            self.parent,
            lvas=self.ds.load_lvas(),
            raeume=self.ds.load_raeume(),
            studiensemester=self.read_studiensemester_models(),
            studienrichtungen=self.ds.load_studienrichtungen(),
            termin=None,
            settings=self.ds.load_settings(),
            new_id=self._new_termin_id(),
            default_semester_id=default_semester_id,
        )

        # Default values for newly created Termine
        dlg.duration_sb.setValue(60)

        if default_qdate is not None:
            dlg.date_de.setDate(default_qdate)
        else:
            # For Data Editor creation: keep new entries unassigned by default
            dlg.date_de.setDate(dlg._unassigned_qdate)

        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return False

        termine = self.ds.load_termine()
        lvas = self._upsert_by_id(
            self.ds.load_lvas(),
            getattr(dlg, "result_lva", None),
            getattr(dlg, "source_lva_id", None),
        )
        rooms = self._upsert_by_id(
            self.ds.load_raeume(),
            getattr(dlg, "result_raum", None),
            getattr(dlg, "source_raum_id", None),
        )
        if isinstance(dlg.result, list):
            existing_ids = {t.id for t in termine}
            for t in dlg.result:
                if t.id in existing_ids:
                    QMessageBox.warning(
                        self.parent, "Fehler", f"Termin-ID '{t.id}' existiert bereits."
                    )
                    return False
            termine.extend(dlg.result)
        else:
            if any(t.id == dlg.result.id for t in termine):
                QMessageBox.warning(
                    self.parent, "Fehler", f"Termin-ID '{dlg.result.id}' existiert bereits."
                )
                return False
            termine.append(dlg.result)

        self._record_undo_snapshot()
        self.ds.save_lvas(lvas)
        self.ds.save_raeume(rooms)
        self.ds.save_termine(termine)
        self.planner.refresh()
        if isinstance(dlg.result, list):
            self._show_toast(
                self._count_message(len(dlg.result), "Termin", "Termine", "gespeichert")
            )
        else:
            self._show_toast("Termin gespeichert.")
        return True

    def add_termin_from_data_editor(self) -> bool:
        dlg = LVATerminDialog(
            self.parent,
            lvas=self.ds.load_lvas(),
            raeume=self.ds.load_raeume(),
            termin=None,
            settings=self.ds.load_settings(),
            new_id=self._new_termin_id(),
        )
        dlg.duration_sb.setValue(60)
        dlg.date_de.setDate(dlg._unassigned_qdate)

        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return False

        termine = self.ds.load_termine()
        if isinstance(dlg.result, list):
            existing_ids = {t.id for t in termine}
            for t in dlg.result:
                if t.id in existing_ids:
                    QMessageBox.warning(
                        self.parent, "Fehler", f"Termin-ID '{t.id}' existiert bereits."
                    )
                    return False
            termine.extend(dlg.result)
        else:
            if any(t.id == dlg.result.id for t in termine):
                QMessageBox.warning(
                    self.parent, "Fehler", f"Termin-ID '{dlg.result.id}' existiert bereits."
                )
                return False
            termine.append(dlg.result)

        self._record_undo_snapshot()
        self.ds.save_termine(termine)
        self.planner.refresh()
        if isinstance(dlg.result, list):
            self._show_toast(
                self._count_message(len(dlg.result), "Termin", "Termine", "gespeichert")
            )
        else:
            self._show_toast("Termin gespeichert.")
        return True

    def edit_termin_from_data_editor(self) -> None:
        tid = self._selected_termin_id()
        if not tid:
            return
        self.edit_termin_by_id_from_data_editor(tid)

    def edit_termin_by_id_from_data_editor(self, tid: str) -> bool:
        termine = self.ds.load_termine()
        source_id = source_termin_id(tid)
        cur = next((t for t in termine if t.id == source_id), None)
        if not cur:
            return False

        dlg = LVATerminDialog(
            self.parent,
            lvas=self.ds.load_lvas(),
            raeume=self.ds.load_raeume(),
            termin=cur,
            settings=self.ds.load_settings(),
            new_id=source_id,
        )
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return False

        if isinstance(dlg.result, list):
            existing_ids = {t.id for t in termine if t.id != source_id}
            duplicate_id = next((t.id for t in dlg.result if t.id in existing_ids), None)
            if duplicate_id:
                QMessageBox.warning(
                    self.parent, "Fehler", f"Termin-ID '{duplicate_id}' existiert bereits."
                )
                return False
            out = [t for t in termine if t.id != source_id]
            out.extend(dlg.result)
        else:
            out = [dlg.result if t.id == source_id else t for t in termine]

        self._record_undo_snapshot()
        self.ds.save_termine(out)
        self.planner.refresh()
        self._show_toast("Termin gespeichert.")
        return True

    def del_termin(self) -> None:
        tid = self._selected_termin_id()
        if not tid:
            return
        termine = self.ds.load_termine()
        source_id = source_termin_id(tid)
        cur = next((t for t in termine if t.id == source_id), None)
        label = "Serientermin" if cur and cur.is_series() else "Termin"
        dlg = DeleteDialog(self.parent, f"{label} '{source_id}' wirklich löschen?")
        if dlg.exec() != QDialog.Accepted:
            return
        termine = [t for t in termine if t.id != source_id]

        self._record_undo_snapshot()
        self.ds.save_termine(termine)
        self.planner.refresh()
        self._show_toast(f"{label} gelöscht.")

    def del_termin_by_id(self, tid: str) -> bool:
        if not tid:
            return False
        termine = self.ds.load_termine()
        source_id = source_termin_id(tid)
        cur = next((t for t in termine if t.id == source_id), None)
        label = "Serientermin" if cur and cur.is_series() else "Termin"
        dlg = DeleteDialog(self.parent, f"{label} '{source_id}' wirklich löschen?")
        if dlg.exec() != QDialog.Accepted:
            return False
        termine = [t for t in termine if t.id != source_id]

        self._record_undo_snapshot()
        self.ds.save_termine(termine)
        self.planner.refresh()
        self._show_toast(f"{label} gelöscht.")
        return True

    def _selected_termin_id(self) -> Optional[str]:
        if not self.termin_dock:
            return None
        if hasattr(self.termin_dock, "selected_id"):
            return self.termin_dock.selected_id()
        if hasattr(self.termin_dock, "table"):
            return selected_id(self.termin_dock.table)
        return None

    def _selected_freie_tage_key(self) -> Optional[str]:
        if not self.freie_tage_dock:
            return None
        return (
            self.freie_tage_dock.selected_id()
            if hasattr(self.freie_tage_dock, "selected_id")
            else None
        )

    def _new_termin_id(self) -> str:
        termine = self.ds.load_termine()
        return next_id("T", [t.id for t in termine], width=3)

    def move_termin(
        self,
        termin_id: str,
        new_date: date,
        new_start: Optional[time],
        new_room_id: Optional[str] = None,
    ) -> bool:
        termine = self.ds.load_termine()
        source_id = source_termin_id(termin_id)
        occurrence_date = occurrence_date_from_id(termin_id)
        t = next((x for x in termine if x.id == source_id), None)
        if not t:
            return False

        if t.is_series() and self._is_existing_series_exception(t, occurrence_date):
            return self._move_existing_series_exception(
                termine=termine,
                termin=t,
                occurrence_date=occurrence_date,
                new_date=new_date,
                new_start=new_start,
                new_room_id=new_room_id,
            )

        series_action = None
        if t.is_series():
            series_action = self._confirm_move_series(t, occurrence_date)
            if series_action == "cancel":
                return False
            if series_action == "single":
                return self._move_series_occurrence_as_exception(
                    termine=termine,
                    termin=t,
                    occurrence_date=occurrence_date,
                    new_date=new_date,
                    new_start=new_start,
                    new_room_id=new_room_id,
                )
            if series_action == "detach":
                return self._move_series_occurrence_as_single(
                    termine=termine,
                    termin=t,
                    occurrence_date=occurrence_date,
                    new_date=new_date,
                    new_start=new_start,
                    new_room_id=new_room_id,
                )

        duration_minutes = t.duration if t.duration > 0 else 30

        try:
            updates = {"start_zeit": new_start, "duration": duration_minutes}
            if t.is_series():
                anchor_date = occurrence_date or t.datum
                if anchor_date and t.datum:
                    visible_anchor_date = anchor_date
                    for ausnahme in getattr(t, "serien_ausnahmen", []) or []:
                        if getattr(ausnahme, "original_datum", None) == anchor_date:
                            visible_anchor_date = ausnahme.datum
                            break
                    delta = new_date - visible_anchor_date
                    updates["datum"] = t.datum + delta
                    updates["datum_bis"] = t.datum_bis + delta if t.datum_bis else None
                    updates["ausfall_daten"] = [
                        ausfall + delta for ausfall in (getattr(t, "ausfall_daten", []) or [])
                    ]
                    exceptions = list(getattr(t, "serien_ausnahmen", []) or [])
                    if exceptions and delta.days != 0:
                        shift_exceptions = self._confirm_shift_series_exceptions(
                            t, exceptions, delta
                        )
                        if shift_exceptions is None:
                            return False
                        if shift_exceptions:
                            updates["serien_ausnahmen"] = [
                                replace(
                                    ausnahme,
                                    original_datum=ausnahme.original_datum + delta,
                                    datum=ausnahme.datum + delta,
                                )
                                for ausnahme in exceptions
                            ]
                else:
                    updates["datum"] = new_date
            else:
                updates["datum"] = new_date
            if new_room_id is not None:
                updates["raum_id"] = new_room_id
            new_t = replace(t, **updates)
        except Exception:
            t.datum = new_date
            t.start_zeit = new_start
            t.duration = duration_minutes
            if new_room_id is not None:
                t.raum_id = new_room_id
            new_t = t

        termine = [new_t if x.id == source_id else x for x in termine]
        self._record_undo_snapshot()
        self.ds.save_termine(termine)
        self.planner.refresh()
        self._show_toast("Serientermin verschoben." if t.is_series() else "Termin verschoben.")
        return True

    @staticmethod
    def _is_existing_series_exception(termin: Termin, occurrence_date: Optional[date]) -> bool:
        if occurrence_date is None:
            return False
        return any(
            getattr(item, "original_datum", None) == occurrence_date
            for item in (getattr(termin, "serien_ausnahmen", []) or [])
        )

    def _move_existing_series_exception(
        self,
        *,
        termine: List[Termin],
        termin: Termin,
        occurrence_date: date,
        new_date: date,
        new_start: Optional[time],
        new_room_id: Optional[str],
    ) -> bool:
        existing = next(
            (
                item
                for item in (getattr(termin, "serien_ausnahmen", []) or [])
                if getattr(item, "original_datum", None) == occurrence_date
            ),
            None,
        )
        if existing is None:
            return False

        effective_start = (
            new_start
            if new_start is not None
            else existing.start_zeit if existing.start_zeit is not None else termin.start_zeit
        )
        effective_room_id = (
            new_room_id
            if new_room_id is not None
            else existing.raum_id if existing.raum_id is not None else termin.raum_id
        )
        effective_duration = existing.duration if existing.duration is not None else termin.duration
        matches_master = (
            new_date == occurrence_date
            and effective_start == termin.start_zeit
            and effective_room_id == termin.raum_id
            and effective_duration == termin.duration
        )

        exceptions = [
            item
            for item in (getattr(termin, "serien_ausnahmen", []) or [])
            if getattr(item, "original_datum", None) != occurrence_date
        ]
        if not matches_master:
            exceptions.append(
                SerienAusnahme(
                    original_datum=occurrence_date,
                    datum=new_date,
                    start_zeit=effective_start,
                    raum_id=effective_room_id,
                    duration=effective_duration,
                )
            )
            exceptions.sort(key=lambda item: item.original_datum)

        updated_series = replace(termin, serien_ausnahmen=exceptions)
        updated = [updated_series if item.id == termin.id else item for item in termine]
        self._record_undo_snapshot()
        self.ds.save_termine(updated)
        self.planner.refresh()
        self._show_toast(
            "Serienausnahme zurückgesetzt." if matches_master else "Serienausnahme verschoben."
        )
        return True

    def _move_series_occurrence_as_exception(
        self,
        *,
        termine: List[Termin],
        termin: Termin,
        occurrence_date: Optional[date],
        new_date: date,
        new_start: Optional[time],
        new_room_id: Optional[str],
    ) -> bool:
        anchor_date = occurrence_date or termin.datum
        if anchor_date is None:
            return False

        duration_minutes = termin.duration if termin.duration > 0 else 30
        exceptions = [
            item
            for item in (getattr(termin, "serien_ausnahmen", []) or [])
            if getattr(item, "original_datum", None) != anchor_date
        ]
        exceptions.append(
            SerienAusnahme(
                original_datum=anchor_date,
                datum=new_date,
                start_zeit=new_start,
                raum_id=new_room_id if new_room_id is not None else termin.raum_id,
                duration=duration_minutes,
            )
        )
        exceptions.sort(key=lambda item: item.original_datum)

        skipped_dates = [
            value for value in (getattr(termin, "ausfall_daten", []) or []) if value != anchor_date
        ]
        updated_series = replace(
            termin,
            ausfall_daten=skipped_dates,
            serien_ausnahmen=exceptions,
        )
        updated = [updated_series if item.id == termin.id else item for item in termine]
        self._record_undo_snapshot()
        self.ds.save_termine(updated)
        self.planner.refresh()
        self._show_toast("Termin innerhalb der Serie verschoben.")
        return True

    def _move_series_occurrence_as_single(
        self,
        *,
        termine: List[Termin],
        termin: Termin,
        occurrence_date: Optional[date],
        new_date: date,
        new_start: Optional[time],
        new_room_id: Optional[str],
    ) -> bool:
        anchor_date = occurrence_date or termin.datum
        if anchor_date is None:
            return False

        skipped_dates = list(getattr(termin, "ausfall_daten", []) or [])
        if anchor_date not in skipped_dates:
            skipped_dates.append(anchor_date)
            skipped_dates.sort()

        existing_ids = [str(item.id) for item in termine]
        new_id = next_id("T", existing_ids, width=3)
        duration_minutes = termin.duration if termin.duration > 0 else 30

        updated_series = replace(termin, ausfall_daten=skipped_dates)
        single_termin = replace(
            termin,
            id=new_id,
            datum=new_date,
            start_zeit=new_start,
            raum_id=new_room_id if new_room_id is not None else termin.raum_id,
            duration=duration_minutes,
            datum_bis=None,
            periodizitaet=None,
            ausfall_daten=[],
            serien_ausnahmen=[],
        )

        updated = [updated_series if item.id == termin.id else item for item in termine]
        updated.append(single_termin)
        self._record_undo_snapshot()
        self.ds.save_termine(updated)
        self.planner.refresh()
        self._show_toast("Termin aus Serie einzeln verschoben.")
        return True

    def _confirm_move_series(self, termin: Termin, occurrence_date: Optional[date]) -> str:
        termin_label = termin.name or termin.id
        moved_date = occurrence_date or termin.datum
        date_text = moved_date.strftime("%d.%m.%Y") if moved_date else "dieser Termin"

        dlg = ActionDialog(
            self.parent,
            title="Serientermin verschieben",
            subtitle=f"'{termin_label}' am {date_text} ist Teil einer Serie.",
            section_title="Auswirkung der Verschiebung",
            actions=[
                DialogAction(
                    "series",
                    "Ganze Serie verschieben",
                    "Alle Termine der Serie werden um dieselbe Differenz verschoben.",
                ),
                DialogAction(
                    "single",
                    "Nur diesen Termin verschieben",
                    "Der Termin bleibt Teil der Serie. Für dieses Vorkommen wird eine Ausnahme gespeichert.",
                ),
                DialogAction(
                    "detach",
                    "Als Einzeltermin lösen",
                    "Dieses Vorkommen wird als normaler Termin gespeichert und in der Serie ausgelassen.",
                ),
            ],
        )
        if dlg.exec() != QDialog.Accepted:
            return "cancel"
        return dlg.result_key or "cancel"

    def _confirm_shift_series_exceptions(
        self,
        termin: Termin,
        exceptions: List[SerienAusnahme],
        delta,
    ) -> Optional[bool]:
        delta_days = getattr(delta, "days", 0)
        if not exceptions or delta_days == 0:
            return False

        direction = "später" if delta_days > 0 else "früher"
        days_text = f"{abs(delta_days)} Tag(e) {direction}"
        examples = []
        for ausnahme in sorted(exceptions, key=lambda item: item.original_datum)[:3]:
            target_old = ausnahme.datum.strftime("%d.%m.%Y")
            target_new = (ausnahme.datum + delta).strftime("%d.%m.%Y")
            time_text = (
                f" um {ausnahme.start_zeit.strftime('%H:%M')}" if ausnahme.start_zeit else ""
            )
            examples.append(f"<b>{target_old}{time_text} -> {target_new}{time_text}</b>")

        remaining = len(exceptions) - len(examples)
        if remaining > 0:
            examples.append(f"... plus {remaining} weitere Ausnahme(n).")

        subtitle = (
            f"'{termin.name or termin.id}' wird um {days_text} verschoben.\n\n"
            "Dabei passiert immer:\n"
            "- Die normale Serie wird verschoben.\n"
            "- Ausfälle werden mitverschoben.\n\n"
            "In dieser Serie gibt es zusätzlich einzeln geänderte Termine:"
        )
        shifted_description = "Diese Termine werden mit der Serie verschoben:<br>" + "<br>".join(
            examples
        )

        dlg = ActionDialog(
            self.parent,
            title="Einzeln geänderte Termine mitverschieben?",
            subtitle=subtitle,
            section_title="Sollen diese einzeln geänderten Termine auch mitverschoben werden?",
            actions=[
                DialogAction(
                    "shift",
                    "Ja, mitverschieben",
                    shifted_description,
                ),
                DialogAction(
                    "keep",
                    "Nein, dort lassen",
                    "Die einzeln geänderten Termine bleiben auf ihren aktuellen Daten. "
                    "Nur die normale Serie und die Ausfälle werden verschoben.",
                ),
            ],
        )
        if dlg.exec() != QDialog.Accepted:
            return None
        if dlg.result_key == "shift":
            return True
        if dlg.result_key == "keep":
            return False
        return None

    def unassign_termin(self, termin_id: str) -> bool:
        termine = self.ds.load_termine()
        source_id = source_termin_id(termin_id)
        t = next((x for x in termine if x.id == source_id), None)
        if not t:
            return False

        if t.is_series():
            termin_label = t.name or termin_id
            occurrence_date = occurrence_date_from_id(termin_id)
            details = []
            display_date = occurrence_date or t.datum
            if display_date:
                details.append(display_date.strftime("%d.%m.%Y"))
            if t.start_zeit:
                details.append(t.start_zeit.strftime("%H:%M"))
            detail_text = f" ({', '.join(details)})" if details else ""

            actions = [
                DialogAction(
                    "series",
                    "Ganze Serie zurückschieben",
                    "Alle Vorkommen der Serie werden aus dem Kalender entfernt und als unzugewiesener Termin geführt.",
                ),
            ]
            if occurrence_date:
                actions.append(
                    DialogAction(
                        "single_cancel",
                        "Nur dieser Termin fällt aus",
                        "Dieses Vorkommen wird aus dem Kalender entfernt. Die restliche Serie bleibt unverändert.",
                    )
                )

            dlg = ActionDialog(
                self.parent,
                title="Serientermin zurück in die Terminliste",
                subtitle=f"'{termin_label}'{detail_text} ist Teil einer Serie.",
                section_title="Auswirkung",
                actions=actions,
            )
            if dlg.exec() != QDialog.Accepted:
                return False

            series_action = dlg.result_key
            if series_action == "single_cancel" and occurrence_date:
                skipped_dates = sorted({*(getattr(t, "ausfall_daten", []) or []), occurrence_date})
                exceptions = [
                    item
                    for item in (getattr(t, "serien_ausnahmen", []) or [])
                    if getattr(item, "original_datum", None) != occurrence_date
                ]
                new_t = replace(t, ausfall_daten=skipped_dates, serien_ausnahmen=exceptions)
            elif series_action == "series":
                new_t = replace(
                    t,
                    datum=None,
                    start_zeit=None,
                    datum_bis=None,
                    periodizitaet=None,
                    ausfall_daten=[],
                    serien_ausnahmen=[],
                )
            else:
                return False
            termine = [new_t if x.id == source_id else x for x in termine]
        else:
            new_t = replace(t, datum=None, start_zeit=None)
            termine = [new_t if x.id == source_id else x for x in termine]

        self._record_undo_snapshot()
        self.ds.save_termine(termine)
        self.planner.refresh()
        if t.is_series() and series_action == "single_cancel":
            self._show_toast("Termin als Ausfall markiert.")
        else:
            self._show_toast(
                "Serientermin zurück in die Terminliste verschoben."
                if t.is_series()
                else "Termin-Zuweisung entfernt."
            )
        return True

    def add_lva(self) -> None:
        dlg = LVADialog(
            self.parent,
            None,
            self.read_studiensemester_models(),
            self.ds.load_studienrichtungen(),
        )
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        lvas = self.ds.load_lvas()
        if any(l.id == dlg.result.id for l in lvas):
            QMessageBox.warning(self.parent, "Fehler", "Diese LVA-Nr. existiert bereits.")
            return

        lvas.append(dlg.result)
        self._record_undo_snapshot()
        self.ds.save_lvas(lvas)
        self.planner.refresh()
        self._show_toast("LVA gespeichert.")

    def edit_lva(self) -> None:
        cid = self.lva_dock.selected_id()
        if not cid:
            return

        lvas = self.ds.load_lvas()
        cur = next((l for l in lvas if l.id == cid), None)
        if not cur:
            return

        dlg = LVADialog(
            self.parent,
            cur,
            self.read_studiensemester_models(),
            self.ds.load_studienrichtungen(),
        )
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        if dlg.result.id != cid and any(l.id == dlg.result.id for l in lvas):
            QMessageBox.warning(self.parent, "Fehler", "Neue LVA-Nr. existiert bereits.")
            return

        lvas = [dlg.result if l.id == cid else l for l in lvas]
        self._record_undo_snapshot()
        self.ds.save_lvas(lvas)

        if dlg.result.id != cid:
            terms = self.ds.load_termine()
            terms = [replace(t, lva_id=dlg.result.id) if t.lva_id == cid else t for t in terms]
            self.ds.save_termine(terms)

        self.planner.refresh()
        self._show_toast("LVA gespeichert.")

    def del_lva(self) -> None:
        cid = self.lva_dock.selected_id()
        if not cid:
            return

        all_terms = self.ds.load_termine()
        terms = [t for t in all_terms if t.lva_id != cid]
        deleted_count = len(all_terms) - len(terms)
        detail = f"{deleted_count} Termin(e) werden mitgelöscht." if deleted_count else ""

        if (
            DeleteDialog(
                self.parent,
                f"LVA {cid} wird aus den Stammdaten entfernt.",
                detail=detail,
                title="LVA löschen",
            ).exec()
            != QDialog.Accepted
        ):
            return

        lvas = [l for l in self.ds.load_lvas() if l.id != cid]
        self._record_undo_snapshot()
        self.ds.save_lvas(lvas)
        if deleted_count:
            self.ds.save_termine(terms)
        self.planner.refresh()
        message = "LVA gelöscht."
        if deleted_count > 0:
            message += f" {self._count_message(deleted_count, 'Termin', 'Termine', 'mitgelöscht')}"
        self._show_toast(message)

    def add_room(self) -> None:
        dlg = RaumDialog(self.parent, None)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        rooms = self.ds.load_raeume()
        if any(r.id == dlg.result.id for r in rooms):
            QMessageBox.warning(self.parent, "Fehler", "Diese Raumnummer existiert bereits.")
            return

        rooms.append(dlg.result)
        self._record_undo_snapshot()
        self.ds.save_raeume(rooms)
        self.planner.refresh()
        self._show_toast("Raum gespeichert.")

    def edit_room(self) -> None:
        rid = self.room_dock.selected_id()
        if not rid:
            return

        rooms = self.ds.load_raeume()
        cur = next((r for r in rooms if r.id == rid), None)
        if not cur:
            return

        dlg = RaumDialog(self.parent, cur)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        if dlg.result.id != rid and any(r.id == dlg.result.id for r in rooms):
            QMessageBox.warning(self.parent, "Fehler", "Neue Raumnummer existiert bereits.")
            return

        rooms = [dlg.result if r.id == rid else r for r in rooms]
        self._record_undo_snapshot()
        self.ds.save_raeume(rooms)

        if dlg.result.id != rid:
            terms = self.ds.load_termine()
            terms = [replace(t, raum_id=dlg.result.id) if t.raum_id == rid else t for t in terms]
            self.ds.save_termine(terms)

        self.planner.refresh()
        self._show_toast("Raum gespeichert.")

    def del_room(self) -> None:
        rid = self.room_dock.selected_id()
        if not rid:
            return

        all_terms = self.ds.load_termine()
        used_count = sum(1 for t in all_terms if self._termin_uses_room(t, rid))
        detail = ""
        if used_count:
            detail = f"{used_count} Termin(e) behalten bestehen; der Raum wird dort entfernt."

        if (
            DeleteDialog(
                self.parent,
                f"Raum {rid} wird aus den Stammdaten entfernt.",
                detail=detail,
                title="Raum löschen",
            ).exec()
            != QDialog.Accepted
        ):
            return

        rooms = [r for r in self.ds.load_raeume() if r.id != rid]
        terms = [
            (
                replace(
                    t,
                    raum_id=(
                        "" if str(getattr(t, "raum_id", "")) == rid else getattr(t, "raum_id", "")
                    ),
                    serien_ausnahmen=[
                        (
                            replace(item, raum_id=None)
                            if str(getattr(item, "raum_id", "") or "") == rid
                            else item
                        )
                        for item in (getattr(t, "serien_ausnahmen", []) or [])
                    ],
                )
                if self._termin_uses_room(t, rid)
                else t
            )
            for t in all_terms
        ]
        self._record_undo_snapshot()
        self.ds.save_raeume(rooms)
        if used_count:
            self.ds.save_termine(terms)
        self.planner.refresh()
        self._show_toast("Raum gelöscht.")
