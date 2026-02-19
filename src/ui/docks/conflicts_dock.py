"""
Konflikte Dock Widget - displays schedule conflicts and warnings.
"""

from typing import List, Dict, Optional
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QScrollArea, QFrame, QStyle
)

from ...core.models import Termin, Lehrveranstaltung, Raum, Semester, ConflictIssue
from ...services.conflict_service import ConflictDetector
from ..components.cards.conflict_card import ConflictCard
from ..utils.datetime_utils import fmt_date, fmt_time

from ..components.widgets.tight_combobox import TightComboBox


class ConflictsDock(QDockWidget):
    """
    Dock widget for displaying conflicts and warnings
    """
    
    # Signal emitted to highlight all related termine
    conflict_items_highlight = Signal(list)

    _CATEGORY_LABELS = {
        "room": "Raum",
        "lecturer": "Vortragende",
        "time_period": "Zeitraum",
        "group": "Gruppe",
        "semester": "Semester",
        "incomplete": "Unvollstaendig",
    }

    _CATEGORY_KIND_MAP = {
        "room": "raum",
        "lecturer": "vortragende",
        "time_period": "zeitraum",
        "group": "gruppe",
        "semester": "semester",
        "incomplete": "unvollstaendig",
    }
    
    def __init__(self, parent=None):
        super().__init__("Konflikte", parent)
        self.setObjectName("dock_conflicts")
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        
        self._issues: List[ConflictIssue] = []
        self._detector: Optional[ConflictDetector] = None
        
        # Filter state
        self._filter_severity = "Alle"  # "Alle", "Konflikt", "Warnung"
        self._filter_category = "all"   # "all" or specific category key
        
        # Main widget
        main_widget = QWidget(self)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Filter controls (match global filter styling)
        filter_bar = QWidget(self)
        filter_bar.setObjectName("HeaderBar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(6, 6, 6, 6)
        filter_layout.setSpacing(8)

        self.severity_filter = TightComboBox()
        self.severity_filter.setObjectName("HeaderCombo")
        self.severity_filter.setMinimumWidth(160)
        self.severity_filter.addItem("Typ: Alle", "Alle")
        self.severity_filter.addItem("Typ: Konflikt", "Konflikt")
        self.severity_filter.addItem("Typ: Warnung", "Warnung")
        self.severity_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.severity_filter)

        self.category_filter = TightComboBox()
        self.category_filter.setObjectName("HeaderCombo")
        self.category_filter.setMinimumWidth(220)
        self.category_filter.addItem("Kategorie: Alle", "all")
        for key, label in self._CATEGORY_LABELS.items():
            self.category_filter.addItem(f"Kategorie: {label}", key)
        self.category_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.category_filter)

        filter_layout.addStretch()

        layout.addWidget(filter_bar)
        
        # Header with summary and refresh button
        header = QHBoxLayout()
        header.setSpacing(8)
        
        self.summary_label = QLabel("Keine Konflikte")
        self.summary_label.setObjectName("ConflictsSummary")
        self.summary_label.setProperty("state", "ok")
        header.addWidget(self.summary_label)
        
        header.addStretch()
        
        self.refresh_btn = QPushButton()
        icon_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "icons"
            / "iconmonstr-reload-lined.svg"
        )
        if icon_path.is_file():
            self.refresh_btn.setIcon(QIcon(str(icon_path)))
        else:
            self.refresh_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.refresh_btn.setToolTip("Aktualisieren")
        self.refresh_btn.setFixedSize(26, 26)
        self.refresh_btn.setIconSize(QSize(16, 16))
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # Scrollable card list
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.cards_container = QWidget(self.scroll)
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch(1)

        self.scroll.setWidget(self.cards_container)
        layout.addWidget(self.scroll)
        
        self.setWidget(main_widget)
    
    def initialize_detector(self, 
                          lvas: List[Lehrveranstaltung],
                          raeume: List[Raum]) -> None:
        """Initialize the conflict detector with current data."""
        self._detector = ConflictDetector(lvas, raeume)
    
    def refresh_conflicts(self, termine: List[Termin]) -> None:
        """Detect and display conflicts for the given Termine."""
        if not self._detector:
            return
        
        # Detect all issues
        self._issues = self._detector.detect_all(termine)
        
        # Update summary (using all issues, not filtered)
        conflicts = [i for i in self._issues if i.severity == "conflict"]
        warnings = [i for i in self._issues if i.severity == "warning"]
        
        if not self._issues:
            summary = "✓ Keine Konflikte"
            state = "ok"
        else:
            summary = f"⚠ {len(conflicts)} Konflikt(e), {len(warnings)} Warnung(en)"
            if conflicts:
                state = "conflict"
            else:
                state = "warning"
        
        self.summary_label.setProperty("state", state)
        # self.summary_label.style().unpolish(self.summary_label)
        self.summary_label.style().polish(self.summary_label)
        self.summary_label.setText(summary)
        
        # Update cards with filtered results
        self._populate_cards()
        
    def _populate_cards(self) -> None:
        self._clear_cards()

        filtered_issues = self._apply_filters()

        for issue in filtered_issues:
            type_text = "Konflikt" if issue.severity == "conflict" else "Warnung"
            zeit_str = ""
            if issue.zeit_von and issue.zeit_bis:
                zeit_str = f"{fmt_time(issue.zeit_von)} - {fmt_time(issue.zeit_bis)}"
            elif issue.zeit_von:
                zeit_str = fmt_time(issue.zeit_von)

            subtitle = f"{fmt_date(issue.datum)} · {zeit_str}".strip(" ·")
            category_label = self._get_category_label(issue.category)
            title = f"{type_text} · {category_label}"

            conflict_kind = self._get_conflict_kind(issue.category)
            termin_ids = [str(tid) for tid in issue.termin_ids] if issue.termin_ids else []

            card = ConflictCard(
                termin_ids=termin_ids,
                title=title,
                subtitle=subtitle,
                typ=type_text,
                raum=issue.raum,
                lva=issue.lva,
                gruppe=issue.gruppe,
                message=issue.message,
                conflict_kind=conflict_kind,
                severity=issue.severity,
                parent=self.cards_container,
            )
            card.clicked.connect(self._on_card_clicked)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.cards_layout.addStretch(1)

    def _on_card_clicked(self, termin_ids: list[str]) -> None:
        if termin_ids:
            self.conflict_items_highlight.emit(termin_ids)

    def _get_conflict_kind(self, category: str) -> str:
        return self._CATEGORY_KIND_MAP.get(category, "default")

    def _get_category_label(self, category: str) -> str:
        return self._CATEGORY_LABELS.get(category, category)
    
    def _on_refresh_clicked(self) -> None:
        # connected to the main window's refresh method
        parent = self.parent()
        if parent and hasattr(parent, 'refresh_conflicts'):
            parent.refresh_conflicts()
    
    def _on_filter_changed(self) -> None:
        self._filter_severity = self.severity_filter.currentData() or "Alle"
        self._filter_category = self.category_filter.currentData() or "all"
        self._populate_cards()
    
    def _apply_filters(self) -> List[ConflictIssue]:
        filtered = self._issues
        
        # Filter by severity
        if self._filter_severity == "Konflikt":
            filtered = [i for i in filtered if i.severity == "conflict"]
        elif self._filter_severity == "Warnung":
            filtered = [i for i in filtered if i.severity == "warning"]
        # "Alle" shows everything
        
        # Filter by category
        if self._filter_category != "all":
            filtered = [i for i in filtered if i.category == self._filter_category]
        
        return filtered
    
