from dataclasses import dataclass
from datetime import date, time
from typing import Optional, List, Dict


@dataclass(frozen=True)
class Semester:
    id: str
    name: str
    start: date
    end: date


@dataclass(frozen=True)
class Raum:
    id: str
    name: str
    kapazitaet: int


@dataclass(frozen=True)
class Vortragende:
    name: str
    email: str


@dataclass(frozen=True)
class Lehrveranstaltung:
    id: str
    name: str
    vortragende: Vortragende
    typ: List[str]  # erlaubte Termin-Typen, z.B. ["VO", "UE"]


@dataclass(frozen=True)
class Zeitfenster:
    von: time
    bis: time


@dataclass(frozen=True)
class Gruppe:
    name: str
    groesse: int


@dataclass(frozen=True)
class Termin:
    name: str
    id: str
    lva_id: str
    typ: str
    datum: Optional[date]
    start_zeit: Optional[time]
    raum_id: str
    gruppe: Optional[Gruppe]
    anwesenheitspflicht: bool
    notiz: str = ""
    duration: int = 0  # duration in minutes
    semester_id: str = ""

    
    def get_end_time(self) -> Optional[time]:
        if self.start_zeit and self.duration > 0:
            from datetime import datetime, date as _date, timedelta
            dummy_date = _date(2000, 1, 1)
            dt_von = datetime.combine(dummy_date, self.start_zeit)
            dt_bis = dt_von + timedelta(minutes=self.duration)
            return dt_bis.time()
        return None
    



@dataclass
class ConflictIssue:
    #Represents a conflict or warning issue with scheduling
    severity: str  # "conflict" or "warning"
    category: str  # e.g. "room", "group", "lecturer", "incomplete", "time_period"
    termin_ids: List[str]  # one or two termin IDs involved
    message: str
    datum: Optional[date]
    zeit_von: Optional[time]
    zeit_bis: Optional[time]
    raum: str
    lva: str
    gruppe: str