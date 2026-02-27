from pathlib import Path
import json

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox, QWidget
)


class ImportDialog(QDialog):
    """Interactive importer: prompt only for changed files and Termine.

    Shows a small prompt per changed file and per changed Termin in `termine.json`.
    After user decisions, writes selected changes into the `data` folder and closes.
    """

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

        # Run interactive import after the dialog is shown so prompts are visible/modal
        QTimer.singleShot(0, self._interactive_import)

    class _FileChangePrompt(QDialog):
        def __init__(self, parent, fname: str, new, old):
            super().__init__(parent)
            self.choice = None
            self.setWindowTitle(f"Änderung: {fname}")
            self.setMinimumSize(640, 300)
            root = QVBoxLayout(self)

            title = QLabel(f"Datei: {fname}")
            title.setObjectName("ImportTitle")
            root.addWidget(title)

            content_area = QHBoxLayout()

            # left: preview
            te = QTextEdit(self)
            te.setReadOnly(True)
            old_text = json.dumps(old, ensure_ascii=False, indent=2) if old is not None else "<nicht vorhanden>"
            new_text = json.dumps(new, ensure_ascii=False, indent=2)
            te.setPlainText(f"--- Vorhanden ---\n{old_text}\n\n--- Import ---\n{new_text}")
            te.setObjectName("importPreview")
            from PySide6.QtGui import QFont
            te.setFont(QFont("Consolas"))
            te.setMinimumWidth(380)
            content_area.addWidget(te, 3)

            # right: concise diff list
            right = QVBoxLayout()
            info = QLabel("Unterschiede:")
            info.setObjectName("ImportSubHeader")
            right.addWidget(info)
            diff_label = QLabel('\n'.join([l for l in (json.dumps(new, ensure_ascii=False, indent=2).splitlines()[:30])]))
            diff_label.setWordWrap(True)
            diff_label.setObjectName("ImportDiff")
            from PySide6.QtGui import QFont
            diff_label.setFont(QFont("Consolas"))
            right.addWidget(diff_label)
            right.addStretch()
            content_area.addLayout(right, 2)

            root.addLayout(content_area)

            h = QHBoxLayout()
            h.addStretch()
            btn_import = QPushButton("Importieren")
            btn_import.setObjectName("PrimaryButton")
            btn_ignore = QPushButton("Ignorieren")
            btn_ignore.setObjectName("SecondaryButton")
            btn_import_all = QPushButton("Importieren (alle)")
            btn_import_all.setObjectName("SecondaryButton")
            btn_ignore_all = QPushButton("Ignorieren (alle)")
            btn_ignore_all.setObjectName("SecondaryButton")
            h.addWidget(btn_import)
            h.addWidget(btn_ignore)
            h.addWidget(btn_import_all)
            h.addWidget(btn_ignore_all)
            root.addLayout(h)

            btn_import.clicked.connect(lambda: self._choose('import'))
            btn_ignore.clicked.connect(lambda: self._choose('ignore'))
            btn_import_all.clicked.connect(lambda: self._choose('import_all'))
            btn_ignore_all.clicked.connect(lambda: self._choose('ignore_all'))

        def _choose(self, c: str):
            self.choice = c
            self.accept()

    class _TerminMergePrompt(QDialog):
        def __init__(self, parent, new: dict, old: dict):
            super().__init__(parent)
            self.choice = None
            self.setWindowTitle("Termin prüfen")
            self.setMinimumSize(680, 360)
            root = QVBoxLayout(self)
            title = QLabel(f"Termin: {new.get('id','-')} — {new.get('name','')}")
            title.setObjectName("ImportTitle")
            root.addWidget(title)

            # two column: left = field diff list, right = preview of selected field details
            main_area = QHBoxLayout()

            # left: difference list
            left = QVBoxLayout()
            keys = sorted(set((old or {}).keys()) | set((new or {}).keys()))
            diffs = []
            for k in keys:
                ov = (old or {}).get(k, '<missing>')
                nv = (new or {}).get(k, '<missing>')
                if ov != nv:
                    diffs.append((k, ov, nv))

            list_widget = QTextEdit(self)
            list_widget.setReadOnly(True)
            if diffs:
                lines = []
                for k, ov, nv in diffs:
                    lines.append(f"{k}:\n  - alt: {ov}\n  + neu: {nv}\n")
                list_widget.setPlainText('\n'.join(lines))
            else:
                list_widget.setPlainText("Keine Unterschiede")
            list_widget.setObjectName("importPreview")
            from PySide6.QtGui import QFont
            list_widget.setFont(QFont("Consolas"))
            list_widget.setMinimumWidth(420)
            left.addWidget(list_widget)
            main_area.addLayout(left, 3)

            # right: metadata / quick info
            right = QVBoxLayout()
            info = QLabel("Schnellansicht")
            info.setObjectName("ImportSubHeader")
            right.addWidget(info)
            meta = QLabel('\n'.join([f"{k}: {str((new or {}).get(k,''))}" for k in sorted((new or {}).keys())][:40]))
            meta.setWordWrap(True)
            from PySide6.QtGui import QFont
            meta.setFont(QFont("Consolas"))
            meta.setObjectName("ImportDiff")
            right.addWidget(meta)
            right.addStretch()
            main_area.addLayout(right, 2)

            root.addLayout(main_area)

            h = QHBoxLayout()
            h.addStretch()
            btn_import = QPushButton("Importieren")
            btn_import.setObjectName("PrimaryButton")
            btn_ignore = QPushButton("Ignorieren")
            btn_ignore.setObjectName("SecondaryButton")
            btn_import_all = QPushButton("Importieren (alle)")
            btn_import_all.setObjectName("SecondaryButton")
            btn_ignore_all = QPushButton("Ignorieren (alle)")
            btn_ignore_all.setObjectName("SecondaryButton")
            h.addWidget(btn_import)
            h.addWidget(btn_ignore)
            h.addWidget(btn_import_all)
            h.addWidget(btn_ignore_all)
            root.addLayout(h)

            btn_import.clicked.connect(lambda: self._choose('import'))
            btn_ignore.clicked.connect(lambda: self._choose('ignore'))
            btn_import_all.clicked.connect(lambda: self._choose('import_all'))
            btn_ignore_all.clicked.connect(lambda: self._choose('ignore_all'))

        def _choose(self, c: str):
            self.choice = c
            self.accept()

    def _interactive_import(self):
        """Run interactive prompts for each changed file/Termin and write approved changes.

        This method does not show a success message itself; the main window handles final confirmation.
        """
        written = []
        errors = []

        import_all_files = False
        ignore_all_files = False

        for fname, content in self.imported_data.items():
            target = self.data_dir / fname
            existing = None
            if target.exists():
                try:
                    existing = json.loads(target.read_text(encoding='utf-8'))
                except Exception:
                    existing = None

            # if identical, skip
            try:
                if existing is not None and json.dumps(existing, sort_keys=True) == json.dumps(content, sort_keys=True):
                    continue
            except Exception:
                pass

            # termine.json => per-termin prompts
            if fname == 'termine.json' and isinstance(content, dict):
                incoming = content.get('termine', [])
                existing = existing or {'termine': []}
                existing_map = {str(t.get('id')): t for t in existing.get('termine', []) if t.get('id') is not None}
                import_all = False
                ignore_all = False
                for inc in incoming:
                    tid = str(inc.get('id',''))
                    ex = existing_map.get(tid)
                    try:
                        different = True if ex is None else (json.dumps(ex, sort_keys=True) != json.dumps(inc, sort_keys=True))
                    except Exception:
                        different = True
                    if not different:
                        continue

                    if import_all:
                        ch = 'import'
                    elif ignore_all:
                        ch = 'ignore'
                    else:
                        prompt = ImportDialog._TerminMergePrompt(self, inc, ex)
                        prompt.exec()
                        ch = prompt.choice

                    if ch == 'import_all':
                        import_all = True
                        ch = 'import'
                    elif ch == 'ignore_all':
                        ignore_all = True
                        ch = 'ignore'

                    if ch == 'import':
                        if tid in existing_map:
                            existing_map[tid].clear()
                            existing_map[tid].update(inc)
                        else:
                            existing.get('termine', []).append(inc)
                    # ignore -> do nothing

                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
                    written.append(fname)
                except Exception as e:
                    errors.append(f"{fname}: {e}")

                continue

            # other files => show a file change prompt
            if import_all_files:
                do_import = True
            elif ignore_all_files:
                do_import = False
            else:
                prompt = ImportDialog._FileChangePrompt(self, fname, content, existing)
                prompt.exec()
                choice = prompt.choice
                if choice == 'import_all':
                    import_all_files = True
                    do_import = True
                elif choice == 'ignore_all':
                    ignore_all_files = True
                    do_import = False
                else:
                    do_import = (choice == 'import')

            if do_import:
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(content, (dict, list)):
                        target.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
                    else:
                        target.write_text(str(content), encoding='utf-8')
                    written.append(fname)
                except Exception as e:
                    errors.append(f"{fname}: {e}")

        # finished; just close (main window shows final message)
        self.accept()
