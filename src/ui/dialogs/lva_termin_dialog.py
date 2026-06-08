from datetime import date, time, timedelta
from typing import List, Optional, Dict

from PySide6.QtCore import QTime, QDate, Qt, QEvent, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QMessageBox,
    QComboBox, QDateEdit, QTimeEdit, QSpinBox, QTextEdit, QTabWidget, QScrollArea, QLabel, QPushButton,
    QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView
)

from ...core.models import Termin, Gruppe, Lehrveranstaltung, Semester, Raum, Vortragende, Studiensemester, SerienAusnahme
from ...services.semester_rules import semester_for_date, semester_from_id
from ...services.termin_occurrence_service import SUPPORTED_PERIODIZITAET, series_date_sequence
from ..utils.datetime_utils import date_to_qdate, qdate_to_date

from ..components.widgets.tick_checkbox import TickCheckBox
from ..components.widgets.tight_combobox import TightComboBox
from ..components.widgets.semester_selector import SemesterSelector
from ..components.widgets.chip_list_widget import ChipListWidget
from .series_occurrence_dialog import SeriesOccurrenceDialog

NEW_LVA_SENTINEL = "__new_lva__"
NEW_RAUM_SENTINEL = "__new_raum__"
STANDARD_TERMIN_TYPES = ["VO", "UE", "VU", "LU", "SE", "PR"]


def _scrollable_tab(form: QFormLayout) -> QScrollArea:
    content = QWidget()
    content.setObjectName("DialogTabContent")
    content.setStyleSheet("QWidget#DialogTabContent { background: #ffffff; }")
    content.setLayout(form)

    scroll = QScrollArea()
    scroll.setObjectName("DialogTabScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    scroll.setStyleSheet(
        "QScrollArea#DialogTabScroll { background: #ffffff; border: none; }"
        "QScrollArea#DialogTabScroll > QWidget > QWidget { background: #ffffff; }"
    )
    return scroll


class LVATerminDialog(QDialog):
    """Dialog for editing LVA master data and Termin planning in one window."""
    def __init__(self, parent: QWidget, *,
                 lvas: List[Lehrveranstaltung],
                 semester: Optional[List[Semester]] = None,
                 raeume: List[Raum],
                 studiensemester: List[Studiensemester] = None,
                 studienrichtungen: List[dict] = None,
                 termin: Optional[Termin] = None,
                 settings: Optional[Dict] = None,
                 new_id = None,
                 default_semester_id: Optional[str] = None,
                 ):
        super().__init__(parent)
        self.new_id = new_id
        self.termin = termin
        self.setObjectName("AppDialog")
        self.setModal(True)
        self.settings = settings or {}
        self._semester = list(semester or [])
        self._studiensemester = list(studiensemester or [])
        self._studienrichtungen = list(studienrichtungen or [])
        self._result_lva: Optional[Lehrveranstaltung] = None
        self._result_raum: Optional[Raum] = None
        self._source_lva_id: Optional[str] = None
        self._source_raum_id: Optional[str] = None
        self._suggested_semester_id: Optional[str] = None
        self._auto_series_end_date: Optional[date] = None
        self._series_end_manually_changed = False
        self._updating_series_end = False
        self._creating_lva = False
        self._creating_raum = False

        # Sentinel for unassigned date
        self._unassigned_qdate = QDate(1900, 1, 1)

        self.name_le = QLineEdit(termin.name if (termin and hasattr(termin, 'name')) else "")
        self.name_le.setObjectName("Field")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)
        self.setMinimumSize(760, 640)
        self.resize(820, 720)

        self.setWindowTitle("LVA-Termin bearbeiten" if termin else "LVA-Termin hinzufügen")
        self._result: Optional[Termin] = None


        self.lva_cb = TightComboBox()
        self.lva_cb.setObjectName("HeaderCombo")
        self._lva_by_id = {}
        self.lva_cb.addItem("+ Neue Lehrveranstaltung", NEW_LVA_SENTINEL)
        for l in lvas:
            self.lva_cb.addItem(f"{l.id} – {l.name}", l.id)
            self._lva_by_id[str(l.id)] = l
        if lvas and termin is not None:
            self.lva_cb.setCurrentIndex(1)

        self.lva_id_le = QLineEdit()
        self.lva_id_le.setObjectName("Field")
        self.lva_name_le = QLineEdit()
        self.lva_name_le.setObjectName("Field")
        self.lva_ects_le = QLineEdit()
        self.lva_ects_le.setObjectName("Field")
        self.lva_teacher_le = QLineEdit()
        self.lva_teacher_le.setObjectName("Field")
        self.lva_email_le = QLineEdit()
        self.lva_email_le.setObjectName("Field")
        self.lva_studienrichtung_cb = TightComboBox(self)
        self.lva_studienrichtung_cb.setObjectName("HeaderCombo")
        self.lva_studienrichtung_cb.setMinimumWidth(160)
        self._populate_lva_studienrichtungen()
        self.lva_studiensemester_chips = ChipListWidget([])
        self.lva_studiensemester_cb = TightComboBox(self)
        self.lva_studiensemester_cb.setObjectName("HeaderCombo")
        self.lva_studiensemester_cb.setMinimumWidth(160)
        self.btn_add_lva_studiensemester = QPushButton("Hinzufügen")

        def _sync_lva_fields():
            if self.lva_cb.currentData() == NEW_LVA_SENTINEL:
                self._clear_lva_fields_for_new()
                return
            self._creating_lva = False
            lva = self._lva_by_id.get(str(self.lva_cb.currentData()))
            self.lva_id_le.setText(getattr(lva, "id", "") if lva else "")
            self.lva_name_le.setText(getattr(lva, "name", "") if lva else "")
            self.lva_ects_le.setText(str(getattr(lva, "ects", "")) if lva and getattr(lva, "ects", "") else "")
            teacher = getattr(lva, "vortragende", None)
            self.lva_teacher_le.setText(getattr(teacher, "name", "") if teacher else "")
            self.lva_email_le.setText(getattr(teacher, "email", "") if teacher else "")
            self._set_lva_studienrichtung(getattr(lva, "studienrichtung", "ETIT") if lva else "ETIT")
            self._set_lva_studiensemester_chips(getattr(lva, "studiensemester", []) if lva else [])

        self.lva_cb.currentIndexChanged.connect(_sync_lva_fields)
        self.lva_studiensemester_chips.chipDeleted.connect(self._remove_lva_studiensemester_chip)
        self.btn_add_lva_studiensemester.clicked.connect(self._add_lva_studiensemester_chip)
        self._refresh_lva_studiensemester_cb()

        self._semester_by_id = {}
        for s in self._semester:
            self._semester_by_id[str(s.id)] = s
        preferred_semester_id = (
            getattr(termin, "semester_id", None)
            if termin is not None
            else default_semester_id
        )
        if not preferred_semester_id:
            preferred_semester_id = semester_for_date(date.today()).id
        self.semester_selector = SemesterSelector(
            self,
            include_all=False,
            default_semester_id=str(preferred_semester_id) if preferred_semester_id else None,
        )


        self.typ_cb = TightComboBox()
        self.typ_cb.setObjectName("HeaderCombo")
        self.typ_cb.setMinimumWidth(120)
        self._refresh_termin_type_options(getattr(termin, "typ", "VO") if termin else "VO")
        
        self.date_de = QDateEdit()
        self.date_de.setCalendarPopup(True)
        self.date_de.setObjectName("DateEdit")

        self.date_de.setMinimumDate(self._unassigned_qdate)
        self.date_de.setSpecialValueText("Kein Datum zugewiesen")
        self.date_de.setDate(self._unassigned_qdate)
        self.date_to_de = QDateEdit()
        self.date_to_de.setCalendarPopup(True)
        self.date_to_de.setObjectName("DateEdit")
        self.date_to_de.setMinimumDate(self._unassigned_qdate)
        self.date_to_de.setSpecialValueText("Kein Datum zugewiesen")
        self.date_to_de.setDate(self._unassigned_qdate)

        # Wenn gerade Kein Datum zugewiesen aktiv ist (Sentinel-Datum), wird beim Öffnen des Kalender-Popups automatisch der aktuelle Monat/Tag angezeigt, statt 1900
        self._calendar_shown = False
        self.date_de.installEventFilter(self)
        self.date_to_de.installEventFilter(self)

        self.time_from = QTimeEdit()
        self.time_from.setObjectName("Field")
        self.time_to = QTimeEdit()
        self.time_to.setObjectName("Field")
        self.time_to.setTime(QTime(9, 0))

        self.raum_cb = TightComboBox()
        self.raum_cb.setObjectName("HeaderCombo")
        self._raum_by_id = {}
        self.raum_cb.addItem("+ Neuer Raum", NEW_RAUM_SENTINEL)
        for r in raeume:
            self.raum_cb.addItem(f"{r.id} – {r.name}", r.id)
            self._raum_by_id[str(r.id)] = r
        if raeume and termin is not None:
            self.raum_cb.setCurrentIndex(1)

        self.raum_id_le = QLineEdit()
        self.raum_id_le.setObjectName("Field")
        self.raum_name_le = QLineEdit()
        self.raum_name_le.setObjectName("Field")
        self.raum_capacity_sb = QSpinBox()
        self.raum_capacity_sb.setRange(1, 2000)
        self.raum_capacity_sb.setObjectName("Field")

        def _sync_raum_fields():
            if self.raum_cb.currentData() == NEW_RAUM_SENTINEL:
                self._clear_raum_fields_for_new()
                return
            self._creating_raum = False
            raum = self._raum_by_id.get(str(self.raum_cb.currentData()))
            self.raum_id_le.setText(getattr(raum, "id", "") if raum else "")
            self.raum_name_le.setText(getattr(raum, "name", "") if raum else "")
            self.raum_capacity_sb.setValue(int(getattr(raum, "kapazitaet", 30)) if raum else 30)

        self.raum_cb.currentIndexChanged.connect(_sync_raum_fields)

        self.grp_name = QLineEdit((termin.gruppe.name if (termin and termin.gruppe) else ""))
        self.grp_name.setObjectName("Field")
        self.grp_size = QSpinBox()
        self.grp_size.setRange(0, 2000)
        self.grp_size.setValue((termin.gruppe.groesse if (termin and termin.gruppe) else 0))
        self.grp_size.setObjectName("Field")

        self.duration_sb = QSpinBox()
        self.duration_sb.setRange(0, 1000)
        self.duration_sb.setSingleStep(int(self.settings.get("duration_step_minutes", 15)))
        self.duration_sb.setValue(termin.duration if termin else 0)
        self.duration_sb.setSuffix(" min")
        self.duration_sb.setObjectName("Field")

        self.repeat_cb = QComboBox()
        self.repeat_cb.addItems(["wöchentlich", "2-wöchentlich", "monatlich", "2-monatlich", "täglich"])
        self.repeat_cb.setObjectName("HeaderCombo")

        self.series_cb = TickCheckBox("")
        self.series_cb.setChecked(bool(termin and getattr(termin, "datum_bis", None)))
        self._ausfall_dates: set[date] = set()
        self._serien_ausnahmen: List[SerienAusnahme] = list(getattr(termin, "serien_ausnahmen", []) or []) if termin else []
        self._occurrence_row_dates: List[date] = []
        self.occurrence_table = QTableWidget(0, 3)
        self.occurrence_table.setObjectName("Field")
        self.occurrence_table.setHorizontalHeaderLabels(["Original", "Termin", ""])
        self.occurrence_table.verticalHeader().hide()
        self.occurrence_table.setSelectionMode(QTableWidget.NoSelection)
        self.occurrence_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.occurrence_table.setFocusPolicy(Qt.NoFocus)
        self.occurrence_table.setShowGrid(False)
        self.occurrence_table.setMinimumHeight(260)
        self.occurrence_table.cellDoubleClicked.connect(self._on_occurrence_row_double_clicked)
        self.occurrence_table.setStyleSheet(
            "QTableWidget#Field { border: none; background: #ffffff; }"
            "QTableWidget#Field::item { border: none; padding: 2px 0; }"
        )
        self.occurrence_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.occurrence_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.occurrence_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.ap_cb = TickCheckBox("")
        self.ap_cb.setChecked(bool(termin.anwesenheitspflicht) if termin else False)

        def _sync_group_fields():
            name = self.grp_name.text().strip()
            if name:
                self.grp_size.setEnabled(True)
            else:
                self.grp_size.setEnabled(False)
                self.grp_size.setValue(0)

        self.grp_name.textChanged.connect(lambda *_: _sync_group_fields())
        _sync_group_fields()

        self.note_te = QTextEdit()
        self.note_te.setObjectName("Field")
        self.note_te.setFixedHeight(92)
        self.note_te.setPlainText(termin.notiz if termin else "")

        self.zu_besprechen_cb = TickCheckBox("")
        self.zu_besprechen_cb.setChecked(bool(getattr(termin, "zu_besprechen", False)) if termin else False)

        self.besprechungshinweis_te = QTextEdit()
        self.besprechungshinweis_te.setObjectName("DiscussionField")
        self.besprechungshinweis_te.setFixedHeight(76)
        self.besprechungshinweis_te.setPlainText(
            str(getattr(termin, "besprechungshinweis", "") or "") if termin else ""
        )

        self.besprechungshinweis_wrap = QWidget()
        self.besprechungshinweis_wrap.setObjectName("InlineField")
        besprechnung_lay = QVBoxLayout(self.besprechungshinweis_wrap)
        besprechnung_lay.setContentsMargins(0, 0, 0, 0)
        besprechnung_lay.setSpacing(8)
        besprechnung_lay.addWidget(self.zu_besprechen_cb)
        besprechnung_lay.addWidget(self.besprechungshinweis_te)

        def _sync_besprechungshinweis(checked: bool) -> None:
            self.besprechungshinweis_te.setEnabled(bool(checked))
            if not checked:
                self.besprechungshinweis_te.clear()

        self.zu_besprechen_cb.toggled.connect(_sync_besprechungshinweis)
        _sync_besprechungshinweis(self.zu_besprechen_cb.isChecked())

        if termin:
            # Set date - keep unassigned if it was unassigned
            if termin and termin.datum:
                self.date_de.setDate(date_to_qdate(termin.datum))
                if getattr(termin, "datum_bis", None):
                    self.date_to_de.setDate(date_to_qdate(termin.datum_bis))
                    period = getattr(termin, "periodizitaet", "wöchentlich") or "wöchentlich"
                    if period in SUPPORTED_PERIODIZITAET:
                        self.repeat_cb.setCurrentText(period)
                else:
                    self.date_to_de.setDate(self._unassigned_qdate)
            else:
                # Keep as unassigned
                self.date_de.setDate(self._unassigned_qdate)
                self.date_to_de.setDate(self._unassigned_qdate)

            # Set start time
            if termin.start_zeit:
                self.time_from.setTime(QTime(termin.start_zeit.hour, termin.start_zeit.minute))
                end_time = termin.get_end_time()
                if end_time:
                    self.time_to.setTime(QTime(end_time.hour, end_time.minute))
            else:
                # Default start time
                self.time_from.setTime(QTime(8, 0))
                self.time_to.setTime(QTime(9, 0))

            self._set_cb(self.lva_cb, termin.lva_id)
            self._set_cb(self.raum_cb, termin.raum_id)
            # Set semester combobox if semester_id is present
            if hasattr(termin, 'semester_id'):
                self.semester_selector.set_semester_id(getattr(termin, 'semester_id', None))
            for ausfall_date in getattr(termin, "ausfall_daten", []) or []:
                self._add_ausfall_date(ausfall_date)
        else:
            # New termin: start with today
            today = date.today()
            self.date_de.setDate(date_to_qdate(today))
            self.date_to_de.setDate(self._unassigned_qdate)
            self.time_from.setTime(QTime(8, 0))
            self.time_to.setTime(QTime(9, 0))

        if termin and getattr(termin, "datum_bis", None):
            self._series_end_manually_changed = True

        def _sync_time_enabled():
            has_date = self.date_de.date() != self._unassigned_qdate
            is_series = self.series_cb.isChecked()
            has_end_date = self.date_to_de.date() != self._unassigned_qdate
            self.time_from.setEnabled(has_date)
            self.time_to.setEnabled(has_date)
            self.series_cb.setEnabled(has_date)
            self.date_to_de.setEnabled(has_date and is_series)
            self.repeat_cb.setEnabled(has_date and is_series and has_end_date)
            self._sync_ausfall_controls()
            if not has_date:
                self.series_cb.setChecked(False)
                self.date_to_de.setDate(self._unassigned_qdate)

        def _on_series_toggled(checked: bool):
            if checked:
                if self.date_de.date() == self._unassigned_qdate:
                    self.series_cb.setChecked(False)
                    return
                if self.date_to_de.date() == self._unassigned_qdate or self.date_to_de.date() <= self.date_de.date():
                    self._set_series_end_date(self._suggested_series_end_date(), auto=True)
            else:
                self._set_series_end_date(None, auto=True)
                self._ausfall_dates.clear()
                self._serien_ausnahmen.clear()
            self._update_semester_warning()
            _sync_time_enabled()
            self._render_occurrence_table()
            self._sync_series_occurrences_tab()

        def _on_date_changed():
            #When date changes from unassigned, jump to today
            current_date = self.date_de.date()
            
            if current_date != self._unassigned_qdate and current_date == self._unassigned_qdate.addDays(1):
                
                today = date.today()
                self.date_de.setDate(date_to_qdate(today))
            self._maybe_update_series_end_date(force_if_invalid=True)
            self._update_semester_warning()
            _sync_time_enabled()
            self._render_occurrence_table()

        self.date_de.dateChanged.connect(_on_date_changed)
        self.date_to_de.dateChanged.connect(lambda *_: (self._on_series_end_changed(), _sync_time_enabled(), self._update_semester_warning(), self._render_occurrence_table()))
        self.series_cb.toggled.connect(_on_series_toggled)
        self.repeat_cb.currentIndexChanged.connect(lambda *_: (self._maybe_update_series_end_date(), self._update_semester_warning(), self._sync_ausfall_controls(), self._render_occurrence_table()))
        self.time_from.timeChanged.connect(lambda *_: self._sync_duration_from_times())
        self.time_to.timeChanged.connect(lambda *_: self._sync_duration_from_times())

        _sync_time_enabled()
        _sync_lva_fields()
        _sync_raum_fields()
        self._sync_duration_from_times()

        self.tabs = QTabWidget(self)
        lay.addWidget(self.tabs, 1)

        self.semester_warning_lbl = QLabel()
        self.semester_warning_lbl.setWordWrap(True)
        self.semester_warning_lbl.setStyleSheet(
            "color: #8a5a00; background: #fff8e6; border: 1px solid #f0d99a; "
            "border-radius: 6px; padding: 8px;"
        )
        self.semester_warning_lbl.hide()
        self.semester_change_btn = QPushButton()
        self.semester_change_btn.setObjectName("SecondaryButton")
        self.semester_change_btn.clicked.connect(self._change_to_suggested_semester)
        self.semester_change_btn.hide()

        termin_form = QFormLayout()
        termin_form.setContentsMargins(20, 18, 20, 18)
        termin_form.setHorizontalSpacing(18)
        termin_form.setVerticalSpacing(14)
        termin_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        termin_form.addRow("Termin-Typ *:", self.typ_cb)
        termin_form.addRow("Semester:", self.semester_selector)
        termin_form.addRow("", self.semester_warning_lbl)
        termin_form.addRow("", self.semester_change_btn)
        termin_form.addRow("Beginn-Datum:", self.date_de)
        termin_form.addRow("Serientermin:", self.series_cb)
        termin_form.addRow("Ende-Datum:", self.date_to_de)
        termin_form.addRow("Periodizität:", self.repeat_cb)
        termin_form.addRow("Von:", self.time_from)
        termin_form.addRow("Bis:", self.time_to)
        termin_form.addRow("Dauer *:", self.duration_sb)
        # termin_form.addRow("Anwesenheitspflicht:", self.ap_cb)
        termin_form.addRow("Zusatzbezeichnung:", self.name_le)
        termin_form.addRow("Notiz:", self.note_te)
        termin_form.addRow("Zu besprechen:", self.besprechungshinweis_wrap)
        self.tabs.addTab(_scrollable_tab(termin_form), "Termindetails")

        series_occurrences_form = QFormLayout()
        series_occurrences_form.setContentsMargins(20, 18, 20, 18)
        series_occurrences_form.setHorizontalSpacing(18)
        series_occurrences_form.setVerticalSpacing(14)
        series_occurrences_form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        series_occurrences_form.setFormAlignment(Qt.AlignTop)
        series_occurrences_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        series_occurrences_form.addRow("Termine:", self.occurrence_table)
        self.series_occurrences_tab = _scrollable_tab(series_occurrences_form)

        gruppe_form = QFormLayout()
        gruppe_form.setContentsMargins(20, 18, 20, 18)
        gruppe_form.setHorizontalSpacing(18)
        gruppe_form.setVerticalSpacing(14)
        gruppe_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gruppe_form.addRow("Name:", self.grp_name)
        gruppe_form.addRow("Größe:", self.grp_size)
        self.tabs.addTab(_scrollable_tab(gruppe_form), "Gruppe")

        lva_form = QFormLayout()
        lva_form.setContentsMargins(20, 18, 20, 18)
        lva_form.setHorizontalSpacing(18)
        lva_form.setVerticalSpacing(14)
        lva_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lva_form.addRow("Auswahl:", self.lva_cb)
        lva_form.addRow("LVA-Nr. *:", self.lva_id_le)
        lva_form.addRow("LVA-Name *:", self.lva_name_le)
        lva_form.addRow("ECTS:", self.lva_ects_le)
        lva_form.addRow("Vortragende/r:", self.lva_teacher_le)
        lva_form.addRow("E-Mail:", self.lva_email_le)
        lva_form.addRow("Studienrichtung *:", self.lva_studienrichtung_cb)
        studiensemester_layout = QHBoxLayout()
        studiensemester_layout.addWidget(self.lva_studiensemester_cb)
        studiensemester_layout.addWidget(self.btn_add_lva_studiensemester)
        lva_form.addRow("Studiensemester:", self.lva_studiensemester_chips)
        lva_form.addRow("Studiensemester hinzufügen/entfernen:", studiensemester_layout)
        self.tabs.addTab(_scrollable_tab(lva_form), "Lehrveranstaltung")

        raum_form = QFormLayout()
        raum_form.setContentsMargins(20, 18, 20, 18)
        raum_form.setHorizontalSpacing(18)
        raum_form.setVerticalSpacing(14)
        raum_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        raum_form.addRow("Auswahl:", self.raum_cb)
        raum_form.addRow("Raumnummer *:", self.raum_id_le)
        raum_form.addRow("Raum *:", self.raum_name_le)
        raum_form.addRow("Kapazität:", self.raum_capacity_sb)
        self.tabs.addTab(_scrollable_tab(raum_form), "Raum")

        self.semester_selector.semesterChanged.connect(lambda *_: (self._maybe_update_series_end_date(), self._update_semester_warning()))
        self._update_semester_warning()
        self._render_occurrence_table()
        self._sync_series_occurrences_tab()
        
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)

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

    def _selected_semester(self) -> Optional[Semester]:
        semester_id = self.semester_selector.current_semester_id()
        if not semester_id:
            return None

        sem = self._semester_by_id.get(str(semester_id))
        if sem:
            return sem

        sem = semester_from_id(str(semester_id))
        if sem is None:
            return None
        self._semester_by_id[sem.id] = sem
        return sem

    def _current_termin_type(self) -> str:
        if not hasattr(self, "typ_cb"):
            return ""
        value = self.typ_cb.currentData()
        if value is None:
            value = self.typ_cb.currentText()
        return str(value or "").strip().upper()

    def _refresh_termin_type_options(self, preferred: Optional[str] = None) -> None:
        if not hasattr(self, "typ_cb"):
            return

        selected = str(preferred or self._current_termin_type() or "VO").strip().upper()
        options = list(STANDARD_TERMIN_TYPES)
        if selected and selected not in options:
            options.append(selected)

        self.typ_cb.blockSignals(True)
        self.typ_cb.clear()
        for value in options:
            self.typ_cb.addItem(value, value)

        idx = self.typ_cb.findData(selected)
        if idx < 0:
            idx = 0
        self.typ_cb.setCurrentIndex(idx)
        self.typ_cb.blockSignals(False)

    def _suggested_series_end_date(self) -> date:
        start = qdate_to_date(self.date_de.date())
        sem = self._selected_semester()
        if sem and sem.end > start:
            return sem.end
        return start + timedelta(days=7)

    def _series_end_date(self) -> Optional[date]:
        if self.date_to_de.date() == self._unassigned_qdate:
            return None
        return qdate_to_date(self.date_to_de.date())

    def _set_series_end_date(self, value: Optional[date], *, auto: bool) -> None:
        self._updating_series_end = True
        try:
            self.date_to_de.setDate(date_to_qdate(value) if value is not None else self._unassigned_qdate)
        finally:
            self._updating_series_end = False
        if auto:
            self._auto_series_end_date = value
            self._series_end_manually_changed = False

    def _on_series_end_changed(self) -> None:
        if self._updating_series_end:
            return
        current = self._series_end_date()
        if current is None:
            self._series_end_manually_changed = bool(self.series_cb.isChecked())
            return
        self._series_end_manually_changed = current != self._auto_series_end_date

    def _maybe_update_series_end_date(self, *, force_if_invalid: bool = False) -> None:
        if not self.series_cb.isChecked() or self.date_de.date() == self._unassigned_qdate:
            return

        start = qdate_to_date(self.date_de.date())
        current = self._series_end_date()
        current_is_invalid = current is None or current <= start
        follows_previous_auto = (
            current is not None
            and self._auto_series_end_date is not None
            and current == self._auto_series_end_date
        )

        if self._series_end_manually_changed and not follows_previous_auto and not (force_if_invalid and current_is_invalid):
            return

        suggested = self._suggested_series_end_date()
        if suggested <= start:
            suggested = start + timedelta(days=7)
        self._set_series_end_date(suggested, auto=True)

    def _clear_lva_fields_for_new(self) -> None:
        self._creating_lva = True
        self.lva_id_le.clear()
        self.lva_name_le.clear()
        self.lva_ects_le.clear()
        self.lva_teacher_le.clear()
        self.lva_email_le.clear()
        self._set_lva_studienrichtung(str(self.settings.get("start_studienrichtung", "ETIT")).strip() or "ETIT")
        self._set_lva_studiensemester_chips([])
        self.lva_id_le.setFocus()

    def _populate_lva_studienrichtungen(self) -> None:
        self.lva_studienrichtung_cb.clear()
        seen_ids = set()
        for item in self._studienrichtungen:
            if not isinstance(item, dict):
                continue
            studienrichtung_id = str(item.get("id", "")).strip()
            studienrichtung_name = str(item.get("name", "")).strip()
            if not studienrichtung_id or studienrichtung_id in seen_ids:
                continue
            seen_ids.add(studienrichtung_id)
            label = f"{studienrichtung_id} - {studienrichtung_name}" if studienrichtung_name else studienrichtung_id
            self.lva_studienrichtung_cb.addItem(label, studienrichtung_id)

        default_studienrichtung = str(self.settings.get("start_studienrichtung", "ETIT")).strip() or "ETIT"
        if default_studienrichtung and self.lva_studienrichtung_cb.findData(default_studienrichtung) < 0:
            self.lva_studienrichtung_cb.addItem(default_studienrichtung, default_studienrichtung)
        self._set_lva_studienrichtung(default_studienrichtung)

    def _set_lva_studienrichtung(self, studienrichtung_id: str) -> None:
        value = str(studienrichtung_id or "").strip()
        if value and self.lva_studienrichtung_cb.findData(value) < 0:
            self.lva_studienrichtung_cb.addItem(value, value)
        idx = self.lva_studienrichtung_cb.findData(value)
        if idx >= 0:
            self.lva_studienrichtung_cb.setCurrentIndex(idx)
        elif self.lva_studienrichtung_cb.count() > 0:
            self.lva_studienrichtung_cb.setCurrentIndex(0)

    def _studiensemester_display(self, studiensemester_item: Studiensemester) -> str:
        return (
            str(studiensemester_item.name).strip()
            if studiensemester_item.name
            else str(studiensemester_item.id).strip()
        )

    def _set_lva_studiensemester_chips(self, semester_ids) -> None:
        chips = []
        for raw_id in semester_ids or []:
            semester_id = str(raw_id).strip()
            if not semester_id:
                continue
            studiensemester_item = next((s for s in self._studiensemester if str(s.id) == semester_id), None)
            display = self._studiensemester_display(studiensemester_item) if studiensemester_item else semester_id
            if display and display not in chips:
                chips.append(display)
        self.lva_studiensemester_chips.setItems(chips)
        self._refresh_lva_studiensemester_cb()

    def _refresh_lva_studiensemester_cb(self) -> None:
        self.lva_studiensemester_cb.clear()
        selected_names = set(self.lva_studiensemester_chips.items)
        for studiensemester_item in self._studiensemester:
            display = self._studiensemester_display(studiensemester_item)
            if not display or display in selected_names:
                continue
            note = str(studiensemester_item.notiz or "").strip()
            label = f"{display} - {note}" if note else display
            self.lva_studiensemester_cb.addItem(label, studiensemester_item.id)

    def _add_lva_studiensemester_chip(self) -> None:
        semester_id = self.lva_studiensemester_cb.currentData()
        if semester_id is None or self.lva_studiensemester_cb.currentIndex() < 0:
            return
        studiensemester_item = next((s for s in self._studiensemester if str(s.id) == str(semester_id)), None)
        if studiensemester_item is None:
            return
        display = self._studiensemester_display(studiensemester_item)
        if display and display not in self.lva_studiensemester_chips.items:
            self.lva_studiensemester_chips.addItem(display)
            self._refresh_lva_studiensemester_cb()

    def _remove_lva_studiensemester_chip(self, index: int) -> None:
        self.lva_studiensemester_chips.removeItem(index)
        self._refresh_lva_studiensemester_cb()

    def _current_lva_studiensemester_ids(self) -> List[str]:
        out = []
        for chip_name in self.lva_studiensemester_chips.items:
            name = str(chip_name).strip()
            if not name:
                continue
            studiensemester_item = next((s for s in self._studiensemester if self._studiensemester_display(s) == name), None)
            if studiensemester_item and studiensemester_item.id not in out:
                out.append(studiensemester_item.id)
        return out

    def _clear_raum_fields_for_new(self) -> None:
        self._creating_raum = True
        self.raum_id_le.clear()
        self.raum_name_le.clear()
        self.raum_capacity_sb.setValue(30)
        self.raum_id_le.setFocus()

    def _current_lva_id(self) -> str:
        return self.lva_id_le.text().strip()

    def _sync_duration_from_times(self) -> None:
        start = self.time_from.time()
        end = self.time_to.time()
        start_minutes = start.hour() * 60 + start.minute()
        end_minutes = end.hour() * 60 + end.minute()
        if end_minutes <= start_minutes:
            return
        self.duration_sb.setValue(end_minutes - start_minutes)

    def _date_sequence(self, start: date, end: date, repeat: str) -> List[date]:
        if repeat not in SUPPORTED_PERIODIZITAET:
            return [start]
        return series_date_sequence(start, end, repeat)

    def _has_series_range(self) -> bool:
        return (
            self.series_cb.isChecked()
            and self.date_de.date() != self._unassigned_qdate
            and self.date_to_de.date() != self._unassigned_qdate
            and self.date_to_de.date() > self.date_de.date()
        )

    def _sync_ausfall_controls(self) -> None:
        enabled = self._has_series_range()
        self.occurrence_table.setEnabled(enabled)

    def _sync_series_occurrences_tab(self) -> None:
        if not hasattr(self, "tabs") or not hasattr(self, "series_occurrences_tab"):
            return

        index = self.tabs.indexOf(self.series_occurrences_tab)
        should_show = self.series_cb.isChecked()
        if should_show and index < 0:
            self.tabs.insertTab(1, self.series_occurrences_tab, "Serientermine")
        elif not should_show and index >= 0:
            self.tabs.removeTab(index)

    def _add_ausfall_date(self, value: date) -> None:
        if value is None:
            return
        self._ausfall_dates.add(value)
        self._render_occurrence_table()

    def _set_occurrence_active(self, value: date, active: bool) -> None:
        if active:
            self._ausfall_dates.discard(value)
        else:
            self._ausfall_dates.add(value)
            self._serien_ausnahmen = [
                item for item in self._serien_ausnahmen if item.original_datum != value
            ]
        self._render_occurrence_table()
        self._update_semester_warning()

    def _series_dates_for_table(self) -> List[date]:
        if not self._has_series_range():
            return []
        return self._date_sequence(
            qdate_to_date(self.date_de.date()),
            qdate_to_date(self.date_to_de.date()),
            self.repeat_cb.currentText(),
        )

    def _render_occurrence_table(self) -> None:
        if not hasattr(self, "occurrence_table"):
            return
        dates = self._series_dates_for_table()
        valid_dates = set(dates)
        self._ausfall_dates = {value for value in self._ausfall_dates if value in valid_dates}
        self._serien_ausnahmen = [
            item
            for item in self._serien_ausnahmen
            if item.original_datum in valid_dates and item.datum is not None
        ]
        exceptions_by_date = {
            item.original_datum: item for item in self._serien_ausnahmen
        }

        self._clear_occurrence_table_widgets()
        self.occurrence_table.clearSpans()
        self.occurrence_table.clearContents()
        self.occurrence_table.setRowCount(0)
        self._occurrence_row_dates = list(dates)
        self.occurrence_table.setRowCount(len(dates))
        for row, value in enumerate(dates):
            hidden = value in self._ausfall_dates
            exception = exceptions_by_date.get(value)

            original_item = QTableWidgetItem(value.strftime("%d.%m.%Y"))
            detail_item = QTableWidgetItem(self._occurrence_detail_text(value, exception))
            if hidden:
                original_item.setForeground(Qt.gray)
                detail_item.setForeground(Qt.gray)
                strike = QFont()
                strike.setStrikeOut(True)
                original_item.setFont(strike)
                detail_item.setFont(strike)
                detail_item.setText(f"{detail_item.text()} · Fällt aus")

            self.occurrence_table.setItem(row, 0, original_item)
            self.occurrence_table.setItem(row, 1, detail_item)

            if exception and not hidden:
                reset_btn = QPushButton("Zurücksetzen")
                reset_btn.setObjectName("SecondaryButton")
                reset_btn.setToolTip("Verschiebung entfernen und wieder den normalen Serientermin verwenden")
                reset_btn.clicked.connect(lambda _checked=False, occurrence_date=value: self._reset_series_exception(occurrence_date))
                self.occurrence_table.setCellWidget(row, 2, reset_btn)
        self.occurrence_table.resizeRowsToContents()
        self.occurrence_table.viewport().update()

    def _clear_occurrence_table_widgets(self) -> None:
        for row in range(self.occurrence_table.rowCount()):
            for col in range(self.occurrence_table.columnCount()):
                widget = self.occurrence_table.cellWidget(row, col)
                if widget:
                    self.occurrence_table.removeCellWidget(row, col)
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()

        for button in self.occurrence_table.findChildren(QPushButton):
            if button.text() == "Zurücksetzen":
                button.hide()
                button.setParent(None)
                button.deleteLater()

    def _current_ausfall_dates(self) -> List[date]:
        if not self._has_series_range():
            return []
        planned = set(self._series_dates_for_table())
        return sorted(value for value in self._ausfall_dates if value in planned)

    def _current_series_exceptions(self) -> List[SerienAusnahme]:
        if not self._has_series_range():
            return []
        planned = set(self._series_dates_for_table())
        return sorted(
            [
                item
                for item in self._serien_ausnahmen
                if item.original_datum in planned and item.original_datum not in self._ausfall_dates
            ],
            key=lambda item: item.original_datum,
        )

    def _occurrence_detail_text(self, original_date: date, exception: Optional[SerienAusnahme]) -> str:
        target_date = exception.datum if exception else original_date
        start = exception.start_zeit if exception and exception.start_zeit is not None else self._current_start_time()
        room_id = exception.raum_id if exception and exception.raum_id is not None else self.raum_id_le.text().strip()

        parts = [target_date.strftime("%d.%m.%Y")]
        if start is not None:
            parts.append(start.strftime("%H:%M"))
        if room_id:
            parts.append(room_id)
        if exception and exception.datum != original_date:
            return f"{original_date.strftime('%d.%m.%Y')} -> {' · '.join(parts)}"
        return " · ".join(parts)

    def _on_occurrence_row_double_clicked(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self._occurrence_row_dates):
            return
        self._open_occurrence_dialog(self._occurrence_row_dates[row])

    def _open_occurrence_dialog(self, value: date) -> None:
        current = next(
            (item for item in self._serien_ausnahmen if item.original_datum == value),
            None,
        )

        base_start = self._current_start_time() or time(8, 0)
        dlg = SeriesOccurrenceDialog(
            self,
            original_date=value,
            current_exception=current,
            base_start=base_start,
            base_room_id=self.raum_id_le.text().strip(),
            rooms=list(self._raum_by_id.values()),
            initially_cancelled=value in self._ausfall_dates,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        result = dlg.result
        if result is None:
            return

        if result.cancelled:
            self._set_occurrence_active(value, False)
            return

        self._ausfall_dates.discard(value)
        self._set_series_exception(
            original_date=result.original_date,
            target_date=result.target_date,
            start_zeit=result.start_zeit,
            room_id=result.room_id,
        )

    def _set_series_exception(
        self,
        *,
        original_date: date,
        target_date: date,
        start_zeit: time,
        room_id: str,
    ) -> None:
        base_start = self._current_start_time()
        base_room = self.raum_id_le.text().strip()
        is_base_value = (
            target_date == original_date
            and start_zeit == base_start
            and str(room_id or "").strip() == base_room
        )

        self._serien_ausnahmen = [
            item for item in self._serien_ausnahmen if item.original_datum != original_date
        ]
        if not is_base_value:
            self._serien_ausnahmen.append(
                SerienAusnahme(
                    original_datum=original_date,
                    datum=target_date,
                    start_zeit=start_zeit,
                    raum_id=str(room_id or "").strip() or None,
                    duration=int(self.duration_sb.value()),
                )
            )
            self._serien_ausnahmen.sort(key=lambda item: item.original_datum)
            self._ausfall_dates.discard(original_date)
        self._render_occurrence_table()
        self._update_semester_warning()

    def _reset_series_exception(self, value: date) -> None:
        self._serien_ausnahmen = [
            item for item in self._serien_ausnahmen if item.original_datum != value
        ]
        self._render_occurrence_table()

    def _current_start_time(self) -> Optional[time]:
        if self.date_de.date() == self._unassigned_qdate:
            return None
        tf = self.time_from.time()
        return time(tf.hour(), tf.minute())

    def _semester_reference_date(self) -> Optional[date]:
        if self.date_de.date() == self._unassigned_qdate:
            return None

        return qdate_to_date(self.date_de.date())

    def _selected_semester_range(self) -> Optional[tuple[date, date]]:
        sem = self._selected_semester()
        if not sem:
            return None
        return sem.start, sem.end

    def _semester_contains_date(self, sem: Semester, planned_date: date) -> bool:
        return sem.start <= planned_date <= sem.end

    def _suggest_semester_for_date(self, planned_date: Optional[date]) -> Optional[Semester]:
        if planned_date is None:
            return None

        current_id = self.semester_selector.current_semester_id()
        suggestion = semester_for_date(planned_date)
        if suggestion.id != current_id:
            return suggestion
        return None

    def _update_semester_warning(self) -> None:
        if not hasattr(self, "semester_warning_lbl"):
            return

        self._suggested_semester_id = None
        planned_date = self._semester_reference_date()
        selected_range = self._selected_semester_range()
        if planned_date is None or selected_range is None:
            self.semester_warning_lbl.hide()
            self.semester_change_btn.hide()
            return

        start, end = selected_range
        if start <= planned_date <= end:
            self.semester_warning_lbl.hide()
            self.semester_change_btn.hide()
            return

        date_text = planned_date.strftime("%d.%m.%Y")

        suggestion = self._suggest_semester_for_date(planned_date)
        if suggestion:
            self._suggested_semester_id = suggestion.id
            if self._semester_contains_date(suggestion, planned_date):
                self.semester_warning_lbl.setText(
                    f"Hinweis: Das Beginn-Datum ({date_text}) liegt außerhalb des ausgewählten Semesters."
                )
            else:
                self.semester_warning_lbl.setText(
                    f"Hinweis: Das Beginn-Datum ({date_text}) liegt außerhalb des üblichen Semesterzeitraums. "
                    "Das naheliegendste Semester kann trotzdem ausgewählt werden."
                )
            self.semester_change_btn.setText(f"Zu {suggestion.name} wechseln")
            self.semester_change_btn.show()
        else:
            self.semester_warning_lbl.setText(
                f"Hinweis: Das Beginn-Datum ({date_text}) liegt außerhalb des üblichen Semesterzeitraums. "
                "Der Termin kann trotzdem gespeichert werden."
            )
            self.semester_change_btn.hide()
        self.semester_warning_lbl.show()

    def _change_to_suggested_semester(self) -> None:
        if self._suggested_semester_id:
            self.semester_selector.set_semester_id(self._suggested_semester_id, emit=True)
            self._update_semester_warning()

    def _accept(self):
        lva_id = self._current_lva_id()
        raum_id = self.raum_id_le.text().strip()
        typ = self._current_termin_type()
        selected_semester = self._selected_semester()
        semester_id = selected_semester.id if selected_semester else ""

        qd = self.date_de.date()
        d = None if qd == self._unassigned_qdate else qdate_to_date(qd)

        start_zeit = None
        if d is not None:
            tf = self.time_from.time()
            start_zeit = time(tf.hour(), tf.minute())
        gname = self.grp_name.text().strip()
        gruppe = None
        if gname:
            gsize = int(self.grp_size.value())
            gruppe = Gruppe(name=gname, groesse=gsize)

        duration_value = int(self.duration_sb.value())
        name_value = self.name_le.text().strip()
        notiz_value = self.note_te.toPlainText().strip()
        zu_besprechen = bool(self.zu_besprechen_cb.isChecked())
        besprechungshinweis_value = self.besprechungshinweis_te.toPlainText().strip()
        anwesenheitspflicht = bool(self.ap_cb.isChecked())
        lva_name_value = self.lva_name_le.text().strip()
        lva_teacher_value = self.lva_teacher_le.text().strip()
        lva_email_value = self.lva_email_le.text().strip()
        lva_ects_value = self.lva_ects_le.text().strip()
        lva_studienrichtung_value = self.lva_studienrichtung_cb.currentData()
        raum_name_value = self.raum_name_le.text().strip()
        semester_name_value = selected_semester.name if selected_semester else ""

        #Validierung
        errors = []
        if not lva_id or lva_id == 'None':
            errors.append("LVA-Nr. fehlt.")
        if not lva_name_value:
            errors.append("LVA-Name fehlt.")
        if lva_studienrichtung_value is None or not str(lva_studienrichtung_value).strip():
            errors.append("Studienrichtung fehlt.")
        if not typ:
            errors.append("Typ fehlt.")
        if not raum_id:
            errors.append("Raumnummer fehlt.")
        if not raum_name_value:
            errors.append("Raum fehlt.")
        if not semester_id:
            errors.append("Semester-ID fehlt.")
        if not semester_name_value:
            errors.append("Semestername fehlt.")
        if duration_value <= 0:
            errors.append("Dauer fehlt oder ist 0.")
        date_to = None
        repeat = None
        if self.series_cb.isChecked():
            if self.date_to_de.date() == self._unassigned_qdate:
                errors.append("Serien-Enddatum fehlt.")
            else:
                date_to = qdate_to_date(self.date_to_de.date())
                repeat = self.repeat_cb.currentText()
                if repeat not in SUPPORTED_PERIODIZITAET:
                    errors.append("Periodizität ist ungültig.")
                if d is not None and date_to <= d:
                    errors.append("Serien-Enddatum muss nach dem Beginn-Datum liegen.")
        if d is not None and date_to is not None and date_to < d:
            errors.append("Datum bis liegt vor Datum von.")
        if date_to is not None and d is None:
            errors.append("Datum bis braucht ein Datum von.")
        if errors:
            QMessageBox.warning(self, "Fehler", "Bitte füllen Sie alle Pflichtfelder aus:\n" + "\n".join(errors))
            return

        existing_lva = self._lva_by_id.get(lva_id)
        selected_lva_id = None
        if self.lva_cb.currentData() is not None:
            selected_lva_id = str(self.lva_cb.currentData()).strip()

        if self._creating_lva and existing_lva is not None:
            QMessageBox.warning(
                self,
                "Fehler",
                "Diese LVA-Nr. existiert bereits. Bitte wählen Sie die bestehende LVA aus "
                "oder verwenden Sie eine neue LVA-Nr.",
            )
            return

        if (
            not self._creating_lva
            and selected_lva_id
            and selected_lva_id != NEW_LVA_SENTINEL
            and lva_id != selected_lva_id
            and existing_lva is not None
        ):
            QMessageBox.warning(self, "Fehler", "Neue LVA-Nr. existiert bereits.")
            return

        existing_raum = self._raum_by_id.get(raum_id)
        selected_raum_id = None
        if self.raum_cb.currentData() is not None:
            selected_raum_id = str(self.raum_cb.currentData()).strip()

        if self._creating_raum and existing_raum is not None:
            QMessageBox.warning(
                self,
                "Fehler",
                "Diese Raumnummer existiert bereits. Bitte wählen Sie den bestehenden Raum aus "
                "oder verwenden Sie eine neue Raumnummer.",
            )
            return

        if (
            not self._creating_raum
            and selected_raum_id
            and selected_raum_id != NEW_RAUM_SENTINEL
            and raum_id != selected_raum_id
            and existing_raum is not None
        ):
            QMessageBox.warning(self, "Fehler", "Neue Raumnummer existiert bereits.")
            return

        self._source_lva_id = None if self._creating_lva else str(self.lva_cb.currentData()).strip() if self.lva_cb.currentData() is not None else None
        self._source_raum_id = None if self._creating_raum else str(self.raum_cb.currentData()).strip() if self.raum_cb.currentData() is not None else None
        self._result_lva = Lehrveranstaltung(
            id=lva_id,
            name=lva_name_value,
            vortragende=Vortragende(lva_teacher_value, lva_email_value),
            typ=[],
            studiensemester=self._current_lva_studiensemester_ids(),
            studienrichtung=str(lva_studienrichtung_value).strip(),
            ects=lva_ects_value,
        )
        self._result_raum = Raum(
            id=raum_id,
            name=raum_name_value,
            kapazitaet=int(self.raum_capacity_sb.value()),
        )

        termin_id = self.termin.id if self.termin is not None and hasattr(self.termin, "id") else self.new_id
        ausfall_dates = self._current_ausfall_dates() if date_to is not None else []
        serien_ausnahmen = self._current_series_exceptions() if date_to is not None else []

        self._result = Termin(
            name=name_value,
            id=termin_id,
            lva_id=lva_id,
            typ=typ,
            datum=d,
            start_zeit=start_zeit,
            raum_id=raum_id,
            gruppe=gruppe,
            anwesenheitspflicht=anwesenheitspflicht,
            notiz=notiz_value,
            zu_besprechen=zu_besprechen,
            besprechungshinweis=besprechungshinweis_value,
            duration=duration_value,
            semester_id=semester_id,
            datum_bis=date_to,
            periodizitaet=repeat,
            ausfall_daten=ausfall_dates,
            serien_ausnahmen=serien_ausnahmen,
        )
        self.accept()

    @property
    def result(self):
        return self._result

    @property
    def result_lva(self):
        return self._result_lva

    @property
    def result_raum(self):
        return self._result_raum

    @property
    def source_lva_id(self):
        return self._source_lva_id

    @property
    def source_raum_id(self):
        return self._source_raum_id

    def eventFilter(self, obj, event):
        #Handle calendar popup to show today's date when unassigned
        if obj in (self.date_de, self.date_to_de) and not self._calendar_shown:
            if event.type() == QEvent.Type.MouseButtonPress or event.type() == QEvent.Type.KeyPress:
                # User is about to open the calendar
                if obj.date() == self._unassigned_qdate:
                    # Set calendar to show today
                    self._calendar_shown = True
                    try:
                        def set_calendar():
                            cal = obj.calendarWidget()
                            if cal:
                                if obj == self.date_to_de and self.date_de.date() != self._unassigned_qdate:
                                    target_date = qdate_to_date(self.date_de.date())
                                else:
                                    target_date = date.today()
                                qd = date_to_qdate(target_date)
                                cal.setCurrentPage(target_date.year, target_date.month)
                                cal.setSelectedDate(qd)
                            self._calendar_shown = False
                        QTimer.singleShot(0, set_calendar)
                    except Exception:
                        self._calendar_shown = False
        return super().eventFilter(obj, event)
