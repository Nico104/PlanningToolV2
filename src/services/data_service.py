import json
from pathlib import Path
from datetime import datetime, date, time
from typing import Dict, List, Any

from ..core.models import Raum, Vortragende, Lehrveranstaltung, Gruppe, Termin


class DataService:
    """
    Minimal JSON layer: loads and writes the project's JSON data files from the data/ directory
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir


    def _read(self, filename: str) -> Dict[str, Any]:
        path = self.data_dir / filename
        # Use utf-8-sig to transparently handle files with optional UTF-8 BOM.
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def _write(self, filename: str, obj: Dict[str, Any]) -> None:
        path = self.data_dir / filename
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _parse_time(s: str) -> time:
        return datetime.strptime(s, "%H:%M").time()

    @staticmethod
    def _fmt_date(d: date) -> str:
        return d.isoformat()

    @staticmethod
    def _fmt_time(t: time) -> str:
        return t.strftime("%H:%M")

    @staticmethod
    def _parse_optional_date(value: Any) -> date | None:
        if not value:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    @staticmethod
    def _parse_date_list(value: Any) -> List[date]:
        if not isinstance(value, list):
            return []
        out: List[date] = []
        for item in value:
            try:
                parsed = DataService._parse_optional_date(item)
            except Exception:
                parsed = None
            if parsed is not None:
                out.append(parsed)
        return out

    @staticmethod
    def _parse_periodizitaet(value: Any) -> str | None:
        text = str(value or "").strip()
        if not text or text.lower() == "keine":
            return None
        return text

    def load_raeume(self) -> List[Raum]:
        raw = self._read("raeume.json")["raeume"]
        return [Raum(id=x["id"], name=x["name"], kapazitaet=int(x["kapazitaet"])) for x in raw]

    def load_lvas(self) -> List[Lehrveranstaltung]:
        settings = self.load_settings()
        studienrichtung = settings.get("start_studienrichtung", "ETIT")
        path = self.data_dir / "lehrveranstaltungen.json"
        raw = json.loads(path.read_text(encoding="utf-8-sig"))["lehrveranstaltungen"]
        out: List[Lehrveranstaltung] = []
        for x in raw:
            v = x["vortragende"]
            raw_studiensemester = x.get("studiensemester", [])
            if not isinstance(raw_studiensemester, list):
                raw_studiensemester = []
            studiensemester = []
            seen = set()
            for item in raw_studiensemester:
                semester_id = str(item).strip()
                if not semester_id or semester_id in seen:
                    continue
                seen.add(semester_id)
                studiensemester.append(semester_id)
            out.append(Lehrveranstaltung(
                id=x["id"],
                name=x["name"],
                vortragende=Vortragende(name=v["name"], email=v.get("email", "")),
                typ=list(x.get("typ", [])),
                studiensemester=studiensemester,
                studienrichtung=str(x.get("studienrichtung", studienrichtung or "ETIT")).strip() or "ETIT",
                ects=str(x.get("ects", "")).strip(),
            ))
        return out


    def load_termine(self) -> List[Termin]:
        # Load all termine from the single termine.json file.
        path = self.data_dir / "termine.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8-sig")).get("termine", [])
        return [self._termin_from_json(x) for x in raw]

    def _termin_from_json(self, x: Dict[str, Any]) -> Termin:
        g = x.get("gruppe")
        datum = self._parse_optional_date(x.get("datum"))
        start_zeit_raw = x.get("start_zeit")
        start_zeit = self._parse_time(start_zeit_raw) if start_zeit_raw else None
        return Termin(
            name=x.get("name", ""),
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
            semester_id=x.get("semester_id", ""),
            datum_bis=self._parse_optional_date(x.get("datum_bis")),
            periodizitaet=self._parse_periodizitaet(x.get("periodizitaet")),
            ausfall_daten=self._parse_date_list(x.get("ausfall_daten")),
        )


    def load_settings(self) -> Dict[str, Any]:
        # settings.json is now in src/
        settings_path = Path(__file__).parent / "../settings.json"
        return json.loads(settings_path.read_text(encoding="utf-8-sig"))

    # ---------- SAVE ----------
    def save_raeume(self, raeume: List[Raum]) -> None:
        self._write("raeume.json", {
            "raeume": [{"id": r.id, "name": r.name, "kapazitaet": r.kapazitaet} for r in raeume]
        })

    def save_lvas(self, lvas: List[Lehrveranstaltung]) -> None:
        settings = self.load_settings()
        studienrichtung = settings.get("start_studienrichtung", "ETIT")
        path = self.data_dir / "lehrveranstaltungen.json"
        path.write_text(json.dumps({
            "lehrveranstaltungen": [{
                "id": l.id,
                "name": l.name,
                "vortragende": {"name": l.vortragende.name, "email": l.vortragende.email},
                "studiensemester": l.studiensemester,
                "studienrichtung": str(getattr(l, "studienrichtung", studienrichtung or "ETIT")).strip() or "ETIT",
                "ects": str(getattr(l, "ects", "")).strip(),
            } for l in lvas]
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def save_termine(self, termine: List[Termin]) -> None:
        # Save all termine into a single termine.json file (with semester_id per termin)
        path = self.data_dir / "termine.json"
        path.write_text(json.dumps({
            "termine": [{
                "name": t.name,
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
                "datum_bis": self._fmt_date(t.datum_bis) if t.datum_bis is not None else None,
                "periodizitaet": getattr(t, "periodizitaet", None) if t.datum_bis is not None else None,
                "ausfall_daten": [
                    self._fmt_date(d) for d in (getattr(t, "ausfall_daten", []) or [])
                ],
            } for t in termine]
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def save_settings(self, settings: Dict[str, Any]) -> None:
        # Save to src/settings.json
        settings_path = Path(__file__).parent / "../settings.json"
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    

    def load_studienrichtungen(self) -> List[Dict[str, Any]]:
        path = self.data_dir / "studienrichtungen.json"
        if not path.exists():
            return []
        try:
            obj = json.loads(path.read_text(encoding="utf-8-sig"))
            items = obj.get("studienrichtungen", [])
            return items if isinstance(items, list) else []
        except Exception:
            return []

    def save_studienrichtungen(self, studienrichtungen: List[Dict[str, Any]]) -> None:
        path = self.data_dir / "studienrichtungen.json"
        path.write_text(
            json.dumps({"studienrichtungen": studienrichtungen}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

   

    def load_freie_tage(self) -> List[Dict[str, Any]]:
        path = self.data_dir / "freie_tage.json"
        if not path.exists():
            return []
        try:
            obj = json.loads(path.read_text(encoding="utf-8-sig"))
            items = obj.get("freie_tage", [])
            return items if isinstance(items, list) else []
        except Exception:
            return []

    def save_freie_tage(self, freie_tage: List[Dict[str, Any]]) -> None:
        path = self.data_dir / "freie_tage.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        cleaned_items: List[Dict[str, Any]] = []
        for item in freie_tage:
            cleaned_items.append(
                {
                    key: value
                    for key, value in dict(item).items()
                    if key not in {"quelle", "quelle_id"}
                }
            )
        path.write_text(
            json.dumps({"freie_tage": cleaned_items}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    

    def load_studiensemester(self) -> List[Dict[str, Any]]:
        path = self.data_dir / "studiensemester.json"
        if not path.exists():
            return []
        try:
            obj = json.loads(path.read_text(encoding="utf-8-sig"))
            items = obj.get("studiensemester", [])
            return items if isinstance(items, list) else []
        except Exception:
            return []

    def save_studiensemester(self, semester_list: List[Dict[str, Any]]) -> None:
        path = self.data_dir / "studiensemester.json"
        path.write_text(
            json.dumps({"studiensemester": semester_list}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
