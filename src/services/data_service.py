import json
from pathlib import Path
from datetime import datetime, date, time
from typing import Dict, List, Any

from ..core.models import Semester, Raum, Vortragende, Lehrveranstaltung, Gruppe, Termin


class DataService:
    def load_semester(self) -> List[Semester]:
        """Lädt alle Semester aus semester.json (falls vorhanden)."""
        path = self.data_dir / "semester.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8")).get("semester", [])
        out = []
        for x in raw:
            out.append(Semester(
                id=x["id"],
                name=x["name"],
                start=datetime.strptime(x["start"], "%Y-%m-%d").date(),
                end=datetime.strptime(x["end"], "%Y-%m-%d").date(),
            ))
        return out
    """
    Minimaler JSON-Speicher: lädt/schreibt die Projekt-JSON-Dateien aus dem data/-Ordner.
    """
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir


    def _read(self, filename: str, fachrichtung: str = None, semester: str = None) -> Dict[str, Any]:
        # Support new structure: Studiengang/ETIT/ss26_termine.json etc.
        if fachrichtung and semester:
            # Compose filename like 'ss26_termine.json' or 'ws26_termine.json'
            if filename == "termine.json":
                filebase = f"{semester.lower()}_termine.json"
                path = self.data_dir / "Studiengang" / fachrichtung / filebase
            else:
                path = self.data_dir / fachrichtung / semester / filename
        else:
            path = self.data_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, filename: str, obj: Dict[str, Any]) -> None:
        path = self.data_dir / filename
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _parse_date(s: str) -> date:
        return datetime.strptime(s, "%Y-%m-%d").date()

    @staticmethod
    def _parse_time(s: str) -> time:
        return datetime.strptime(s, "%H:%M").time()

    @staticmethod
    def _fmt_date(d: date) -> str:
        return d.isoformat()

    @staticmethod
    def _fmt_time(t: time) -> str:
        return t.strftime("%H:%M")

    # ---------- LOAD ----------

    def load_raeume(self) -> List[Raum]:
        raw = self._read("raeume.json")["raeume"]
        return [Raum(id=x["id"], name=x["name"], kapazitaet=int(x["kapazitaet"])) for x in raw]

    def load_lvas(self) -> List[Lehrveranstaltung]:
        settings = self.load_settings()
        fachrichtung = settings.get("start_fachrichtung", "ETIT")
        path = self.data_dir / "lehrveranstaltungen.json"
        raw = json.loads(path.read_text(encoding="utf-8"))["lehrveranstaltungen"]
        out: List[Lehrveranstaltung] = []
        for x in raw:
            v = x["vortragende"]
            out.append(Lehrveranstaltung(
                id=x["id"],
                name=x["name"],
                vortragende=Vortragende(name=v["name"], email=v.get("email", "")),
                typ=list(x.get("typ", [])),
            ))
        return out


    def load_termine(self) -> List[Termin]:
        # Load all termine from the single termine.json file for the current fachrichtung
        settings = self.load_settings()
        fachrichtung = settings.get("start_fachrichtung", "ETIT")
        path = self.data_dir / "termine.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8")).get("termine", [])
        out: List[Termin] = []
        for x in raw:
            g = x.get("gruppe")
            d_raw = x.get("datum")
            datum = self._parse_date(d_raw) if d_raw else None
            start_zeit_raw = x.get("start_zeit")
            start_zeit = self._parse_time(start_zeit_raw) if start_zeit_raw else None
            out.append(Termin(
                id=x["id"],
                lva_id=x["lva_id"],
                typ=x["typ"],
                datum=datum,
                start_zeit=start_zeit,
                raum_id=x.get("raum_id", ""),
                gruppe=(
                    Gruppe(
                        name=g.get("name", "-") if g else "-",
                        groesse=int(g.get("groesse", 0)) if g else 0,
                    ) if g is not None else None
                ),
                anwesenheitspflicht=bool(x.get("anwesenheitspflicht", False)),
                notiz=x.get("notiz", ""),
                duration=int(x.get("duration", 0)),
                semester_id=x.get("semester_id", "")
            ))
        return out


    def load_settings(self) -> Dict[str, Any]:
        # settings.json is now in src/
        settings_path = Path(__file__).parent / "../settings.json"
        return json.loads(settings_path.read_text(encoding="utf-8"))

    # ---------- SAVE ----------
    def save_semester(self, semester: List[Semester]) -> None:
        self._write("semester.json", {
            "semester": [{
                "id": s.id, "name": s.name,
                "start": self._fmt_date(s.start),
                "end": self._fmt_date(s.end)
            } for s in semester]
        })

    def save_raeume(self, raeume: List[Raum]) -> None:
        self._write("raeume.json", {
            "raeume": [{"id": r.id, "name": r.name, "kapazitaet": r.kapazitaet} for r in raeume]
        })

    def save_lvas(self, lvas: List[Lehrveranstaltung]) -> None:
        settings = self.load_settings()
        fachrichtung = settings.get("start_fachrichtung", "ETIT")
        path = self.data_dir / "lehrveranstaltungen.json"
        path.write_text(json.dumps({
            "lehrveranstaltungen": [{
                "id": l.id,
                "name": l.name,
                "vortragende": {"name": l.vortragende.name, "email": l.vortragende.email},
                "typ": list(l.typ)
            } for l in lvas]
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def save_termine(self, termine: List[Termin]) -> None:
        # Save all termine into a single termine.json file (with semester_id per termin)
        settings = self.load_settings()
        fachrichtung = settings.get("start_fachrichtung", "ETIT")
        path = self.data_dir / "termine.json"
        path.write_text(json.dumps({
            "termine": [{
                "id": t.id,
                "lva_id": t.lva_id,
                "typ": t.typ,
                "datum": self._fmt_date(t.datum) if t.datum is not None else None,
                "start_zeit": self._fmt_time(t.start_zeit) if t.start_zeit else None,
                "raum_id": t.raum_id,
                "gruppe": (
                    {
                        "name": t.gruppe.name,
                        "groesse": t.gruppe.groesse,
                    }
                    if t.gruppe is not None
                    else None
                ),
                "anwesenheitspflicht": t.anwesenheitspflicht,
                "notiz": t.notiz,
                "duration": t.duration,
                "semester_id": t.semester_id,
            } for t in termine]
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def save_settings(self, settings: Dict[str, Any]) -> None:
        # Save to src/settings.json
        settings_path = Path(__file__).parent / "../settings.json"
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")