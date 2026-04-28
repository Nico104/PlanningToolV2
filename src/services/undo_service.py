from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..core.models import Lehrveranstaltung, Raum, Semester, Termin
from .data_service import DataService


@dataclass
class ProjectSnapshot:
    termine: List[Termin]
    lvas: List[Lehrveranstaltung]
    raeume: List[Raum]
    semester: List[Semester]
    fachrichtungen: List[Dict[str, Any]]
    freie_tage: List[Dict[str, Any]]
    geplante_semester: List[Dict[str, Any]]


class UndoService:
    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self._undo_stack: List[ProjectSnapshot] = []
        self._redo_stack: List[ProjectSnapshot] = []
        self._history_changed_callbacks: List[Callable[[], None]] = []

    def on_history_changed(self, callback: Callable[[], None]) -> None:
        if not callable(callback):
            return
        if callback not in self._history_changed_callbacks:
            self._history_changed_callbacks.append(callback)

    def _emit_history_changed(self) -> None:
        for cb in list(self._history_changed_callbacks):
            try:
                cb()
            except Exception:
                pass

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def record_snapshot(self, ds: DataService) -> None:
        self._undo_stack.append(self.capture(ds))
        if len(self._undo_stack) > self.max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._emit_history_changed()

    def undo(self, ds: DataService) -> Optional[ProjectSnapshot]:
        if not self._undo_stack:
            return None
        self._redo_stack.append(self.capture(ds))
        snapshot = self._undo_stack.pop()
        self._emit_history_changed()
        return snapshot

    def redo(self, ds: DataService) -> Optional[ProjectSnapshot]:
        if not self._redo_stack:
            return None
        self._undo_stack.append(self.capture(ds))
        snapshot = self._redo_stack.pop()
        self._emit_history_changed()
        return snapshot

    def capture(self, ds: DataService) -> ProjectSnapshot:
        return ProjectSnapshot(
            termine=deepcopy(ds.load_termine()),
            lvas=deepcopy(ds.load_lvas()),
            raeume=deepcopy(ds.load_raeume()),
            semester=deepcopy(ds.load_semester()),
            fachrichtungen=deepcopy(ds.load_fachrichtungen()),
            freie_tage=deepcopy(ds.load_freie_tage()),
            geplante_semester=deepcopy(ds.load_geplante_semester()),
        )

    def restore(self, ds: DataService, snapshot: ProjectSnapshot) -> None:
        ds.save_termine(deepcopy(snapshot.termine))
        ds.save_lvas(deepcopy(snapshot.lvas))
        ds.save_raeume(deepcopy(snapshot.raeume))
        ds.save_semester(deepcopy(snapshot.semester))
        ds.save_fachrichtungen(deepcopy(snapshot.fachrichtungen))
        ds.save_freie_tage(deepcopy(snapshot.freie_tage))
        ds.save_geplante_semester(deepcopy(snapshot.geplante_semester))