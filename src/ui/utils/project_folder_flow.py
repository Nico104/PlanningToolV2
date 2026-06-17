from pathlib import Path

from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from ...services.data_folder_service import initialize_missing_project_files, inspect_project_folder


PROJECT_PART_LABELS = {
    "raeume.json": "Räume",
    "lehrveranstaltungen.json": "LVAs",
    "termine.json": "Termine",
    "studienrichtungen.json": "Studienrichtungen",
    "freie_tage.json": "Freie Tage",
}


def project_part_labels(file_names: list[str]) -> list[str]:
    return [PROJECT_PART_LABELS.get(file_name, file_name) for file_name in file_names]


def _add_list_section(layout: QVBoxLayout, title: str, items: list[str], parent) -> None:
    if not items:
        return
    label = QLabel(title, parent)
    label.setObjectName("DialogSectionTitle")
    layout.addWidget(label)
    for item in items:
        row = QLabel(f"- {item}", parent)
        row.setObjectName("SettingsHelp")
        layout.addWidget(row)


def _confirm(parent, *, title: str, text: str, target_dir: Path, inspection, confirm_label: str) -> bool:
    dlg = QDialog(parent)
    dlg.setObjectName("AppDialog")
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    dlg.setMinimumWidth(520)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(18, 16, 18, 14)
    root.setSpacing(12)

    title_label = QLabel(title, dlg)
    title_label.setObjectName("DialogTitle")
    root.addWidget(title_label)

    subtitle = QLabel(text, dlg)
    subtitle.setObjectName("DialogSubtitle")
    subtitle.setWordWrap(True)
    root.addWidget(subtitle)

    section = QFrame(dlg)
    section.setObjectName("DialogSection")
    section_layout = QVBoxLayout(section)
    section_layout.setContentsMargins(14, 12, 14, 14)
    section_layout.setSpacing(6)

    folder_label = QLabel("Projektordner", section)
    folder_label.setObjectName("DialogSectionTitle")
    section_layout.addWidget(folder_label)
    folder_path = QLabel(str(target_dir), section)
    folder_path.setObjectName("SettingsHelp")
    folder_path.setWordWrap(True)
    section_layout.addWidget(folder_path)

    _add_list_section(section_layout, "Bereits vorhanden", project_part_labels(inspection.valid_files), section)
    _add_list_section(section_layout, "Wird vorbereitet", project_part_labels(inspection.missing_files), section)
    root.addWidget(section)

    buttons = QHBoxLayout()
    buttons.addStretch(1)
    cancel_btn = QPushButton("Abbrechen", dlg)
    cancel_btn.setObjectName("SecondaryButton")
    cancel_btn.clicked.connect(dlg.reject)
    ok_btn = QPushButton(confirm_label, dlg)
    ok_btn.setObjectName("PrimaryButton")
    ok_btn.clicked.connect(dlg.accept)
    buttons.addWidget(cancel_btn)
    buttons.addWidget(ok_btn)
    root.addLayout(buttons)

    ok_btn.setDefault(True)
    return dlg.exec() == QDialog.Accepted


def _show_invalid(parent, invalid_files: list[str]) -> None:
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle("Projektdateien ungültig")
    msg.setText("Der gewählte Ordner enthält ungültige Projektdateien.")
    msg.setInformativeText("Die Dateien wurden nicht überschrieben. Bitte wählen Sie einen anderen Ordner.")
    msg.setDetailedText("\n".join(invalid_files))
    msg.exec()


def prepare_project_folder(
    parent,
    folder: Path,
    *,
    title: str,
    require_existing_project: bool = False,
    creating_new: bool = False,
) -> list[str] | None:
    try:
        if creating_new:
            folder.mkdir(parents=True, exist_ok=True)
        inspection = inspect_project_folder(folder)
    except Exception as exc:
        QMessageBox.warning(parent, title, f"Projektordner konnte nicht vorbereitet werden: {exc}")
        return None

    if require_existing_project and not inspection.has_project_files:
        QMessageBox.warning(parent, title, "Dieser Ordner enthält kein Planungsprojekt.")
        return None

    if inspection.invalid_files:
        _show_invalid(parent, inspection.invalid_files)
        return None

    if creating_new and inspection.has_project_files:
        text = (
            "In diesem Ordner liegt bereits ein teilweise vorhandenes Projekt. "
            "Die fehlenden Projektbereiche werden ergänzt."
            if inspection.missing_files
            else "In diesem Ordner liegt bereits ein Projekt. Möchten Sie es verwenden?"
        )
        ok = _confirm(
            parent,
            title=title,
            text=text,
            target_dir=folder,
            inspection=inspection,
            confirm_label="Projekt verwenden",
        )
        if not ok:
            return None
    elif inspection.missing_files:
        text = (
            "Dieser Projektordner ist unvollständig. Die fehlenden Projektbereiche werden ergänzt."
            if require_existing_project
            else "Die App richtet diesen Ordner als neues Planungsprojekt ein."
        )
        confirm_label = "Projekt ergänzen" if require_existing_project else "Projekt anlegen"
        if not _confirm(
            parent,
            title=title,
            text=text,
            target_dir=folder,
            inspection=inspection,
            confirm_label=confirm_label,
        ):
            return None

    return initialize_missing_project_files(folder, inspection.missing_files)
