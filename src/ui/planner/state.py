from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ...core.models import Raum, Lehrveranstaltung, Termin
from ...services.data_service import DataService
from ...services.filter_service import filter_termine
from ...services.termin_occurrence_service import expand_termine
from ...services.termin_service import TerminService

# Manages data and filtering for the planner UI


@dataclass
class PlannerState:
    """
    Holds all loaded planner data and settings for the UI.
    Provides methods to reload data and filter Termine.
    """

    ds: DataService

    raeume: List[Raum] = field(default_factory=list)
    lvas: List[Lehrveranstaltung] = field(default_factory=list)
    termine: List[Termin] = field(default_factory=list)
    occurrences: List[Termin] = field(default_factory=list)
    termin_map: Dict[str, Termin] = field(default_factory=dict)
    settings: Dict = field(default_factory=dict)

    ts: Optional[TerminService] = None

    def reload(self) -> None:
        self.raeume = self.ds.load_raeume()
        self.lvas = self.ds.load_lvas()
        self.termine = self.ds.load_termine()
        self.occurrences = expand_termine(self.termine)
        self.termin_map = {str(t.id): t for t in self.termine}
        self.termin_map.update({str(t.id): t for t in self.occurrences})
        self.settings = self.ds.load_settings()
        self.ts = TerminService(self.settings)

    def filtered_termine(
        self,
        raum_id: Optional[str],
        typ: Optional[str] = None,
        dozent: Optional[str] = None,
        semester_id: Optional[str] = None,
        studiensemester: Optional[str] = None,
        lva_id: Optional[str] = None,
        studienrichtung: Optional[str] = None,
        zu_besprechen: bool = False,
    ) -> List[Termin]:
        lva_dict = {lva.id: lva for lva in self.lvas}
        out = filter_termine(
            self.termine,
            semester_id=semester_id,
            studiensemester=studiensemester,
            raum_id=raum_id,
            lva_id=lva_id,
            typ=typ,
            dozent=dozent,
            studienrichtung=studienrichtung,
            zu_besprechen=zu_besprechen,
            lva_dict=lva_dict,
        )
        return out
