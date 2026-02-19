from dataclasses import dataclass
from typing import Optional



@dataclass
class FilterState:
    fachrichtung: Optional[str] = None
    semester: Optional[str] = None
    lva_id: Optional[str] = None
    raum_id: Optional[str] = None
    typ: Optional[str] = None
    dozent: Optional[str] = None
