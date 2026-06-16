from pathlib import Path

from PySide6.QtWidgets import QMessageBox

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


def _details(target_dir: Path, inspection) -> str:
    parts = [f"Projektordner:\n{target_dir}"]
    if inspection.valid_files:
        parts.append("Bereits vorbereitet:\n- " + "\n- ".join(project_part_labels(inspection.valid_files)))
    if inspection.missing_files:
        parts.append("Wird vorbereitet:\n- " + "\n- ".join(project_part_labels(inspection.missing_files)))
    return "\n\n".join(parts)


def _confirm(parent, *, title: str, text: str, target_dir: Path, inspection, confirm_label: str) -> bool:
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setInformativeText(_details(target_dir, inspection))
    ok_btn = msg.addButton(confirm_label, QMessageBox.AcceptRole)
    msg.addButton("Abbrechen", QMessageBox.RejectRole)
    msg.setDefaultButton(ok_btn)
    msg.exec()
    return msg.clickedButton() == ok_btn


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
