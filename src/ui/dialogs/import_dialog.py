from pathlib import Path
import json

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QWidget
)

#TODO - Importlogik überarbeitung, alle files zugelassen?

class ImportDialog(QDialog):
    """Steps through every changed entry across all imported files and lets the user merge or ignore each."""

    # Maps filename → (list_key, id_field).
    # list_key=None means the file content is a top-level list (no wrapper dict).
    _FILE_SCHEMAS = {
        "termine.json":             ("termine",             "id"),
        "raeume.json":              ("raeume",              "id"),
        "lehrveranstaltungen.json": ("lehrveranstaltungen", "id"),
        "semester.json":            ("semester",            "id"),
        "fachrichtungen.json":      ("fachrichtungen",      "id"),
        "freie_tage.json":          ("freie_tage",          "id"),
        "konflikte.json":           (None,                  "key"),
    }

    @staticmethod
    def _get_entry_id(entry: dict, id_field):
        """Return the stable identifier for an imported entry."""
        v = entry.get(id_field)
        if v is not None:
            return str(v)
        return None

    def __init__(self, parent: QWidget, data_dir: Path, imported_data: dict):
        super().__init__(parent)
        self.setWindowTitle("Import prüfen")
        self.setObjectName("importDialog")
        self.data_dir = Path(data_dir)
        self.imported_data = imported_data or {}

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

        def __init__(self, parent, fname: str, new: dict, old):
            super().__init__(parent)
            self.choice = None
            entry_id = new.get('id') or new.get('datum') or new.get('key') or new.get('name') or '-'
            self.setWindowTitle(f"{fname}: {entry_id}")
            self.setMinimumSize(680, 360)
            root = QVBoxLayout(self)
            title = QLabel(f"{fname}  —  {entry_id}")
            title.setObjectName("ImportTitle")
            root.addWidget(title)

            main_area = QHBoxLayout()

            # left: field-level diff
            keys = sorted(set((old or {}).keys()) | set(new.keys()))
            diffs = [(k, (old or {}).get(k, '<missing>'), new.get(k, '<missing>'))
                     for k in keys if (old or {}).get(k, '<missing>') != new.get(k, '<missing>')]

            diff_view = QTextEdit(self)
            diff_view.setReadOnly(True)
            diff_view.setPlainText(
                '\n'.join(f"{k}:\n  - alt: {ov}\n  + neu: {nv}\n" for k, ov, nv in diffs)
                if diffs else "Keine Unterschiede"
            )
            diff_view.setObjectName("importPreview")
            diff_view.setFont(QFont("Consolas"))
            diff_view.setMinimumWidth(420)

            left = QVBoxLayout()
            left.addWidget(diff_view)
            main_area.addLayout(left, 3)

            # right: full new entry for quick reference
            right = QVBoxLayout()
            lbl = QLabel("Neu (Gesamt)")
            lbl.setObjectName("ImportSubHeader")
            right.addWidget(lbl)
            meta = QLabel('\n'.join([f"{k}: {new.get(k, '')}" for k in sorted(new.keys())][:40]))
            meta.setWordWrap(True)
            meta.setFont(QFont("Consolas"))
            meta.setObjectName("ImportDiff")
            right.addWidget(meta)
            right.addStretch()
            main_area.addLayout(right, 2)

            root.addLayout(main_area)

            h = QHBoxLayout()
            h.addStretch()
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
            root.addLayout(h)

        def _choose(self, c: str):
            self.choice = c
            self.accept()

    def _interactive_import(self):
        """Step through each changed entry in every imported file, prompt user, then write and close"""
        for fname, content in self.imported_data.items():
            if fname not in ImportDialog._FILE_SCHEMAS:
                continue

            list_key, id_field = ImportDialog._FILE_SCHEMAS[fname]
            target = self.data_dir / fname

            existing_raw = None
            if target.exists():
                try:
                    existing_raw = json.loads(target.read_text(encoding='utf-8'))
                except Exception:
                    pass

            # skip if file content is identical
            try:
                if existing_raw is not None and json.dumps(existing_raw, sort_keys=True) == json.dumps(content, sort_keys=True):
                    continue
            except Exception:
                pass


            if list_key is None:
                incoming_list = content if isinstance(content, list) else []
                existing_list = existing_raw if isinstance(existing_raw, list) else []
            else:
                incoming_list = content.get(list_key, []) if isinstance(content, dict) else []
                existing_list = existing_raw.get(list_key, []) if isinstance(existing_raw, dict) else []


            existing_map = {
                ImportDialog._get_entry_id(e, id_field): e
                for e in existing_list
                if ImportDialog._get_entry_id(e, id_field) is not None
            }

            import_all = False
            ignore_all = False

            for inc in incoming_list:
                eid = ImportDialog._get_entry_id(inc, id_field)
                ex = existing_map.get(eid) if eid else None

                try:
                    different = ex is None or json.dumps(ex, sort_keys=True) != json.dumps(inc, sort_keys=True)
                except Exception:
                    different = True
                if not different:
                    continue

                if import_all:
                    ch = 'import'
                elif ignore_all:
                    ch = 'ignore'
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
            if list_key is None:
                out = existing_list
            else:
                if not isinstance(existing_raw, dict):
                    existing_raw = {}
                existing_raw[list_key] = existing_list
                out = existing_raw

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
            except Exception:
                pass

        self.accept()
