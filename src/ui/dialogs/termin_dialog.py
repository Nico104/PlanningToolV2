from datetime import date, time
from typing import List, Optional, Dict

from PySide6.QtCore import QTime, QDate, Qt, QEvent, QTimer, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox,
    QComboBox, QDateEdit, QTimeEdit, QCheckBox, QSpinBox, QTextEdit
)
from PySide6.QtGui import QIcon

from ...core.models import Termin, Gruppe, Lehrveranstaltung, Semester, Raum
from ..utils.datetime_utils import date_to_qdate, qdate_to_date

from ..components.widgets.tight_combobox import TightComboBox

class TerminDialog(QDialog):
    def __init__(self, parent: QWidget, *,
                 lvas: List[Lehrveranstaltung],
                 semester: List[Semester],
                 raeume: List[Raum],
                 termin: Optional[Termin] = None,
                 settings: Optional[Dict] = None,
                 new_id = None,
                 ):
        super().__init__(parent)
        self.new_id = new_id
        self.termin = termin  # Store for access in other methods
        self.setObjectName("AppDialog")
        self.setModal(True)
        self.settings = settings or {}

        # Erst die Felder initialisieren, dann die Logik:
        self.name_le = QLineEdit(termin.name if (termin and hasattr(termin, 'name')) else "")
        self.name_le.setObjectName("Field")
        self.grp_name = QLineEdit((termin.gruppe.name if (termin and termin.gruppe) else ""))
        self.grp_size = QSpinBox()
        self.grp_size.setRange(0, 2000)
        self.grp_size.setValue((termin.gruppe.groesse if (termin and termin.gruppe) else 0))

        def _sync_group_fields():
            name = self.grp_name.text().strip()
            if name:
                self.grp_size.setEnabled(True)
            else:
                self.grp_size.setEnabled(False)
                self.grp_size.setValue(0)

        self.grp_name.textChanged.connect(lambda *_: _sync_group_fields())
        _sync_group_fields()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        self.setMinimumWidth(400)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(form)

        
        
        self.setWindowTitle("Termin bearbeiten" if termin else "Termin hinzufügen")
        self._result: Optional[Termin] = None


        self.lva_cb = TightComboBox()
        for l in lvas:
            self.lva_cb.addItem(f"{l.id} – {l.name}", l.id)

        # Semester ComboBox
        self.semester_cb = TightComboBox()
        for s in semester:
            self.semester_cb.addItem(f"{s.name}", s.id)


        self.typ_le = QLineEdit(termin.typ if termin else "VO")
        
        self.date_de = QDateEdit()
        self.date_de.setCalendarPopup(True)

        # Sentinel for unassigned date
        self._unassigned_qdate = QDate(2026, 1, 1)
        self.date_de.setMinimumDate(self._unassigned_qdate)
        self.date_de.setSpecialValueText("Kein Datum zugewiesen")
        self.date_de.setDate(self._unassigned_qdate)

        # Install event filter to detect when calendar popup opens
        self._calendar_shown = False
        self.date_de.installEventFilter(self)

        self.time_from = QTimeEdit()

        self.raum_cb = TightComboBox()
        for r in raeume:
            self.raum_cb.addItem(f"{r.id} – {r.name}", r.id)

        self.grp_name = QLineEdit((termin.gruppe.name if (termin and termin.gruppe) else ""))
        self.grp_size = QSpinBox()
        self.grp_size.setRange(0, 2000)
        self.grp_size.setValue((termin.gruppe.groesse if (termin and termin.gruppe) else 0))

        self.duration_sb = QSpinBox()
        self.duration_sb.setRange(0, 1000)
        self.duration_sb.setSingleStep(int(self.settings.get("duration_step_minutes", 15)))
        self.duration_sb.setValue(termin.duration if termin else 0)
        self.duration_sb.setSuffix(" min")

        from src.ui.components.widgets.tick_checkbox import TickCheckBox
        self.ap_cb = TickCheckBox("Anwesenheitspflicht")
        self.ap_cb.setChecked(bool(termin.anwesenheitspflicht) if termin else False)

        self.note_te = QTextEdit()
        self.note_te.setFixedHeight(60)
        self.note_te.setPlainText(termin.notiz if termin else "")

        if termin:
            # Set date - keep unassigned if it was unassigned
            if termin and termin.datum:
                self.date_de.setDate(date_to_qdate(termin.datum))
            else:
                # Keep as unassigned
                self.date_de.setDate(self._unassigned_qdate)

            # Set start time
            if termin.start_zeit:
                self.time_from.setTime(QTime(termin.start_zeit.hour, termin.start_zeit.minute))
            else:
                # Default start time
                self.time_from.setTime(QTime(8, 0))

            self._set_cb(self.lva_cb, termin.lva_id)
            self._set_cb(self.raum_cb, termin.raum_id)
            # Set semester combobox if semester_id is present
            if hasattr(termin, 'semester_id'):
                self._set_cb(self.semester_cb, getattr(termin, 'semester_id', None))
        else:
            # New termin: start with today
            today = date.today()
            self.date_de.setDate(date_to_qdate(today))
            self.time_from.setTime(QTime(8, 0))

        def _update_duration_display():
            """Duration is always editable - no auto-calculation."""
            has_date = self.date_de.date() != self._unassigned_qdate
            if has_date:
                self.duration_sb.setEnabled(True)
                self.duration_sb.setToolTip("Dauer in Minuten")
            else:
                self.duration_sb.setEnabled(True)
                self.duration_sb.setToolTip("Manuelle Dauer: definiert den Platzhalter-Umfang beim Ziehen in den Kalender")

        def _sync_time_enabled():
            has_date = self.date_de.date() != self._unassigned_qdate
            self.time_from.setEnabled(has_date)
            self.duration_sb.setEnabled(has_date or True)  # Always enabled
            _update_duration_display()

        def _on_date_changed():
            """When date changes from unassigned, jump to today."""
            current_date = self.date_de.date()
            # If user is moving away from unassigned (clicking up arrow or editing)
            if current_date != self._unassigned_qdate and current_date == self._unassigned_qdate.addDays(1):
                # They tried to go from unassigned to next day, jump to today instead
                today = date.today()
                self.date_de.setDate(date_to_qdate(today))
            _sync_time_enabled()

        # Connect time changes to update duration
        self.time_from.timeChanged.connect(lambda *_: _update_duration_display())
        self.date_de.dateChanged.connect(lambda *_: _on_date_changed())

        _sync_time_enabled()


        form.addRow("Name:", self.name_le)
        form.addRow("LVA:", self.lva_cb)
        form.addRow("Semester:", self.semester_cb)
        form.addRow("Typ:", self.typ_le)
        form.addRow("Datum:", self.date_de)
        form.addRow("Von:", self.time_from)
        form.addRow("Dauer:", self.duration_sb)
        form.addRow("Raum:", self.raum_cb)
        form.addRow("Gruppe Name:", self.grp_name)
        form.addRow("Gruppe Größe:", self.grp_size)
        form.addRow("", self.ap_cb)
        form.addRow("Notiz:", self.note_te)

        # bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        # bb.accepted.connect(self._accept)
        # bb.rejected.connect(self.reject)
        # lay.addWidget(bb)
        
        # Removed ID object name
        self.lva_cb.setObjectName("HeaderCombo")
        self.semester_cb.setObjectName("HeaderCombo")
        self.typ_le.setObjectName("Field")
        self.date_de.setObjectName("DateEdit")
        self.time_from.setObjectName("Field")
        self.duration_sb.setObjectName("Field")
        self.raum_cb.setObjectName("HeaderCombo")
        self.grp_name.setObjectName("Field")
        self.grp_size.setObjectName("Field")
        self.note_te.setObjectName("Field")
        
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)

        # QSS hooks
        bb.setObjectName("DialogButtons")
        ok_btn = bb.button(QDialogButtonBox.Ok)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setObjectName("PrimaryButton")
        if cancel_btn:
            cancel_btn.setObjectName("SecondaryButton")

        lay.addWidget(bb)



    def _set_cb(self, cb: QComboBox, data_value: str):
        for i in range(cb.count()):
            if cb.itemData(i) == data_value:
                cb.setCurrentIndex(i)
                return

    def _accept(self):
        # Removed ID field validation and assignment


        lva_id = str(self.lva_cb.currentData())
        raum_id = str(self.raum_cb.currentData())
        typ = self.typ_le.text().strip().upper()
        semester_id = str(self.semester_cb.currentData())

        qd = self.date_de.date()
        d = None if qd == self._unassigned_qdate else qdate_to_date(qd)

        start_zeit = None
        if d is not None:
            tf = self.time_from.time()
            start_zeit = time(tf.hour(), tf.minute())
        gname = self.grp_name.text().strip()
        gruppe = None
        # Nur wenn ein Name gesetzt ist, eine Gruppe erzeugen
        if gname:
            gsize = int(self.grp_size.value())
            gruppe = Gruppe(name=gname, groesse=gsize)

        # Duration: always save the user-entered value
        duration_value = int(self.duration_sb.value())

        name_value = self.name_le.text().strip()
        if self.termin is not None and hasattr(self.termin, 'id'):
            self._result = Termin(
                name=name_value,
                id=self.termin.id,
                lva_id=lva_id,
                typ=typ,
                datum=d,
                start_zeit=start_zeit,
                raum_id=raum_id,
                gruppe=gruppe,
                anwesenheitspflicht=bool(self.ap_cb.isChecked()),
                notiz=self.note_te.toPlainText().strip(),
                duration=duration_value,
                semester_id=semester_id,
            )
        else:
            self._result = Termin(
                name=name_value,
                id=self.new_id,
                lva_id=lva_id,
                typ=typ,
                datum=d,
                start_zeit=start_zeit,
                raum_id=raum_id,
                gruppe=gruppe,
                anwesenheitspflicht=bool(self.ap_cb.isChecked()),
                notiz=self.note_te.toPlainText().strip(),
                duration=duration_value,
                semester_id=semester_id,
            )
        self.accept()

    @property
    def result(self) -> Optional[Termin]:
        return self._result

    def eventFilter(self, obj, event):
        #Handle calendar popup to show today's date when unassigned
        if obj == self.date_de and not self._calendar_shown:
            if event.type() == QEvent.Type.MouseButtonPress or event.type() == QEvent.Type.KeyPress:
                # User is about to open the calendar
                if self.date_de.date() == self._unassigned_qdate:
                    # Set calendar to show today
                    self._calendar_shown = True
                    try:
                        def set_calendar():
                            cal = self.date_de.calendarWidget()
                            if cal:
                                today = date.today()
                                qd = date_to_qdate(today)
                                cal.setCurrentPage(today.year, today.month)
                                cal.setSelectedDate(qd)
                            self._calendar_shown = False
                        QTimer.singleShot(0, set_calendar)
                    except:
                        self._calendar_shown = False
        return super().eventFilter(obj, event)