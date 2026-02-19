from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ...core.models import Semester, Raum, Lehrveranstaltung, Termin
from ...services.data_service import DataService
from ...services.filter_service import filter_termine
from ...services.termin_service import TerminService

#Manages data and filtering for the planner UI

@dataclass
class PlannerState:
    ds: DataService

    raeume: List[Raum] = field(default_factory=list)
    lvas: List[Lehrveranstaltung] = field(default_factory=list)
    termine: List[Termin] = field(default_factory=list)
    settings: Dict = field(default_factory=dict)

    ts: Optional[TerminService] = None

    def reload(self) -> None:
        self.raeume = self.ds.load_raeume()
        self.lvas = self.ds.load_lvas()
        self.termine = self.ds.load_termine()
        self.settings = self.ds.load_settings()
        self.ts = TerminService(self.settings)

    def filtered_termine(self, raum_id: Optional[str], q: str, typ: Optional[str] = None, dozent: Optional[str] = None, semester_id: Optional[str] = None) -> List[Termin]:
        # baue lva_dict für schnellen Zugriff
        lva_dict = {lva.id: lva for lva in self.lvas}
        out = filter_termine(self.termine, semester_id=semester_id, raum_id=raum_id, typ=typ, dozent=dozent, lva_dict=lva_dict)
        q = (q or "").strip().lower()
        if q:
            def match(t: Termin) -> bool:
                lva = lva_dict.get(t.lva_id)
                hay = " ".join([
                    t.lva_id,
                    lva.name if lva else "",
                    lva.vortragende.name if lva else "",
                ]).lower()
                return q in hay
            out = [t for t in out if match(t)]
        return out
