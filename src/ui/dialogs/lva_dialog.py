from typing import Optional, Sequence

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QFrame,
)

from ...core.models import Studiensemester, Lehrveranstaltung, Vortragende
from ..components.widgets.chip_list_widget import ChipListWidget
from ..components.widgets.tight_combobox import TightComboBox


class LVADialog(QDialog):
    """Dialog for creating or editing a LVA"""

    def __init__(
        self,
        parent: QWidget,
        lva: Optional[Lehrveranstaltung] = None,
        studiensemester: Sequence[Studiensemester] = (),
        studienrichtungen: Sequence[dict] = (),
    ):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("LVA bearbeiten" if lva else "LVA hinzufügen")
        self.setModal(True)
        self._result: Optional[Lehrveranstaltung] = None
        self.sem_objects = list(studiensemester)
        self._studienrichtung_value = getattr(lva, "studienrichtung", "ETIT") if lva else "ETIT"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(12)
        self.setMinimumWidth(560)

        title = QLabel("Lehrveranstaltung", self)
        title.setObjectName("DialogTitle")
        lay.addWidget(title)
        subtitle = QLabel(
            "Stammdaten, Vortragende und Studiensemester-Zuordnung einer LVA erfassen.", self
        )
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.id_le = QLineEdit(lva.id if lva else "")
        self.id_le.setObjectName("Field")
        self.name_le = QLineEdit(lva.name if lva else "")
        self.name_le.setObjectName("Field")
        self.ects_le = QLineEdit(getattr(lva, "ects", "") if lva else "")
        self.ects_le.setObjectName("Field")
        self.vname_le = QLineEdit(lva.vortragende.name if lva else "")
        self.vname_le.setObjectName("Field")
        self.vmail_le = QLineEdit(lva.vortragende.email if lva else "")
        self.vmail_le.setObjectName("Field")

        self.studienrichtung_cb = TightComboBox(self)
        self.studienrichtung_cb.setObjectName("HeaderCombo")
        self.studienrichtung_cb.setMinimumWidth(160)
        seen_ids = set()
        for f in studienrichtungen:
            if not isinstance(f, dict):
                continue
            fid = str(f.get("id", "")).strip()
            fname = str(f.get("name", "")).strip()
            if not fid or fid in seen_ids:
                continue
            seen_ids.add(fid)
            label = f"{fid} - {fname}" if fname else fid
            self.studienrichtung_cb.addItem(label, fid)

        if (
            self._studienrichtung_value
            and self.studienrichtung_cb.findData(self._studienrichtung_value) < 0
        ):
            self.studienrichtung_cb.addItem(
                self._studienrichtung_value, self._studienrichtung_value
            )

        idx_studienrichtung = self.studienrichtung_cb.findData(self._studienrichtung_value)
        if idx_studienrichtung >= 0:
            self.studienrichtung_cb.setCurrentIndex(idx_studienrichtung)
        elif self.studienrichtung_cb.count() > 0:
            self.studienrichtung_cb.setCurrentIndex(0)

        # Use ChipListWidget for semester chips
        self.sem_chip_items = []
        if lva and getattr(lva, "studiensemester", None):
            for sid in lva.studiensemester:
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
        self.btn_add_sem.setObjectName("SecondaryButton")
        sem_add_layout.addWidget(self.sem_cb)
        sem_add_layout.addWidget(self.btn_add_sem)

        def add_sem():
            sid = self.sem_cb.currentData()
            idx = self.sem_cb.currentIndex()
            if sid is None or not isinstance(sid, str) or idx < 0:
                return
            # Always use only the name part for chips
            display_full = self.sem_cb.currentText()
            name = display_full.split(" - ")[0]
            # Avoid duplicates
            for chip in self.sem_list.items:
                if name == chip:
                    return
            self.sem_list.addItem(name)
            refresh_sem_cb()

        self.btn_add_sem.clicked.connect(add_sem)

        form.addRow("LVA-Nr.:", self.id_le)
        form.addRow("Name:", self.name_le)
        form.addRow("ECTS:", self.ects_le)
        form.addRow("Vortragende Name:", self.vname_le)
        form.addRow("Vortragende E-Mail:", self.vmail_le)
        form.addRow("Studienrichtung:", self.studienrichtung_cb)

        form.addRow("Studiensemester:", self.sem_list)
        form.addRow("Studiensemester hinzufügen:", sem_add_layout)
        lay.addWidget(self._section("LVA-Daten", form))

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("DialogButtons")
        ok_btn = bb.button(QDialogButtonBox.Ok)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setText("Speichern")
            ok_btn.setObjectName("PrimaryButton")
        if cancel_btn:
            cancel_btn.setText("Abbrechen")
            cancel_btn.setObjectName("SecondaryButton")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _section(self, title: str, content_layout: QFormLayout) -> QFrame:
        section = QFrame(self)
        section.setObjectName("DialogSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        label = QLabel(title, section)
        label.setObjectName("DialogSectionTitle")
        layout.addWidget(label)
        layout.addLayout(content_layout)
        return section

    def _accept(self):
        cid = self.id_le.text().strip()
        name = self.name_le.text().strip()
        vname = self.vname_le.text().strip()
        if not cid or not name:
            QMessageBox.warning(self, "Fehler", "LVA-Nr. und Name sind Pflicht.")
            return
        selected_studienrichtung = self.studienrichtung_cb.currentData()
        if selected_studienrichtung is None or not str(selected_studienrichtung).strip():
            QMessageBox.warning(self, "Fehler", "Studienrichtung ist Pflicht.")
            return
        studiensemester = []
        # Map chip names back to IDs
        for chip_name in self.sem_list.items:
            chip_name = str(chip_name).strip()
            if not chip_name:
                continue
            # Find the semester object by name
            sem = next((s for s in self.sem_objects if s.name == chip_name), None)
            if sem and sem.id not in studiensemester:
                studiensemester.append(sem.id)
        self._result = Lehrveranstaltung(
            id=cid,
            name=name,
            vortragende=Vortragende(name=vname, email=self.vmail_le.text().strip()),
            studiensemester=studiensemester,
            studienrichtung=str(selected_studienrichtung).strip(),
            ects=self.ects_le.text().strip(),
        )
        self.accept()

    @property
    def result(self) -> Optional[Lehrveranstaltung]:
        return self._result
