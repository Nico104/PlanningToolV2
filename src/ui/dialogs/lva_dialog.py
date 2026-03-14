from typing import Optional, Sequence

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox,
    QPushButton, QHBoxLayout,
)

from ...core.models import GeplantesSemester, Lehrveranstaltung, Vortragende
from ..components.widgets.chip_list_widget import ChipListWidget
from ..components.widgets.tight_combobox import TightComboBox

class LVADialog(QDialog):
    """Dialog for creating or editing a LVA
    """
    def __init__(
        self,
        parent: QWidget,
        lva: Optional[Lehrveranstaltung] = None,
        geplante_semester: Sequence[GeplantesSemester] = (),
        fachrichtungen: Sequence[dict] = (),
    ):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("LVA bearbeiten" if lva else "LVA hinzufügen")
        self.setModal(True)
        self._result: Optional[Lehrveranstaltung] = None
        self.sem_objects = list(geplante_semester)
        self._fachrichtung_value = getattr(lva, "fachrichtung", "ETIT") if lva else "ETIT"

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

        self.fach_cb = TightComboBox(self)
        self.fach_cb.setObjectName("HeaderCombo")
        self.fach_cb.setMinimumWidth(160)
        seen_ids = set()
        for f in fachrichtungen:
            if not isinstance(f, dict):
                continue
            fid = str(f.get("id", "")).strip()
            fname = str(f.get("name", "")).strip()
            if not fid or fid in seen_ids:
                continue
            seen_ids.add(fid)
            label = f"{fid} - {fname}" if fname else fid
            self.fach_cb.addItem(label, fid)

        if self._fachrichtung_value and self.fach_cb.findData(self._fachrichtung_value) < 0:
            self.fach_cb.addItem(self._fachrichtung_value, self._fachrichtung_value)

        idx_fach = self.fach_cb.findData(self._fachrichtung_value)
        if idx_fach >= 0:
            self.fach_cb.setCurrentIndex(idx_fach)
        elif self.fach_cb.count() > 0:
            self.fach_cb.setCurrentIndex(0)

        # Use ChipListWidget for semester chips
        self.sem_chip_items = []
        if lva and getattr(lva, "geplante_semester", None):
            for sid in lva.geplante_semester:
                sid = str(sid).strip()
                if not sid:
                    continue
                sem = next((sem for sem in self.sem_objects if sem.id == sid), None)
                if sem:
                    display = sem.name 
                    display = str(display).strip()
                    if display and display not in self.sem_chip_items:
                        self.sem_chip_items.append(display)
                else:
                    if sid not in self.sem_chip_items:
                        self.sem_chip_items.append(sid)
        self.sem_list = ChipListWidget(self.sem_chip_items)
        def refresh_sem_cb():
            self.sem_cb.clear()
            chip_names = set(self.sem_list.items)
            for sem in self.sem_objects:
                
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
        form.addRow("Fachrichtung:", self.fach_cb)
        form.addRow("Erlaubte Typen (Komma):", self.typ_le)

        form.addRow("Geplante Semester:", self.sem_list)
        form.addRow("Semester hinzufügen/entfernen:", sem_add_layout)

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
        selected_fach = self.fach_cb.currentData()
        if selected_fach is None or not str(selected_fach).strip():
            QMessageBox.warning(self, "Fehler", "Fachrichtung ist Pflicht.")
            return
        typ = [t.strip().upper() for t in self.typ_le.text().split(",") if t.strip()]
        geplante_semester = []
        # Map chip names back to IDs
        for chip_name in self.sem_list.items:
            chip_name = str(chip_name).strip()
            if not chip_name:
                continue
            # Find the semester object by name
            sem = next((s for s in self.sem_objects if s.name == chip_name), None)
            if sem and sem.id not in geplante_semester:
                geplante_semester.append(sem.id)
        self._result = Lehrveranstaltung(
            id=cid,
            name=name,
            vortragende=Vortragende(name=vname, email=self.vmail_le.text().strip()),
            typ=typ,
            geplante_semester=geplante_semester,
            fachrichtung=str(selected_fach).strip(),
        )
        self.accept()

    @property
    def result(self) -> Optional[Lehrveranstaltung]:
        return self._result