from pathlib import Path
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog

from ....services.data_folder_service import (
    data_path_for_settings,
    initialize_missing_project_files,
    inspect_project_folder,
    load_settings,
    resolve_data_dir,
    save_settings,
    validate_or_initialize_data_dir,
)
from ... import resources_rc  # type: ignore  # noqa: F401
from ...utils.qss_tokens import set_qss_tokens
from .main_window import MainWindow


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "plannerV2.planungstool"
        )
    except Exception:
        pass


def _install_german_qt_translations(app: QApplication) -> None:
    translator = QTranslator(app)
    translations_dir = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    if translator.load(QLocale(QLocale.German, QLocale.Germany), "qtbase", "_", translations_dir):
        app.installTranslator(translator)
        app._qtbase_de_translator = translator


def _app_icon_path() -> Path:
    icon_dir = Path(__file__).resolve().parents[2] / "assets" / "icons"
    if sys.platform == "win32":
        preferred = icon_dir / "app_icon.ico"
    elif sys.platform == "darwin":
        preferred = icon_dir / "app_icon.icns"
    else:
        preferred = icon_dir / "app_icon.png"
    return preferred if preferred.exists() else icon_dir / "app_icon.png"


def _choose_data_path(settings: dict, current_data_dir: Path):
    folder = _choose_project_folder("Projektordner wählen", current_data_dir)
    if folder is None:
        return settings, current_data_dir
    if not _prepare_project_folder(folder, title="Projekt öffnen", require_existing_project=True):
        return settings, current_data_dir
    return _save_project_folder(folder)


def _choose_project_folder(title: str, start_dir: Path) -> Path | None:
    folder = QFileDialog.getExistingDirectory(None, title, str(start_dir))
    return Path(folder).resolve() if folder else None


def _save_project_folder(target_dir: Path) -> tuple[dict, Path]:
    settings = load_settings()
    settings["data_path"] = data_path_for_settings(target_dir)
    save_settings(settings)
    return settings, target_dir


def _project_folder_details(target_dir: Path, inspection) -> str:
    parts = [str(target_dir)]
    if inspection.valid_files:
        parts.append("Gefunden:\n" + "\n".join(inspection.valid_files))
    if inspection.missing_files:
        parts.append("Wird angelegt:\n" + "\n".join(inspection.missing_files))
    return "\n\n".join(parts)


def _confirm_project_folder_change(title: str, text: str, target_dir: Path, inspection) -> bool:
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setInformativeText(_project_folder_details(target_dir, inspection))
    ok_btn = msg.addButton("Fortfahren", QMessageBox.AcceptRole)
    msg.addButton("Abbrechen", QMessageBox.RejectRole)
    msg.setDefaultButton(ok_btn)
    msg.exec()
    return msg.clickedButton() == ok_btn


def _show_invalid_project_files(invalid_files: list[str]) -> None:
    error = QMessageBox()
    error.setIcon(QMessageBox.Critical)
    error.setWindowTitle("Projektdateien ungültig")
    error.setText("Der gewählte Ordner enthält ungültige Projektdateien.")
    error.setInformativeText("Die Dateien wurden nicht überschrieben. Bitte wählen Sie einen anderen Ordner.")
    error.setDetailedText("\n".join(invalid_files))
    error.exec()


def _prepare_project_folder(
    folder: Path,
    *,
    title: str,
    require_existing_project: bool = False,
    creating_new: bool = False,
) -> bool:
    try:
        if creating_new:
            folder.mkdir(parents=True, exist_ok=True)
        inspection = inspect_project_folder(folder)
    except Exception as exc:
        QMessageBox.warning(None, title, f"Projektordner konnte nicht vorbereitet werden: {exc}")
        return False

    if require_existing_project and not inspection.has_project_files:
        QMessageBox.warning(None, title, "Dieser Ordner enthält kein Planungsprojekt.")
        return False

    if inspection.invalid_files:
        _show_invalid_project_files(inspection.invalid_files)
        return False

    if creating_new and inspection.has_project_files:
        ok = _confirm_project_folder_change(
            title,
            "Der Ordner enthält bereits Projektdateien. Dieses Projekt verwenden?",
            folder,
            inspection,
        )
        if not ok:
            return False
    elif inspection.missing_files:
        text = (
            "Der Projektordner ist unvollständig. Fehlende Dateien werden angelegt."
            if require_existing_project
            else "In diesem Ordner werden Projektdateien angelegt."
        )
        if not _confirm_project_folder_change(title, text, folder, inspection):
            return False

    initialize_missing_project_files(folder, inspection.missing_files)
    return True


def _choose_initial_project(project_root: Path) -> tuple[dict, Path] | None:
    start_dir = Path.home() / "Documents"
    if not start_dir.exists():
        start_dir = project_root

    while True:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Projekt auswählen")
        msg.setText("Es ist noch kein Projektordner ausgewählt.")
        msg.setInformativeText("Bitte legen Sie ein neues Projekt an oder wählen Sie einen bestehenden Projektordner.")
        create_btn = msg.addButton("Neues Projekt", QMessageBox.AcceptRole)
        choose_btn = msg.addButton("Projektordner wählen", QMessageBox.ActionRole)
        msg.addButton("Abbrechen", QMessageBox.RejectRole)
        msg.setDefaultButton(create_btn)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == create_btn:
            folder = _choose_project_folder("Neues Projekt anlegen", start_dir)
        elif clicked == choose_btn:
            folder = _choose_project_folder("Projektordner wählen", start_dir)
        else:
            return None

        if folder is None:
            continue

        if clicked == create_btn:
            prepared = _prepare_project_folder(folder, title="Neues Projekt", creating_new=True)
        else:
            prepared = _prepare_project_folder(
                folder,
                title="Projekt öffnen",
                require_existing_project=True,
            )
        if not prepared:
            continue

        return _save_project_folder(folder)


def load_global_style(app: QApplication, theme: str = "light") -> None:
    app.setStyle("Fusion")

    pal = QPalette()
    theme = "dark" if str(theme).strip().lower() == "dark" else "light"

    if theme == "dark":
        pal.setColor(QPalette.Window, QColor("#1f2328"))
        pal.setColor(QPalette.Base, QColor("#15181c"))
        pal.setColor(QPalette.Text, QColor("#f1f5f9"))
        pal.setColor(QPalette.WindowText, QColor("#f1f5f9"))
        pal.setColor(QPalette.Highlight, QColor("#3b82f6"))
        pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    else:
        pal.setColor(QPalette.Window, QColor("#f8f8f8"))
        pal.setColor(QPalette.Base, QColor("#ffffff"))
        pal.setColor(QPalette.Text, QColor("#111111"))
        pal.setColor(QPalette.WindowText, QColor("#111111"))
        pal.setColor(QPalette.Highlight, QColor("#01659b"))
        pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    qss_path = Path(__file__).resolve().parents[2] / "styles" / f"{theme}.qss"

    if qss_path.exists():
        qss = qss_path.read_text(encoding="utf-8")
        set_qss_tokens(qss)
        app.setStyleSheet(qss)


def run_gui() -> None:
    _set_windows_app_id()
    app = QApplication([])
    _install_german_qt_translations(app)
    icon_path = _app_icon_path()
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if icon_path.exists():
        app.setWindowIcon(app_icon)
    project_root = Path(__file__).resolve().parents[4]
    settings = load_settings()
    load_global_style(app, settings.get("theme", "light"))
    data_dir = resolve_data_dir(settings)
    if data_dir is None:
        selected = _choose_initial_project(project_root)
        if selected is None:
            return
        settings, data_dir = selected

    while True:
        if not data_dir.exists() or not data_dir.is_dir():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Datenordner ungültig")
            msg.setText(f"Der Datenordner '{data_dir}' ist ungültig oder nicht vorhanden.")
            msg.setInformativeText("Möchten Sie den Datenpfad zurücksetzen oder einen neuen Pfad wählen?")
            reset_btn = msg.addButton("Zurücksetzen", QMessageBox.AcceptRole)
            set_btn = msg.addButton("Pfad wählen", QMessageBox.ActionRole)
            msg.addButton("Abbrechen", QMessageBox.RejectRole)
            msg.setDefaultButton(reset_btn)
            msg.exec()

            if msg.clickedButton() == reset_btn:
                settings = load_settings()
                settings["data_path"] = ""
                save_settings(settings)
                selected = _choose_initial_project(project_root)
                if selected is None:
                    return
                settings, data_dir = selected
                continue
            if msg.clickedButton() == set_btn:
                settings, data_dir = _choose_data_path(settings, data_dir)
                continue
            return

        created_files, invalid_files = validate_or_initialize_data_dir(data_dir)
        if not invalid_files:
            if created_files:
                QMessageBox.information(
                    None,
                    "Datenordner initialisiert",
                    "Fehlende Projektdateien wurden angelegt:\n\n" + "\n".join(created_files),
                )
            break

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Projektdateien ungültig")
        msg.setText(f"Der Datenordner '{data_dir}' enthält ungültige Projektdateien.")
        msg.setInformativeText(
            "Die Dateien wurden nicht überschrieben. Bitte wählen Sie einen anderen Datenordner "
            "oder setzen Sie den Datenpfad zurück."
        )
        msg.setDetailedText("\n".join(invalid_files))
        reset_btn = msg.addButton("Zurücksetzen", QMessageBox.AcceptRole)
        set_btn = msg.addButton("Pfad wählen", QMessageBox.ActionRole)
        msg.addButton("Abbrechen", QMessageBox.RejectRole)
        msg.setDefaultButton(reset_btn)
        msg.exec()

        if msg.clickedButton() == reset_btn:
            settings = load_settings()
            settings["data_path"] = ""
            save_settings(settings)
            selected = _choose_initial_project(project_root)
            if selected is None:
                return
            settings, data_dir = selected
        elif msg.clickedButton() == set_btn:
            settings, data_dir = _choose_data_path(settings, data_dir)
        else:
            return

    w = MainWindow(data_dir)
    if not app_icon.isNull():
        w.setWindowIcon(app_icon)
    w.show()

    app.exec()
