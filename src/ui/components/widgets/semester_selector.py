from __future__ import annotations

import re
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QSpinBox, QWidget

from .tight_combobox import TightComboBox


_SEMESTER_ID_RE = re.compile(r"^(SS|WS)[\s_-]?(\d{2}|\d{4})$", re.IGNORECASE)


def _parse_semester_id(semester_id: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    match = _SEMESTER_ID_RE.match(str(semester_id or "").strip())
    if not match:
        return None, None
    raw_year = match.group(2)
    year = int(raw_year) if len(raw_year) == 4 else 2000 + int(raw_year)
    return match.group(1).upper(), year


class SemesterSelector(QWidget):
    """Compact selector for SS/WS plus year, while exposing the stored semester id."""

    semesterChanged = Signal(object)

    def __init__(
        self,
        parent=None,
        *,
        include_all: bool = True,
        all_label: str = "Semester: Alle",
        default_semester_id: Optional[str] = None,
        min_year: int = 2000,
        max_year: int = 2099,
    ):
        super().__init__(parent)
        self._include_all = include_all
        self._updating = False
        self.setObjectName("SemesterSelector")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.kind_cb = TightComboBox(self, min_popup_width=150)
        self.kind_cb.setObjectName("SemesterKindCombo")
        self.kind_cb.setToolTip("Semester auswählen")
        self.kind_cb.setFixedWidth(178 if include_all else 184)
        self.kind_cb.setFixedHeight(36)
        self.kind_cb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if include_all:
            self.kind_cb.addItem(all_label, None)
        self.kind_cb.addItem("Sommersemester", "SS")
        self.kind_cb.addItem("Wintersemester", "WS")

        self.year_sb = QSpinBox(self)
        self.year_sb.setObjectName("SemesterYearSpin")
        self.year_sb.setToolTip("Jahr auswählen")
        self.year_sb.setRange(min_year, max_year)
        self.year_sb.setValue(date.today().year)
        self.year_sb.setAccelerated(True)
        self.year_sb.setKeyboardTracking(False)
        self.year_sb.setFixedWidth(78)
        self.year_sb.setFixedHeight(36)
        self.year_sb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout.addWidget(self.kind_cb)
        layout.addWidget(self.year_sb)

        self.kind_cb.currentIndexChanged.connect(self._on_changed)
        self.year_sb.valueChanged.connect(self._on_changed)
        self.set_semester_id(default_semester_id)

    def current_semester_id(self) -> Optional[str]:
        kind = self.kind_cb.currentData()
        if not kind:
            return None
        return f"{str(kind).upper()}{self.year_sb.value() % 100:02d}"

    def current_kind(self) -> Optional[str]:
        kind = self.kind_cb.currentData()
        return str(kind).upper() if kind else None

    def current_year(self) -> int:
        return int(self.year_sb.value())

    def set_semester_id(self, semester_id: Optional[str], *, emit: bool = False) -> None:
        kind, year = _parse_semester_id(semester_id)
        self._updating = True
        try:
            if kind is None:
                if self._include_all:
                    self.kind_cb.setCurrentIndex(0)
                elif self.kind_cb.count() > 0:
                    self.kind_cb.setCurrentIndex(0)
            else:
                idx = self.kind_cb.findData(kind)
                if idx >= 0:
                    self.kind_cb.setCurrentIndex(idx)
                if year is not None:
                    if year < self.year_sb.minimum():
                        self.year_sb.setMinimum(year)
                    if year > self.year_sb.maximum():
                        self.year_sb.setMaximum(year)
                    self.year_sb.setValue(year)
        finally:
            self._updating = False
        self._sync_year_enabled()
        if emit:
            self.semesterChanged.emit(self.current_semester_id())

    def _sync_year_enabled(self) -> None:
        self.year_sb.setEnabled(bool(self.kind_cb.currentData()))

    def _on_changed(self, *_args) -> None:
        if self._updating:
            return
        self._sync_year_enabled()
        self.semesterChanged.emit(self.current_semester_id())
