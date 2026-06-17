from dataclasses import dataclass
from datetime import date, time
from typing import Optional

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QTimeEdit,
    QVBoxLayout,
)

from ...core.models import Raum, SerienAusnahme
from ..components.widgets.tick_checkbox import TickCheckBox
from ..components.widgets.tight_combobox import TightComboBox
from ..utils.datetime_utils import date_to_qdate, qdate_to_date


@dataclass(frozen=True)
class SeriesOccurrenceResult:
    original_date: date
    target_date: date
    start_zeit: time
    room_id: str
    cancelled: bool


class SeriesOccurrenceDialog(QDialog):
    """Edit one generated occurrence of a series without detaching it from the series."""

    def __init__(
        self,
        parent,
        *,
        original_date: date,
        current_exception: Optional[SerienAusnahme],
        base_start: time,
        base_room_id: str,
        rooms: list[Raum],
        initially_cancelled: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("AppDialog")
        self.setWindowTitle("Serientermin bearbeiten")
        self.setModal(True)
        self._original_date = original_date
        self._result: Optional[SeriesOccurrenceResult] = None

        target_date = current_exception.datum if current_exception else original_date
        start = (
            current_exception.start_zeit
            if current_exception and current_exception.start_zeit is not None
            else base_start
        )
        room_id = (
            current_exception.raum_id
            if current_exception and current_exception.raum_id is not None
            else base_room_id
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)
        self.setMinimumWidth(520)

        title = QLabel("Serientermin", self)
        title.setObjectName("DialogTitle")
        root.addWidget(title)
        subtitle = QLabel("Ausnahme für einen einzelnen Termin der Serie bearbeiten.", self)
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        form = QFormLayout()
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.cancelled_cb = TickCheckBox("Fällt aus")
        self.cancelled_cb.setChecked(initially_cancelled)

        self.date_de = QDateEdit()
        self.date_de.setCalendarPopup(True)
        self.date_de.setObjectName("DateEdit")
        self.date_de.setDate(date_to_qdate(target_date))

        self.time_edit = QTimeEdit()
        self.time_edit.setObjectName("Field")
        self.time_edit.setTime(QTime(start.hour, start.minute))

        self.room_cb = TightComboBox(min_popup_width=320)
        self.room_cb.setObjectName("HeaderCombo")
        self.room_cb.setMinimumWidth(260)
        self.room_cb.setMaxVisibleItems(7)
        for room in sorted(rooms, key=lambda item: item.id):
            self.room_cb.addItem(f"{room.id} - {room.name}", room.id)
        if room_id and self.room_cb.findData(room_id) < 0:
            self.room_cb.addItem(room_id, room_id)
        idx = self.room_cb.findData(room_id)
        if idx >= 0:
            self.room_cb.setCurrentIndex(idx)

        self.cancelled_cb.toggled.connect(self._sync_enabled)

        form.addRow("Original:", QLabel(original_date.strftime("%d.%m.%Y")))
        form.addRow("", self.cancelled_cb)
        form.addRow("Neues Datum:", self.date_de)
        form.addRow("Neue Startzeit:", self.time_edit)
        form.addRow("Raum:", self.room_cb)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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
        bb.setObjectName("DialogButtons")
        form.addRow("", bb)
        root.addWidget(self._section("Ausnahme", form))

        self._sync_enabled()

    @property
    def result(self) -> Optional[SeriesOccurrenceResult]:
        return self._result

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

    def _sync_enabled(self) -> None:
        enabled = not self.cancelled_cb.isChecked()
        self.date_de.setEnabled(enabled)
        self.time_edit.setEnabled(enabled)
        self.room_cb.setEnabled(enabled)

    def _accept(self) -> None:
        qtime = self.time_edit.time()
        self._result = SeriesOccurrenceResult(
            original_date=self._original_date,
            target_date=qdate_to_date(self.date_de.date()),
            start_zeit=time(qtime.hour(), qtime.minute()),
            room_id=self.room_cb.currentData() or "",
            cancelled=bool(self.cancelled_cb.isChecked()),
        )
        self.accept()
