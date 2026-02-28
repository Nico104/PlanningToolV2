import json
from dataclasses import replace
from datetime import date, time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QDialog, QMessageBox

from ...services.id_service import next_id
from ..dialogs import LVADialog, RaumDialog, SemesterDialog
from ...core.models import GeplantesSemester
from ..dialogs.freie_tage_dialog import FreieTageDialog
from ..dialogs.termin_dialog import TerminDialog
from ..components.widgets.delete_dialog import DeleteDialog


class CrudHandlers:
    def _geplante_semester_path(self):
        return Path(self.data_dir) / "geplante_semester.json"

    def read_geplante_semester(self):
        path = self._geplante_semester_path()
        if not path.exists():
            return []
        try:
            import json
            with open(path, encoding="utf-8") as f:
                return json.load(f)["geplante_semester"]
        except Exception:
            return []

    def write_geplante_semester(self, semester_list):
        path = self._geplante_semester_path()
        import json
        obj = {"geplante_semester": semester_list}
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if self.planner:
            self.planner.refresh()
        if hasattr(self.parent, '_refresh_geplante_semester'):
            self.parent._refresh_geplante_semester()

    def add_geplante_semester(self):
        from ..dialogs.geplante_semester_dialog import GeplanteSemesterDialog
        semester_list = self.read_geplante_semester()
        dlg = GeplanteSemesterDialog(self.parent, None)
        result = dlg.get_result()
        if not result:
            return
        # Check for duplicate ID
        if any(s["id"] == result.id for s in semester_list):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self.parent, "Fehler", f"ID '{result.id}' existiert bereits.")
            return
        semester_list.append({"id": result.id, "name": result.name, "notiz": result.notiz})
        self.write_geplante_semester(semester_list)

    def edit_geplante_semester(self):
        from ..dialogs.geplante_semester_dialog import GeplanteSemesterDialog
        semester_list = self.read_geplante_semester()
        # Find selected row
        table = getattr(self.parent.tab_geplante_semester, "table", None)
        row = table.currentRow() if table else None
        if row is None or row < 0 or row >= len(semester_list):
            return
        cur = semester_list[row]
        dlg = GeplanteSemesterDialog(self.parent, GeplantesSemester(**cur))
        result = dlg.get_result()
        if not result:
            return
        # Check for duplicate ID (if changed)
        if result.id != cur["id"] and any(s["id"] == result.id for s in semester_list):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self.parent, "Fehler", f"ID '{result.id}' existiert bereits.")
            return
        semester_list[row] = {"id": result.id, "name": result.name, "notiz": result.notiz}
        self.write_geplante_semester(semester_list)

    def del_geplante_semester(self):
        semester_list = self.read_geplante_semester()
        table = getattr(self.parent.tab_geplante_semester, "table", None)
        row = table.currentRow() if table else None
        if row is None or row < 0 or row >= len(semester_list):
            return
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self.parent, "Löschen", "Eintrag wirklich löschen?") != QMessageBox.Yes:
            return
        semester_list.pop(row)
        self.write_geplante_semester(semester_list)
    def __init__(
        self,
        mw=None,
        *,
        ds=None,
        parent=None,
        planner=None,
        lva_dock=None,
        room_dock=None,
        sem_dock=None,
        termin_dock=None,
        freie_tage_dock=None,
        data_dir=None,
    ):
        self.mw = mw
        self.ds = ds or (mw.ds if mw else None)
        self.parent = parent or mw
        self.planner = planner or (mw.planner if mw else None)
        self.lva_dock = lva_dock or (getattr(mw, "lva_dock", None) if mw else None)
        self.room_dock = room_dock or (getattr(mw, "room_dock", None) if mw else None)
        self.sem_dock = sem_dock or (getattr(mw, "sem_dock", None) if mw else None)
        self.termin_dock = termin_dock or (getattr(mw, "termine_dock", None) if mw else None)
        self.freie_tage_dock = freie_tage_dock
        self.data_dir = data_dir

    def edit_termin_by_id(self, tid: str) -> bool:
        termine = self.ds.load_termine()
        cur = next((t for t in termine if t.id == tid), None)
        if not cur:
            return False

        # debug logging removed

        sems = []
        if hasattr(self.ds, "load_semester"):
            try:
                sems = self.ds.load_semester() or []
            except Exception:
                sems = []
        dlg = TerminDialog(
            self.parent,
            lvas=self.ds.load_lvas(),
            semester=sems,
            raeume=self.ds.load_raeume(),
            termin=cur,
            settings=self.ds.load_settings(),
        )
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return False

        out = [dlg.result if t.id == tid else t for t in termine]
        self.ds.save_termine(out)
        self.planner.refresh()
        if hasattr(self.parent, '_refresh_semester'):
            self.parent._refresh_semester()
        return True


    def add_freie_tage(self) -> None:
        path = self._freie_tage_path()
        if not path:
            return

        freie = self.read_freie_tage()
        dlg = FreieTageDialog(self.parent, None)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        freie.append(dlg.result)
        self._write_freie_tage(path, freie)
    def read_freie_tage(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        if year is None:
            year = date.today().year
        # Standardpfad
        path = Path(self.data_dir) / "freie_tage" / f"freie_tage_{year}.json"
        if not path.exists():
            # Fallback auf data/freie_tage.json
            path = Path(self.data_dir) / "freie_tage.json"
        return self._read_json_list(path, "freie_tage")

    def add_freie_tage(self, year: Optional[int] = None) -> None:
        if year is None:
            year = date.today().year
        path = Path(self.data_dir) / "freie_tage" / f"freie_tage_{year}.json"
        if not path:
            return

        freie = self.read_freie_tage(year)
        dlg = FreieTageDialog(self.parent, None)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        freie.append(dlg.result)
        self._write_freie_tage(path, freie)
        self.planner.refresh()
        if hasattr(self.parent, '_refresh_semester'):
            self.parent._refresh_semester()

    def edit_freie_tage(self, year: Optional[int] = None) -> None:
        if year is None:
            year = date.today().year
        path = Path(self.data_dir) / "freie_tage" / f"freie_tage_{year}.json"
        row = self._freie_tage_row()
        if not path or row is None or row < 0:
            return

        freie = self.read_freie_tage(year)
        if row >= len(freie):
            return

        cur = freie[row]
        dlg = FreieTageDialog(self.parent, cur)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        freie[row] = dlg.result
        self._write_freie_tage(path, freie)
        self.planner.refresh()
        if hasattr(self.parent, '_refresh_semester'):
            self.parent._refresh_semester()

    def del_freie_tage(self, year: Optional[int] = None) -> None:
        if year is None:
            year = date.today().year
        path = Path(self.data_dir) / "freie_tage" / f"freie_tage_{year}.json"
        row = self._freie_tage_row()
        if not path or row is None or row < 0:
            return

        if QMessageBox.question(self.parent, "Löschen", "Eintrag wirklich löschen?") != QMessageBox.Yes:
            return

        freie = self.read_freie_tage(year)
        if row >= len(freie):
            return

        freie.pop(row)
        self._write_freie_tage(path, freie)
        self.planner.refresh()

    def add_termin(self, default_qdate=None, auto_id: bool = False) -> bool:
        dlg = TerminDialog(
            self.parent,
            lvas=self.ds.load_lvas(),
            semester=self.ds.load_semester(),
            raeume=self.ds.load_raeume(),
            termin=None,
            settings=self.ds.load_settings(),
            new_id=self._new_termin_id(),
        )
        if auto_id:
            dlg.id_le.setText(self._new_termin_id())
        if default_qdate is not None:
            dlg.date_de.setDate(default_qdate)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return False

        termine = self.ds.load_termine()
        # Serientermin: Liste von Terminen
        if isinstance(dlg.result, list):
            pass
            # Prüfe auf doppelte IDs
            existing_ids = {t.id for t in termine}
            for t in dlg.result:
                pass
                if t.id in existing_ids:
                    print(f"[DEBUG] Fehler: Termin-ID {t.id} existiert bereits!")
                    QMessageBox.warning(self.parent, "Fehler", f"Termin-ID '{t.id}' existiert bereits.")
                    return False
            termine.extend(dlg.result)
        else:
            pass
            if any(t.id == dlg.result.id for t in termine):
                pass
                QMessageBox.warning(self.parent, "Fehler", f"Termin-ID '{dlg.result.id}' existiert bereits.")
                return False
            termine.append(dlg.result)
        pass
        self.ds.save_termine(termine)
        self.planner.refresh()
        pass
        return True

    def edit_termin(self) -> None:
        tid = self._selected_termin_id()
        if not tid:
            return
        self.edit_termin_by_id(tid)

    def del_termin(self) -> None:
        tid = self._selected_termin_id()
        if not tid:
            return

        dlg = DeleteDialog(self.parent, f"Termin '{tid}' wirklich löschen?")
        if dlg.exec() != QDialog.Accepted:
            return

        termine = [t for t in self.ds.load_termine() if t.id != tid]
        self.ds.save_termine(termine)
        self.planner.refresh()

    def del_termin_by_id(self, tid: str) -> bool:
        if not tid:
            return False

        
        dlg = DeleteDialog(self.parent, f"Termin '{tid}' wirklich löschen?")
        if dlg.exec() != QDialog.Accepted:
            return False

        termine = [t for t in self.ds.load_termine() if t.id != tid]
        self.ds.save_termine(termine)
        self.planner.refresh()
        return True

    def _selected_termin_id(self) -> Optional[str]:
        if not self.termin_dock:
            return None
        if hasattr(self.termin_dock, "selected_id"):
            return self.termin_dock.selected_id()
        if hasattr(self.termin_dock, "table"):
            row = self.termin_dock.table.currentRow()
            if row < 0:
                return None
            it = self.termin_dock.table.item(row, 0)
            return it.text().strip() if it else None
        return None

    def _freie_tage_path(self, year: Optional[int] = None) -> Optional[Path]:
        if year is None:
            year = date.today().year
        return Path(self.data_dir) / "freie_tage" / f"freie_tage_{year}.json"

    def _freie_tage_row(self) -> Optional[int]:
        if not self.freie_tage_dock:
            return None
        if hasattr(self.freie_tage_dock, "selected_row"):
            return self.freie_tage_dock.selected_row()
        if hasattr(self.freie_tage_dock, "table"):
            return self.freie_tage_dock.table.currentRow()
        return None

    def _new_termin_id(self) -> str:
        termine = self.ds.load_termine()
        return next_id("T", [t.id for t in termine], width=3)

    def move_termin(
        self,
        termin_id: str,
        new_date: date,
        new_start: time,
        new_room_id: Optional[str] = None,
    ) -> bool:
        termine = self.ds.load_termine()
        t = next((x for x in termine if x.id == termin_id), None)
        if not t:
            return False

        duration_minutes = t.duration if t.duration > 0 else 30

        try:
            updates = {
                "datum": new_date,
                "start_zeit": new_start,
                "duration": duration_minutes,
            }
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

        # debug logging removed

        termine = [new_t if x.id == termin_id else x for x in termine]
        self.ds.save_termine(termine)
        self.planner.refresh()
        return True

    def unassign_termin(self, termin_id: str) -> bool:
        termine = self.ds.load_termine()
        t = next((x for x in termine if x.id == termin_id), None)
        if not t:
            return False

        new_t = replace(t, datum=None, start_zeit=None)
        termine = [new_t if x.id == termin_id else x for x in termine]
        self.ds.save_termine(termine)
        self.planner.refresh()
        return True

    def _write_freie_tage(self, path: Path, freie_tage: List[Dict[str, Any]]) -> None:
        self._write_json_list(path, "freie_tage", freie_tage)

    def _read_json_list(self, path: Optional[Path], key: str) -> List[Dict[str, Any]]:
        if not path or not path.exists():
            return []
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            lst = obj.get(key, [])
            return lst if isinstance(lst, list) else []
        except Exception:
            return []

    def _write_json_list(self, path: Path, key: str, items: List[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({key: items}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    
    def add_lva(self) -> None:
        dlg = LVADialog(self.parent, None)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        lvas = self.ds.load_lvas()
        if any(l.id == dlg.result.id for l in lvas):
            QMessageBox.warning(self.parent, "Fehler", "Diese LVA-ID existiert bereits.")
            return

        lvas.append(dlg.result)
        self.ds.save_lvas(lvas)
        self.planner.refresh()

    def edit_lva(self) -> None:
        cid = self.lva_dock.selected_id()
        if not cid:
            return

        lvas = self.ds.load_lvas()
        cur = next((l for l in lvas if l.id == cid), None)
        if not cur:
            return

        dlg = LVADialog(self.parent, cur)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        if dlg.result.id != cid and any(l.id == dlg.result.id for l in lvas):
            QMessageBox.warning(self.parent, "Fehler", "Neue LVA-ID existiert bereits.")
            return

        lvas = [dlg.result if l.id == cid else l for l in lvas]
        self.ds.save_lvas(lvas)

        if dlg.result.id != cid:
            terms = self.ds.load_termine()
            terms = [replace(t, lva_id=dlg.result.id) if t.lva_id == cid else t for t in terms]
            self.ds.save_termine(terms)

        self.planner.refresh()

    def del_lva(self) -> None:
        cid = self.lva_dock.selected_id()
        if not cid:
            return

        if QMessageBox.question(
            self.parent,
            "Löschen",
            f"LVA {cid} wirklich löschen? (Termine werden auch gelöscht)"
        ) != QMessageBox.Yes:
            return

        lvas = [l for l in self.ds.load_lvas() if l.id != cid]
        terms = [t for t in self.ds.load_termine() if t.lva_id != cid]
        self.ds.save_lvas(lvas)
        self.ds.save_termine(terms)
        self.planner.refresh()
    
    def add_room(self) -> None:
        dlg = RaumDialog(self.parent, None)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        rooms = self.ds.load_raeume()
        if any(r.id == dlg.result.id for r in rooms):
            QMessageBox.warning(self.parent, "Fehler", "Diese Raum-ID existiert bereits.")
            return

        rooms.append(dlg.result)
        self.ds.save_raeume(rooms)
        self.planner.refresh()

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
            QMessageBox.warning(self.parent, "Fehler", "Neue Raum-ID existiert bereits.")
            return

        rooms = [dlg.result if r.id == rid else r for r in rooms]
        self.ds.save_raeume(rooms)

        if dlg.result.id != rid:
            terms = self.ds.load_termine()
            terms = [replace(t, raum_id=dlg.result.id) if t.raum_id == rid else t for t in terms]
            self.ds.save_termine(terms)

        self.planner.refresh()

    def del_room(self) -> None:
        rid = self.room_dock.selected_id()
        if not rid:
            return

        if QMessageBox.question(
            self.parent,
            "Löschen",
            f"Raum {rid} wirklich löschen? (Termine werden auch gelöscht)"
        ) != QMessageBox.Yes:
            return

        rooms = [r for r in self.ds.load_raeume() if r.id != rid]
        terms = [t for t in self.ds.load_termine() if t.raum_id != rid]
        self.ds.save_raeume(rooms)
        self.ds.save_termine(terms)
        self.planner.refresh()

    
    def add_semester(self) -> None:
        dlg = SemesterDialog(self.parent, None)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        sems = self.ds.load_semester()
        if any(s.id == dlg.result.id for s in sems):
            QMessageBox.warning(self.parent, "Fehler", "Diese Semester-ID existiert bereits.")
            return

        sems.append(dlg.result)
        self.ds.save_semester(sems)
        self.planner.refresh()

    def edit_semester(self) -> None:
        sid = self.sem_dock.selected_id()
        if not sid:
            return

        sems = self.ds.load_semester()
        cur = next((s for s in sems if s.id == sid), None)
        if not cur:
            return

        dlg = SemesterDialog(self.parent, cur)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        if dlg.result.id != sid and any(s.id == dlg.result.id for s in sems):
            QMessageBox.warning(self.parent, "Fehler", "Neue Semester-ID existiert bereits.")
            return

        sems = [dlg.result if s.id == sid else s for s in sems]
        self.ds.save_semester(sems)

        if dlg.result.id != sid:
            terms = self.ds.load_termine()
            terms = [replace(t, semester_id=dlg.result.id) if t.semester_id == sid else t for t in terms]
            self.ds.save_termine(terms)

        self.planner.refresh()

    def del_semester(self) -> None:
        sid = self.sem_dock.selected_id()
        if not sid:
            return

        if QMessageBox.question(
            self.parent,
            "Löschen",
            f"Semester {sid} wirklich löschen? (Termine werden auch gelöscht)"
        ) != QMessageBox.Yes:
            return

        sems = [s for s in self.ds.load_semester() if s.id != sid]
        terms = [t for t in self.ds.load_termine() if t.semester_id != sid]
        self.ds.save_semester(sems)
        self.ds.save_termine(terms)
        self.planner.refresh()
