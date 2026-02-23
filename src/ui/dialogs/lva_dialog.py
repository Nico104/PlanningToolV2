from typing import Optional
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox
)

from ...core.models import Semester, Raum, Lehrveranstaltung, Vortragende, Termin, Zeitfenster, Gruppe







class LVADialog(QDialog):
    def __init__(self, parent: QWidget, lva: Optional[Lehrveranstaltung] = None):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("LVA bearbeiten" if lva else "LVA hinzufügen")
        self.setModal(True)
        self._result: Optional[Lehrveranstaltung] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        self.id_le = QLineEdit(lva.id if lva else "")
        self.id_le.setObjectName("Field")
        self.name_le = QLineEdit(lva.name if lva else "")
        self.name_le.setObjectName("Field")
        self.vname_le = QLineEdit(lva.vortragende.name if lva else "")
        self.vname_le.setObjectName("Field")
        self.vmail_le = QLineEdit(lva.vortragende.email if lva else "")
        self.vmail_le.setObjectName("Field")

        self.typ_le = QLineEdit(", ".join(lva.typ) if lva else "VO")
        self.typ_le.setObjectName("Field")

        # Geplante Semester Auswahl (beliebig viele)
        import os, json
        from PySide6.QtWidgets import QComboBox, QPushButton, QHBoxLayout
        from ..components.widgets.chip_list_widget import ChipListWidget
        # Use workspace root for absolute path
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        semester_path = os.path.join(workspace_root, "data", "geplante_semester.json")
        try:
            with open(semester_path, encoding="utf-8") as f:
                semester_data = json.load(f)["geplante_semester"]
            print("DEBUG: Loaded semester_data:", semester_data)
        except Exception as e:
            print("DEBUG: Failed to load semester_data:", e)
            semester_data = []
        from ...core.models import GeplantesSemester
        self.sem_objects = [GeplantesSemester(
            id=s["id"],
            name=s["name"],
            notiz=s.get("notiz")
        ) for s in semester_data]

        # Use ChipListWidget for semester chips
        self.sem_chip_items = []
        if lva and getattr(lva, "geplante_semester", None):
            for sid in lva.geplante_semester:
                sem = next((sem for sem in self.sem_objects if sem.id == sid), None)
                if sem:
                    display = sem.name  # Only show name
                    self.sem_chip_items.append(display)
                else:
                    self.sem_chip_items.append(sid)
        self.sem_list = ChipListWidget(self.sem_chip_items)
        def refresh_sem_cb():
            self.sem_cb.clear()
            chip_names = set(self.sem_list.items)
            for sem in self.sem_objects:
                # Only show if not already in chips (by name only)
                if sem.name not in chip_names:
                    if sem.notiz:
                        display_full = f"{sem.name} - {sem.notiz}"
                    else:
                        display_full = sem.name
                    self.sem_cb.addItem(display_full, sem.id)
        def on_chip_deleted(idx):
            self.sem_list.removeItem(idx)
            refresh_sem_cb()
        self.sem_list.chipDeleted.connect(on_chip_deleted)

        sem_add_layout = QHBoxLayout()
        from ..components.widgets.tight_combobox import TightComboBox
        self.sem_cb = TightComboBox(self)
        self.sem_cb.setObjectName("HeaderCombo")
        self.sem_cb.setMinimumWidth(160)
        refresh_sem_cb()
        self.sem_cb.setMaxVisibleItems(len(self.sem_objects))
        self.sem_cb.view().setMinimumHeight(32 * len(self.sem_objects))
        self.sem_cb.view().setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.btn_add_sem = QPushButton("Hinzufügen")
        sem_add_layout.addWidget(self.sem_cb)
        sem_add_layout.addWidget(self.btn_add_sem)

        def add_sem():
            sid = self.sem_cb.currentData()
            idx = self.sem_cb.currentIndex()
            if sid is None or not isinstance(sid, str) or idx < 0:
                return
            # Always use only the name part for chips
            display_full = self.sem_cb.currentText()
            name = display_full.split(' - ')[0]
            # Avoid duplicates
            for chip in self.sem_list.items:
                if name == chip:
                    return
            self.sem_list.addItem(name)
            refresh_sem_cb()
        self.btn_add_sem.clicked.connect(add_sem)

        form.addRow("LVA-ID:", self.id_le)
        form.addRow("Name:", self.name_le)
        form.addRow("Vortragende Name:", self.vname_le)
        form.addRow("Vortragende E-Mail:", self.vmail_le)
        form.addRow("Erlaubte Typen (Komma):", self.typ_le)

        form.addRow("Geplante Semester:", self.sem_list)
        form.addRow("Semester hinzufügen/entfernen:", sem_add_layout)

        # ...existing code...

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("DialogButtons")
        ok_btn = bb.button(QDialogButtonBox.Ok)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setObjectName("PrimaryButton")
        if cancel_btn:
            cancel_btn.setObjectName("SecondaryButton")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _accept(self):
        cid = self.id_le.text().strip()
        name = self.name_le.text().strip()
        vname = self.vname_le.text().strip()
        if not cid or not name or not vname:
            QMessageBox.warning(self, "Fehler", "LVA-ID, Name und Vortragende Name sind Pflicht.")
            return
        typ = [t.strip().upper() for t in self.typ_le.text().split(",") if t.strip()]
        geplante_semester = []
        # Map chip names back to IDs
        for chip_name in self.sem_list.items:
            # Find the semester object by name
            sem = next((s for s in self.sem_objects if s.name == chip_name), None)
            if sem:
                geplante_semester.append(sem.id)
        self._result = Lehrveranstaltung(
            id=cid,
            name=name,
            vortragende=Vortragende(name=vname, email=self.vmail_le.text().strip()),
            typ=typ,
            geplante_semester=geplante_semester
        )
        self.accept()

    @property
    def result(self) -> Optional[Lehrveranstaltung]:
        return self._result