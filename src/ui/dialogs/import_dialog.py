from pathlib import Path
import json

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QWidget, QFrame,
    QMessageBox, QApplication,
)

from ...services.import_merge_service import IMPORT_FILE_SCHEMAS, get_entry_id, payload_list

class ImportDialog(QDialog):
    """Steps through every changed entry across all imported files and lets the user merge or ignore each."""

    def __init__(self, parent: QWidget, data_dir: Path, imported_data: dict, *, auto_import_new: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Import prüfen")
        self.setObjectName("importDialog")
        self.data_dir = Path(data_dir)
        self.imported_data = imported_data or {}
        self.auto_import_new = auto_import_new

        layout = QVBoxLayout(self)
        hdr = QLabel("Import: Sie werden nacheinander durch alle Änderungen geführt.")
        hdr.setObjectName("ImportHeader")
        layout.addWidget(hdr)

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
            "raeume.json": {
                "id": "Raumnummer",
                "name": "Raum",
                "kapazitaet": "Kapazität",
                "gebaeude": "Gebäude",
            },
        }

        @classmethod
        def _humanize_key(cls, key: str, fname: str = "") -> str:
            return (
                cls._FILE_FIELD_LABELS.get(fname, {}).get(key)
                or cls._FIELD_LABELS.get(key)
                or key.replace("_", " ").strip().capitalize()
            )

        @classmethod
        def _format_value(cls, value, field: str = "", fname: str = "") -> str:
            if value == '<missing>':
                return "(leer)"
            if value is None:
                return "(leer)"
            if isinstance(value, bool):
                return "Ja" if value else "Nein"
            if isinstance(value, dict):
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
            lines = [
                f"{cls._humanize_key(str(k), fname)}: {cls._format_value(new.get(k, ''), str(k), fname)}"
                for k in sorted(new.keys())
            ][:40]
            return "\n".join(lines)

        def __init__(self, parent, fname: str, new: dict, old):
            super().__init__(parent)
            self.choice = None
            self.setObjectName("ImportEntryMergePrompt")
            entry_id = new.get('id') or new.get('datum') or new.get('key') or new.get('name') or '-'
            self.setWindowTitle(f"{fname}: {entry_id}")
            self.resize(980, 620)
            self.setMinimumSize(860, 520)
            self.setModal(True)

            root = QVBoxLayout(self)
            root.setContentsMargins(16, 14, 16, 12)
            root.setSpacing(8)

            title = QLabel(f"{fname}  —  {entry_id}")
            title.setObjectName("ImportTitle")
            root.addWidget(title)

            subtitle = QLabel("Bitte prufen: bestehender Eintrag wird mit den neuen Werten verglichen.")
            subtitle.setObjectName("ImportSubHeader")
            root.addWidget(subtitle)

            # left: field-level diff
            keys = sorted(set((old or {}).keys()) | set(new.keys()))
            diffs = [(k, (old or {}).get(k, '<missing>'), new.get(k, '<missing>'))
                     for k in keys if (old or {}).get(k, '<missing>') != new.get(k, '<missing>')]

            content_row = QHBoxLayout()
            content_row.setSpacing(10)

            left_card = QFrame(self)
            left_card.setObjectName("importCard")
            left_layout = QVBoxLayout(left_card)
            left_layout.setContentsMargins(10, 10, 10, 10)
            left_layout.setSpacing(6)
            left_lbl = QLabel("Anderungen")
            left_lbl.setObjectName("ImportSubHeader")
            left_layout.addWidget(left_lbl)

            diff_view = QTextEdit(self)
            diff_view.setReadOnly(True)
            diff_view.setLineWrapMode(QTextEdit.NoWrap)
            diff_view.setPlainText(self._build_diff_text(diffs, fname))
            diff_view.setObjectName("importPreview")
            diff_view.setFont(QFont("Consolas"))
            left_layout.addWidget(diff_view)

            right_card = QFrame(self)
            right_card.setObjectName("importCard")
            right_layout = QVBoxLayout(right_card)
            right_layout.setContentsMargins(10, 10, 10, 10)
            right_layout.setSpacing(6)
            lbl = QLabel("Neu (Gesamt)")
            lbl.setObjectName("ImportSubHeader")
            right_layout.addWidget(lbl)

            meta = QTextEdit(self)
            meta.setReadOnly(True)
            meta.setLineWrapMode(QTextEdit.NoWrap)
            meta.setFont(QFont("Consolas"))
            meta.setObjectName("importPreview")
            meta.setPlainText(self._build_compact_entry_text(new, fname))
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

            for index, inc in enumerate(incoming_list):
                if index % 25 == 0:
                    QApplication.processEvents()

                eid = get_entry_id(inc, schema.id_field)
                ex = existing_map.get(eid) if eid else None

                different = ex is None or ex != inc

                if not different:
                    continue

                if import_all:
                    ch = 'import'
                elif ignore_all:
                    ch = 'ignore'
                elif ex is None and self.auto_import_new:
                    ch = 'import'
                else:
                    prompt = ImportDialog._EntryMergePrompt(self, fname, inc, ex)
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
                        existing_map[eid].update(inc)
                    else:
                        existing_list.append(inc)
                        if eid:
                            existing_map[eid] = inc

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
