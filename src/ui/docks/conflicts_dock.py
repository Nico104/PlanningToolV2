"""
Konflikte Dock Widget - displays schedule conflicts and warnings.
"""

from typing import List, Optional
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QStyle,
    QTabBar,
)

from ...core.models import Termin, Lehrveranstaltung, Raum, ConflictIssue
from ...services.conflict_service import ConflictDetector
from ...services.conflict_labels import (
    CONFLICT_CATEGORY_LABELS,
    conflict_category_kind,
    conflict_category_label,
)
from ..components.cards.conflict_card import ConflictCard
from ..utils.datetime_utils import fmt_date, fmt_time

from ..components.widgets.tight_combobox import TightComboBox


def _is_dark_theme(widget: QWidget) -> bool:
    return widget.palette().color(QPalette.Window).lightness() < 128


class ConflictsDock(QDockWidget):
    """
    Dock widget for displaying conflicts and warnings
    """

    # Signal emitted to highlight all related termine
    conflict_items_highlight = Signal(list)

    def __init__(self, parent=None):
        super().__init__("Konflikte", parent)
        self.setObjectName("dock_conflicts")
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        self._base_title = "Konflikte"
        self._tab_badge_total = 0
        self._tab_badge_has_conflicts = False
        self._tab_badge_sync_generation = 0
        self._tab_badge_retry_delays_ms = (0, 50, 150, 400, 900, 1600)

        self._issues: List[ConflictIssue] = []
        self._detector: Optional[ConflictDetector] = None
        self._max_visible_cards = 250

        # Filter state
        self._filter_severity = "all"  # "all", "conflict", "warning"
        self._filter_category = "all"  # "all" or specific category key

        # Main widget
        main_widget = QWidget(self)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        filter_bar = QWidget(self)
        filter_bar.setObjectName("HeaderBar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(6, 6, 6, 6)
        filter_layout.setSpacing(8)

        self.severity_filter = TightComboBox()
        self.severity_filter.setObjectName("HeaderCombo")
        self.severity_filter.setMinimumWidth(160)
        self.severity_filter.addItem("Typ: Alle", "all")
        self.severity_filter.addItem("Typ: Konflikt", "conflict")
        self.severity_filter.addItem("Typ: Warnung", "warning")
        self.severity_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.severity_filter)

        self.category_filter = TightComboBox()
        self.category_filter.setObjectName("HeaderCombo")
        self.category_filter.setMinimumWidth(220)
        self._rebuild_category_filter_options()
        self.category_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.category_filter)

        filter_layout.addStretch()

        layout.addWidget(filter_bar)

        # Header
        header = QHBoxLayout()
        header.setSpacing(6)

        self.summary_label = QLabel("Keine Konflikte")
        self.summary_label.setObjectName("ConflictsSummary")
        self.summary_label.setProperty("state", "ok")
        header.addWidget(self.summary_label)

        self.conflict_summary_chip = QLabel()
        self.conflict_summary_chip.setObjectName("ConflictsSummaryChip")
        self.conflict_summary_chip.setProperty("severity", "conflict")
        self.conflict_summary_chip.hide()
        header.addWidget(self.conflict_summary_chip)

        self.warning_summary_chip = QLabel()
        self.warning_summary_chip.setObjectName("ConflictsSummaryChip")
        self.warning_summary_chip.setProperty("severity", "warning")
        self.warning_summary_chip.hide()
        header.addWidget(self.warning_summary_chip)

        header.addStretch()

        self.refresh_btn = QPushButton()
        icon_name = (
            "iconmonstr-reload-lined_white.svg"
            if _is_dark_theme(self)
            else "iconmonstr-reload-lined.svg"
        )
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "icons" / icon_name
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
        self.dockLocationChanged.connect(lambda _area: self.request_tab_badge_sync())
        self.topLevelChanged.connect(lambda _floating: self.request_tab_badge_sync())
        self.visibilityChanged.connect(lambda _visible: self.request_tab_badge_sync())

    def initialize_detector(
        self, lvas: List[Lehrveranstaltung], raeume: List[Raum], data_dir=None
    ) -> None:
        """Initialize the conflict detector with current data."""
        self._detector = ConflictDetector(lvas, raeume, data_dir=data_dir)

    def refresh_conflicts(self, termine: List[Termin]) -> None:
        """Detect and display conflicts for the given Termine."""
        if not self._detector:
            return

        # Detect all issues
        self._issues = self._detector.detect_all(termine)
        self._rebuild_category_filter_options()

        conflicts = [i for i in self._issues if i.severity == "conflict"]
        warnings = [i for i in self._issues if i.severity == "warning"]
        self._update_title_indicator(len(conflicts), len(warnings))

        if not self._issues:
            self.summary_label.setProperty("state", "ok")
            self.summary_label.setText("Keine Konflikte")
            self.summary_label.show()
            self.conflict_summary_chip.hide()
            self.warning_summary_chip.hide()
        else:
            state = "conflict" if conflicts else "warning"
            self.summary_label.setProperty("state", state)
            self.summary_label.hide()
            self._set_summary_chip(
                self.conflict_summary_chip,
                len(conflicts),
                "Konflikt",
                "Konflikte",
            )
            self._set_summary_chip(
                self.warning_summary_chip,
                len(warnings),
                "Warnung",
                "Warnungen",
            )

        self.summary_label.style().polish(self.summary_label)
        self.conflict_summary_chip.style().polish(self.conflict_summary_chip)
        self.warning_summary_chip.style().polish(self.warning_summary_chip)

        # Update cards mit filtered results
        self._populate_cards()

    def _set_summary_chip(
        self, chip: QLabel, count: int, singular: str, plural: str
    ) -> None:
        chip.setText(f"{count} {singular if count == 1 else plural}")
        chip.setVisible(count > 0)

    def _update_title_indicator(self, conflict_count: int, warning_count: int) -> None:
        total = int(conflict_count) + int(warning_count)
        self.setWindowTitle(self._base_title)
        # Diese setWindowIcon sollte es nicht brauchen, da die BAdges QLabel sind, aber es schadet nicht die Line drinnen zu haben
        self.setWindowIcon(QIcon())
        self._tab_badge_total = total
        self._tab_badge_has_conflicts = conflict_count > 0
        self.setToolTip(
            f"{conflict_count} {'Konflikt' if conflict_count == 1 else 'Konflikte'}, "
            f"{warning_count} {'Warnung' if warning_count == 1 else 'Warnungen'}"
            if total
            else "Keine Konflikte"
        )
        self.request_tab_badge_sync()

    def request_tab_badge_sync(self) -> None:
        self._tab_badge_sync_generation += 1
        generation = self._tab_badge_sync_generation
        for delay in self._tab_badge_retry_delays_ms:
            QTimer.singleShot(delay, lambda generation=generation: self._sync_tab_badge(generation))

    def _sync_tab_badge(self, generation: int | None = None) -> None:
        if generation is not None and generation != self._tab_badge_sync_generation:
            return

        tabbar = self._dock_tabbar()
        if tabbar is None:
            return

        index = self._dock_tab_index(tabbar)
        if index < 0:
            return

        tabbar.setTabToolTip(index, self.toolTip())
        if self._tab_badge_total <= 0:
            tabbar.setTabButton(index, QTabBar.RightSide, None)
            return

        badge = QLabel("99+" if self._tab_badge_total > 99 else str(self._tab_badge_total), tabbar)
        badge.setObjectName("ConflictTabBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setMinimumSize(28, 20)
        badge.setToolTip(self.toolTip())
        badge.setProperty("state", "conflict" if self._tab_badge_has_conflicts else "warning")
        tabbar.setTabButton(index, QTabBar.RightSide, badge)

    def _dock_tabbar(self) -> Optional[QTabBar]:
        window = self.window()
        for tabbar in window.findChildren(QTabBar):
            if self._dock_tab_index(tabbar) >= 0:
                return tabbar
        return None

    def _dock_tab_index(self, tabbar: QTabBar) -> int:
        for index in range(tabbar.count()):
            if tabbar.tabText(index).strip() == self._base_title:
                return index
        return -1

    def _populate_cards(self) -> None:
        self._clear_cards()

        filtered_issues = self._apply_filters()
        visible_issues = filtered_issues[: self._max_visible_cards]

        if len(filtered_issues) > len(visible_issues):
            note = QLabel(
                f"{len(filtered_issues)} Einträge gefunden. "
                f"Die ersten {len(visible_issues)} werden angezeigt; Filter grenzen die Liste ein.",
                self.cards_container,
            )
            note.setObjectName("SettingsHelp")
            note.setWordWrap(True)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, note)

        for issue in visible_issues:
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
        return conflict_category_kind(category)

    def _get_category_label(self, category: str) -> str:
        return conflict_category_label(category)

    def _rebuild_category_filter_options(self) -> None:
        current = (
            self.category_filter.currentData()
            if hasattr(self, "category_filter")
            else self._filter_category
        )

        categories = set(CONFLICT_CATEGORY_LABELS.keys())
        categories.update(i.category for i in self._issues if getattr(i, "category", None))

        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("Kategorie: Alle", "all")
        for category in sorted(categories, key=lambda c: self._get_category_label(c).casefold()):
            label = self._get_category_label(category)
            self.category_filter.addItem(f"Kategorie: {label}", category)
        self.category_filter.blockSignals(False)

        self._set_category_filter_value(current if current is not None else "all")

    def _set_category_filter_value(self, value: str) -> None:
        for i in range(self.category_filter.count()):
            if self.category_filter.itemData(i) == value:
                self.category_filter.setCurrentIndex(i)
                return
        self.category_filter.setCurrentIndex(0)

    def _on_refresh_clicked(self) -> None:
        # connected to the main window's refresh method
        parent = self.parent()
        if parent and hasattr(parent, "refresh_conflicts"):
            parent.refresh_conflicts()

    def _on_filter_changed(self) -> None:
        self._filter_severity = self.severity_filter.currentData() or "all"
        self._filter_category = self.category_filter.currentData() or "all"
        self._populate_cards()

    def _apply_filters(self) -> List[ConflictIssue]:
        filtered = self._issues

        # Filter by severity
        if self._filter_severity == "conflict":
            filtered = [i for i in filtered if i.severity == "conflict"]
        elif self._filter_severity == "warning":
            filtered = [i for i in filtered if i.severity == "warning"]

        # Filter by category
        if self._filter_category != "all":
            filtered = [i for i in filtered if i.category == self._filter_category]

        return filtered
