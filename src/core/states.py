from dataclasses import dataclass
from typing import Optional



@dataclass
class FilterState:
    """Represents the current set of filters the user has chosen in the planner UI"""
    studienrichtung: Optional[str] = None
    semester: Optional[str] = None
    lva_id: Optional[str] = None
    gebaeude: Optional[str] = None
    raum_id: Optional[str] = None
    typ: Optional[str] = None
    dozent: Optional[str] = None
    studiensemester: Optional[str] = None
    zu_besprechen: bool = False
