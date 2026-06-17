from pathlib import Path
import json
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QWidget, QFrame,
    QMessageBox, QApplication,
)

from ...services.import_merge_service import (
    IMPORT_FILE_SCHEMAS,
    effective_import_entry,
    get_entry_id,
    payload_list,
)
from ...services.app_config_service import load_default_config

class ImportDialog(QDialog):
    """Steps through every changed entry across all imported files and lets the user merge or ignore each."""

    def __init__(self, parent: QWidget, data_dir: Path, imported_data: dict, *, auto_import_new: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Import prüfen")
        self.setObjectName("importDialog")
        self.data_dir = Path(data_dir)
        self.imported_data = imported_data or {}
        self.auto_import_new = auto_import_new
        self.result_counts: dict[str, dict[str, int]] = {}
        self.reference_warnings: list[str] = []

        if self.auto_import_new:
            QTimer.singleShot(0, self._interactive_import)
            return

        layout = QVBoxLayout(self)
        hdr = QLabel("Import prüfen")
        hdr.setObjectName("ImportHeader")
        layout.addWidget(hdr)

        summary = QLabel(self._build_import_summary())
        summary.setObjectName("ImportSubHeader")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        status_help = QLabel(
            "Neu wird hinzugefügt. Geändert aktualisiert einen bestehenden Eintrag. "
            "Vorhanden ist identisch und wird übersprungen."
        )
        status_help.setObjectName("ImportHelp")
        status_help.setWordWrap(True)
        layout.addWidget(status_help)

        self.reference_warnings = self._reference_warnings()
        if self.reference_warnings:
            warning_label = QLabel(
                f"{len(self.reference_warnings)} problematische Verweise gefunden. "
                "Einträge mit fehlenden Stammdaten werden beim Import übersprungen."
            )
            warning_label.setObjectName("ImportWarning")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Abbrechen")
        cancel.setObjectName("SecondaryButton")
        btns.addWidget(cancel)
        layout.addLayout(btns)
        cancel.clicked.connect(self.reject)

        # Start import one event-loop step later so this dialog is visible first;
        # without singleShot, child prompts can open too early
        QTimer.singleShot(0, self._interactive_import)

    _FILE_LABELS = {
        "raeume.json": "Räume",
        "lehrveranstaltungen.json": "LVAs",
        "termine.json": "Termine",
        "studienrichtungen.json": "Studienrichtungen",
        "freie_tage.json": "Freie Zeiträume",
    }

    @staticmethod
    def _merge_import_entry(file_name: str, existing: dict | None, incoming: dict) -> dict:
        return effective_import_entry(existing, incoming)

    def _build_import_summary(self) -> str:
        parts = []
        for fname, content in self.imported_data.items():
            schema = IMPORT_FILE_SCHEMAS.get(fname)
            if schema is None:
                continue
            incoming = payload_list(content, schema)
            label = self._FILE_LABELS.get(fname, fname)
            existing_map = self._existing_map(fname, schema)
            new_count = 0
            changed_count = 0
            identical_count = 0
            skipped_count = 0
            for item in incoming:
                if self._entry_reference_warnings(fname, item):
                    skipped_count += 1
                    continue
                item_id = get_entry_id(item, schema.id_field)
                existing = existing_map.get(item_id or "")
                merged = self._merge_import_entry(fname, existing, item)
                if existing is None:
                    new_count += 1
                elif existing == merged:
                    identical_count += 1
                else:
                    changed_count += 1
            parts.append(
                f"{label}: {len(incoming)} gesamt, {new_count} neu, "
                f"{changed_count} geändert, {identical_count} vorhanden, {skipped_count} übersprungen"
            )
        return " · ".join(parts) if parts else "Keine importierbaren Einträge erkannt."

    def _existing_map(self, fname: str, schema) -> dict[str, dict[str, Any]]:
        target = self.data_dir / fname
        if not target.exists():
            return {}
        try:
            raw = json.loads(target.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}
        return {
            entry_id: item
            for item in payload_list(raw, schema)
            if (entry_id := get_entry_id(item, schema.id_field)) is not None
        }

    def _incoming_ids(self, fname: str) -> set[str]:
        schema = IMPORT_FILE_SCHEMAS.get(fname)
        if schema is None:
            return set()
        return {
            entry_id
            for item in payload_list(self.imported_data.get(fname), schema)
            if (entry_id := get_entry_id(item, schema.id_field)) is not None
        }

    def _known_ids_after_import(self, fname: str) -> set[str]:
        schema = IMPORT_FILE_SCHEMAS.get(fname)
        if schema is None:
            return set()
        return set(self._existing_map(fname, schema).keys()) | self._incoming_ids(fname)

    @staticmethod
    def _default_ids(filename: str, root_key: str) -> set[str]:
        data = load_default_config(filename, {})
        items = data.get(root_key, []) if isinstance(data, dict) else []
        return {
            text
            for item in items
            if isinstance(item, dict)
            if (text := str(item.get("id") or "").strip())
        }

    def _reference_warnings(self) -> list[str]:
        warnings = []
        for fname, content in self.imported_data.items():
            schema = IMPORT_FILE_SCHEMAS.get(fname)
            if schema is None:
                continue
            for item in payload_list(content, schema):
                warnings.extend(self._entry_reference_warnings(fname, item))
        return warnings

    def _entry_reference_warnings(self, fname: str, item: dict[str, Any]) -> list[str]:
        warnings = []
        known_lvas = self._known_ids_after_import("lehrveranstaltungen.json")
        known_rooms = self._known_ids_after_import("raeume.json")
        known_studienrichtungen = self._known_ids_after_import("studienrichtungen.json")
        known_studiensemester = self._default_ids("studiensemester.json", "studiensemester")

        if fname == "termine.json":
            item_label = get_entry_id(item, "id") or str(item.get("name") or "Termin")
            lva_id = str(item.get("lva_id") or "").strip()
            if not lva_id:
                warnings.append(f"Termin {item_label}: keine LVA angegeben")
            elif lva_id not in known_lvas:
                warnings.append(f"Termin {item_label}: unbekannte LVA {lva_id}")
            room_id = str(item.get("raum_id") or "").strip()
            if room_id and room_id not in known_rooms:
                warnings.append(f"Termin {item_label}: unbekannter Raum {room_id}")
            for exception in item.get("serien_ausnahmen") or []:
                if not isinstance(exception, dict):
                    continue
                exception_room = str(exception.get("raum_id") or "").strip()
                if exception_room and exception_room not in known_rooms:
                    warnings.append(f"Termin {item_label}: Serien-Ausnahme mit unbekanntem Raum {exception_room}")

        if fname == "lehrveranstaltungen.json":
            item_label = get_entry_id(item, "id") or str(item.get("name") or "LVA")
            studienrichtung = str(item.get("studienrichtung") or "").strip()
            if studienrichtung and known_studienrichtungen and studienrichtung not in known_studienrichtungen:
                warnings.append(f"LVA {item_label}: unbekannte Studienrichtung {studienrichtung}")
            raw_studiensemester = item.get("studiensemester") or []
            studiensemester_values = raw_studiensemester if isinstance(raw_studiensemester, list) else [raw_studiensemester]
            unknown_studiensemester = [
                value
                for raw_value in studiensemester_values
                if (value := str(raw_value or "").strip()) and value not in known_studiensemester
            ]
            if unknown_studiensemester:
                shown = ", ".join(unknown_studiensemester[:6])
                if len(unknown_studiensemester) > 6:
                    shown += f", ... ({len(unknown_studiensemester)} insgesamt)"
                warnings.append(f"LVA {item_label}: unbekannte Studiensemester {shown}")
        return warnings

    def _confirm_reference_warnings(self) -> bool:
        warnings = self.reference_warnings or self._reference_warnings()
        self.reference_warnings = warnings
        if not warnings:
            return True
        shown = "\n".join(f"- {line}" for line in warnings[:12])
        if len(warnings) > 12:
            shown += f"\n- ... {len(warnings) - 12} weitere"
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Import prüfen")
        msg.setText("Der Import enthält Verweise auf Stammdaten, die nicht gefunden wurden.")
        msg.setInformativeText(
            f"{shown}\n\n"
            "Diese Einträge werden übersprungen. Importieren Sie zuerst die fehlenden Stammdaten, "
            "wenn diese Termine übernommen werden sollen."
        )
        cancel_btn = msg.addButton("Abbrechen", QMessageBox.RejectRole)
        continue_btn = msg.addButton("Gültige Einträge importieren", QMessageBox.AcceptRole)
        msg.setDefaultButton(cancel_btn)
        msg.exec()
        return msg.clickedButton() == continue_btn

    class _EntryMergePrompt(QDialog):
        """Decision dialog showing field-level differences for one entry, with import/ignore choices."""

        _FIELD_LABELS = {
            "id": "ID",
            "name": "Name",
            "typ": "Typ",
            "duration": "Dauer",
            "datum": "Datum",
            "datum_bis": "Datum bis",
            "periodizitaet": "Periodizität",
            "ausfall_daten": "Ausfalltermine",
            "serien_ausnahmen": "Serien-Ausnahmen",
            "von_datum": "Von",
            "bis_datum": "Bis",
            "gruppe": "Gruppe",
            "groesse": "Groesse",
            "start_zeit": "Startzeit",
            "end_zeit": "Endzeit",
            "raum_id": "Raum",
            "lva_id": "LVA-Nr.",
            "semester_id": "Semester",
            "anwesenheitspflicht": "Anwesenheitspflicht",
            "notiz": "Notiz",
            "beschreibung": "Beschreibung",
            "kapazitaet": "Kapazität",
            "gebaeude": "Gebäude",
            "vortragende": "Vortragende",
            "email": "E-Mail",
            "studienrichtung": "Studienrichtung",
            "studiensemester": "Studiensemester",
        }

        _FILE_FIELD_LABELS = {
            "termine.json": {
                "id": "Termin-ID",
                "name": "Bezeichnung",
                "datum": "Datum",
                "start_zeit": "Beginn",
                "duration": "Dauer",
                "lva_id": "LVA",
                "raum_id": "Raum",
                "semester_id": "Semester",
                "typ": "Typ",
                "gruppe": "Gruppe",
                "notiz": "Notiz",
                "periodizitaet": "Wiederholung",
                "datum_bis": "Wiederholung bis",
                "ausfall_daten": "Ausfalltermine",
                "serien_ausnahmen": "Serien-Ausnahmen",
                "zu_besprechen": "Zu besprechen",
                "besprechungshinweis": "Besprechungshinweis",
            },
            "raeume.json": {
                "id": "Raumnummer",
                "name": "Raum",
                "kapazitaet": "Kapazität",
                "gebaeude": "Gebäude",
            },
        }

        _FIELD_ORDER = {
            "termine.json": [
                "datum",
                "start_zeit",
                "duration",
                "lva_id",
                "typ",
                "raum_id",
                "gruppe",
                "semester_id",
                "name",
                "notiz",
                "zu_besprechen",
                "besprechungshinweis",
                "periodizitaet",
                "datum_bis",
                "ausfall_daten",
                "serien_ausnahmen",
                "id",
            ],
            "lehrveranstaltungen.json": [
                "id",
                "name",
                "vortragende",
                "studienrichtung",
                "studiensemester",
                "ects",
            ],
            "raeume.json": ["id", "name", "kapazitaet", "gebaeude"],
            "freie_tage.json": ["typ", "beschreibung", "von_datum", "bis_datum", "id"],
        }

        _OPTIONAL_EMPTY_FIELDS = {
            "termine.json": {
                "datum_bis",
                "periodizitaet",
                "ausfall_daten",
                "serien_ausnahmen",
                "notiz",
                "besprechungshinweis",
                "anwesenheitspflicht",
                "zu_besprechen",
            },
            "lehrveranstaltungen.json": {"ects", "vortragende"},
        }

        @classmethod
        def _humanize_key(cls, key: str, fname: str = "") -> str:
            return (
                cls._FILE_FIELD_LABELS.get(fname, {}).get(key)
                or cls._FIELD_LABELS.get(key)
                or key.replace("_", " ").strip().capitalize()
            )

        @classmethod
        def _file_label(cls, fname: str) -> str:
            return ImportDialog._FILE_LABELS.get(fname, fname.replace(".json", ""))

        @classmethod
        def _format_value(cls, value, field: str = "", fname: str = "") -> str:
            if value == '<missing>':
                return "(leer)"
            if value is None:
                return "(leer)"
            if isinstance(value, bool):
                return "Ja" if value else "Nein"
            if isinstance(value, dict):
                if field == "gruppe":
                    name = str(value.get("name", "") or "").strip()
                    size = str(value.get("groesse", "") or "").strip()
                    if name and size:
                        return f"{name} ({size} Personen)"
                    return name or (f"{size} Personen" if size else "(leer)")
                if field == "vortragende":
                    name = str(value.get("name", "") or "").strip()
                    email = str(value.get("email", "") or "").strip()
                    if name and email:
                        return f"{name} · {email}"
                    return name or email or "(leer)"
                parts = []
                for k in sorted(value.keys()):
                    parts.append(
                        f"{cls._humanize_key(str(k), fname)}: {cls._format_value(value[k], str(k), fname)}"
                    )
                return " | ".join(parts) if parts else "(leer)"
            if isinstance(value, list):
                if not value:
                    return "(leer)"
                return ", ".join(cls._format_value(v, field, fname) for v in value)

            display = str(value)
            if field == "duration" and display and not display.endswith(" min"):
                return f"{display} min"
            return display

        @classmethod
        def _is_empty_display_value(cls, value) -> bool:
            if value == '<missing>' or value is None:
                return True
            if isinstance(value, str):
                return value.strip() == ""
            if isinstance(value, bool):
                return not value
            if isinstance(value, list):
                return len(value) == 0
            if isinstance(value, dict):
                return all(cls._is_empty_display_value(v) for v in value.values())
            return False

        @classmethod
        def _ordered_keys(cls, data: dict, fname: str) -> list[str]:
            preferred = cls._FIELD_ORDER.get(fname, [])
            existing = [key for key in preferred if key in data]
            rest = sorted(key for key in data.keys() if key not in preferred)
            return existing + rest

        @classmethod
        def _build_diff_text(cls, diffs, fname: str = ""):
            if not diffs:
                return "Keine Unterschiede"

            blocks = []
            for field, old_value, new_value in diffs:
                blocks.append(
                    "\n".join([
                        f"{cls._humanize_key(str(field), fname)}",
                        f"Alt: {cls._format_value(old_value, str(field), fname)}",
                        f"Neu: {cls._format_value(new_value, str(field), fname)}",
                    ])
                )
            return "\n\n".join(blocks)

        @classmethod
        def _build_compact_entry_text(cls, new: dict, fname: str = "") -> str:
            lines = []
            optional_empty = cls._OPTIONAL_EMPTY_FIELDS.get(fname, set())
            for key in cls._ordered_keys(new, fname):
                value = new.get(key, "")
                if key in optional_empty and cls._is_empty_display_value(value):
                    continue
                if key.startswith("__"):
                    continue
                lines.append(f"{cls._humanize_key(str(key), fname)}: {cls._format_value(value, str(key), fname)}")
            lines = lines[:40]
            return "\n".join(lines)

        def __init__(self, parent, fname: str, new: dict, old):
            super().__init__(parent)
            self.choice = None
            self.setObjectName("ImportEntryMergePrompt")
            entry_id = new.get('id') or new.get('datum') or new.get('key') or new.get('name') or '-'
            file_label = self._file_label(fname)
            self.setWindowTitle(f"{file_label}: {entry_id}")
            self.resize(980, 620)
            self.setMinimumSize(860, 520)
            self.setModal(True)

            root = QVBoxLayout(self)
            root.setContentsMargins(16, 14, 16, 12)
            root.setSpacing(8)

            title = QLabel(f"{file_label}  —  {entry_id}")
            title.setObjectName("ImportTitle")
            root.addWidget(title)

            subtitle_text = (
                "Neuer Eintrag. Beim Importieren wird er hinzugefügt."
                if old is None
                else "Bestehender Eintrag. Beim Importieren werden die geänderten Felder aktualisiert."
            )
            subtitle = QLabel(subtitle_text)
            subtitle.setObjectName("ImportSubHeader")
            root.addWidget(subtitle)

            # left: field-level diff
            effective_new = ImportDialog._merge_import_entry(fname, old, new)
            keys = sorted(set((old or {}).keys()) | set(effective_new.keys()))
            diffs = [(k, (old or {}).get(k, '<missing>'), effective_new.get(k, '<missing>'))
                     for k in keys if (old or {}).get(k, '<missing>') != effective_new.get(k, '<missing>')]

            content_row = QHBoxLayout()
            content_row.setSpacing(10)

            left_card = QFrame(self)
            left_card.setObjectName("importCard")
            left_layout = QVBoxLayout(left_card)
            left_layout.setContentsMargins(10, 10, 10, 10)
            left_layout.setSpacing(6)
            left_lbl = QLabel("Importstatus" if old is None else "Was wird geändert?")
            left_lbl.setObjectName("ImportSubHeader")
            left_layout.addWidget(left_lbl)

            diff_view = QTextEdit(self)
            diff_view.setReadOnly(True)
            diff_view.setLineWrapMode(QTextEdit.WidgetWidth)
            if old is None:
                diff_view.setPlainText(
                    "Dieser Eintrag ist im aktuellen Projekt noch nicht vorhanden.\n\n"
                    "Beim Importieren wird er neu angelegt."
                )
            else:
                diff_view.setPlainText(self._build_diff_text(diffs, fname))
            diff_view.setObjectName("importPreview")
            left_layout.addWidget(diff_view)

            right_card = QFrame(self)
            right_card.setObjectName("importCard")
            right_layout = QVBoxLayout(right_card)
            right_layout.setContentsMargins(10, 10, 10, 10)
            right_layout.setSpacing(6)
            lbl = QLabel("Importierter Stand")
            lbl.setObjectName("ImportSubHeader")
            right_layout.addWidget(lbl)

            meta = QTextEdit(self)
            meta.setReadOnly(True)
            meta.setLineWrapMode(QTextEdit.WidgetWidth)
            meta.setObjectName("importPreview")
            meta.setPlainText(self._build_compact_entry_text(effective_new, fname))
            right_layout.addWidget(meta)

            content_row.addWidget(left_card, 3)
            content_row.addWidget(right_card, 2)
            root.addLayout(content_row, 1)

            h = QHBoxLayout()
            h.setSpacing(8)
            h.addStretch()
            primary_btn = None
            for label, obj_name, choice in [
                ("Importieren",        "PrimaryButton",   "import"),
                ("Ignorieren",         "SecondaryButton", "ignore"),
                ("Importieren (alle)", "SecondaryButton", "import_all"),
                ("Ignorieren (alle)",  "SecondaryButton", "ignore_all"),
            ]:
                btn = QPushButton(label)
                btn.setObjectName(obj_name)
                btn.clicked.connect(lambda _, c=choice: self._choose(c))
                h.addWidget(btn)
                if choice == "import":
                    primary_btn = btn
            root.addLayout(h)

            if primary_btn is not None:
                primary_btn.setDefault(True)
                primary_btn.setFocus()

        def _choose(self, c: str):
            self.choice = c
            self.accept()

    def _interactive_import(self):
        """Step through each changed entry in every imported file, prompt user, then write and close"""
        if not self._confirm_reference_warnings():
            self.reject()
            return

        for fname, content in self.imported_data.items():
            schema = IMPORT_FILE_SCHEMAS.get(fname)
            if schema is None:
                continue

            target = self.data_dir / fname

            existing_raw = None
            if target.exists():
                try:
                    existing_raw = json.loads(target.read_text(encoding='utf-8'))
                except Exception as exc:
                    QMessageBox.warning(self, "Import Fehler", f"{fname} konnte nicht gelesen werden: {exc}")
                    self.reject()
                    return

            # skip if file content is identical
            try:
                if existing_raw is not None and json.dumps(existing_raw, sort_keys=True) == json.dumps(content, sort_keys=True):
                    continue
            except Exception:
                pass


            incoming_list = payload_list(content, schema)
            existing_list = existing_raw.get(schema.list_key, []) if isinstance(existing_raw, dict) else []


            existing_map = {
                get_entry_id(e, schema.id_field): e
                for e in existing_list
                if get_entry_id(e, schema.id_field) is not None
            }

            import_all = False
            ignore_all = False
            counts = self.result_counts.setdefault(
                fname,
                {"new": 0, "changed": 0, "identical": 0, "ignored": 0, "skipped": 0},
            )

            for index, inc in enumerate(incoming_list):
                if index % 25 == 0:
                    QApplication.processEvents()

                eid = get_entry_id(inc, schema.id_field)
                ex = existing_map.get(eid) if eid else None
                effective_inc = self._merge_import_entry(fname, ex, inc)

                different = ex is None or ex != effective_inc

                if not different:
                    counts["identical"] += 1
                    continue

                if self._entry_reference_warnings(fname, effective_inc):
                    counts["skipped"] += 1
                    continue

                if import_all:
                    ch = 'import'
                elif ignore_all:
                    ch = 'ignore'
                elif ex is None:
                    ch = 'import'
                else:
                    prompt = ImportDialog._EntryMergePrompt(self, fname, effective_inc, ex)
                    prompt.exec()
                    ch = prompt.choice

                if ch == 'import_all':
                    import_all = True
                    ch = 'import'
                elif ch == 'ignore_all':
                    ignore_all = True
                    ch = 'ignore'

                if ch == 'import':
                    if eid and eid in existing_map:
                        existing_map[eid].clear()
                        existing_map[eid].update(effective_inc)
                        counts["changed"] += 1
                    else:
                        existing_list.append(effective_inc)
                        if eid:
                            existing_map[eid] = effective_inc
                        counts["new"] += 1
                else:
                    counts["ignored"] += 1

            # write back
            if not isinstance(existing_raw, dict):
                existing_raw = {}
            existing_raw[schema.list_key] = existing_list

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(".tmp")
                tmp.write_text(json.dumps(existing_raw, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
                tmp.replace(target)
            except Exception as exc:
                QMessageBox.warning(self, "Import Fehler", f"{fname} konnte nicht gespeichert werden: {exc}")
                self.reject()
                return

        self.accept()
