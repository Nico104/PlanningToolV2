from pathlib import Path
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTimer, QTranslator
from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog

from ....services.data_folder_service import (
    data_path_for_settings,
    load_settings,
    resolve_data_dir,
    save_settings,
)
from ... import resources_rc  # type: ignore  # noqa: F401
from ...components.widgets.action_dialog import ActionDialog, DialogAction
from ...utils.project_folder_flow import prepare_project_folder
from ...utils.qss_tokens import set_qss_tokens
from .main_window import MainWindow


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("plannerV2.planungstool")
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
    if (
        prepare_project_folder(None, folder, title="Projekt öffnen", require_existing_project=True)
        is None
    ):
        return settings, current_data_dir
    settings, data_dir, _created_new = _save_project_folder(folder)
    return settings, data_dir


def _choose_project_folder(title: str, start_dir: Path) -> Path | None:
    if not start_dir.exists():
        start_dir = start_dir.parent if start_dir.parent.exists() else Path.home() / "Documents"
    if not start_dir.exists():
        start_dir = Path.home()
    folder = QFileDialog.getExistingDirectory(None, title, str(start_dir))
    return Path(folder).resolve() if folder else None


def _invalid_data_dir_action(data_dir: Path, *, prepared: bool) -> str | None:
    reason = (
        "Der gespeicherte Projektordner existiert nicht mehr oder ist nicht erreichbar."
        if not prepared
        else "Der gespeicherte Projektordner enthält keine vollständig verwendbaren Projektdaten."
    )
    dlg = ActionDialog(
        None,
        title="Projektordner nicht verwendbar",
        subtitle=f"{reason}\n\nProjektordner:\n{data_dir}",
        section_title="Fortfahren",
        actions=[
            DialogAction(
                "reset",
                "Gespeicherten Pfad vergessen",
                "Die App vergisst diesen Ordner und fragt danach erneut nach einem Projektordner.",
            ),
            DialogAction(
                "choose",
                "Anderen Projektordner wählen",
                "Einen vorhandenen Projektordner direkt auswählen.",
            ),
        ],
    )
    return dlg.result_key if dlg.exec() else None


def _save_project_folder(target_dir: Path, *, created_new: bool = False) -> tuple[dict, Path, bool]:
    settings = load_settings()
    settings["data_path"] = data_path_for_settings(target_dir)
    save_settings(settings)
    return settings, target_dir, created_new


def _choose_initial_project(project_root: Path) -> tuple[dict, Path, bool] | None:
    start_dir = Path.home() / "Documents"
    if not start_dir.exists():
        start_dir = project_root

    while True:
        dlg = ActionDialog(
            None,
            title="Projekt auswählen",
            subtitle="Es ist noch kein Projektordner ausgewählt. Legen Sie ein neues Planungsprojekt an oder öffnen Sie einen bestehenden Projektordner.",
            section_title="Fortfahren",
            actions=[
                DialogAction(
                    "create",
                    "Neues Projekt anlegen",
                    "Einen leeren Projektordner vorbereiten und optional Standarddaten importieren.",
                ),
                DialogAction(
                    "choose",
                    "Bestehendes Projekt öffnen",
                    "Einen Ordner auswählen, der bereits Projektdaten enthält.",
                ),
            ],
        )
        action = dlg.result_key if dlg.exec() else None

        if action == "create":
            folder = _choose_project_folder("Neues Projekt anlegen", start_dir)
        elif action == "choose":
            folder = _choose_project_folder("Projektordner wählen", start_dir)
        else:
            return None

        if folder is None:
            continue

        if action == "create":
            prepared = prepare_project_folder(
                None, folder, title="Neues Projekt", creating_new=True
            )
        else:
            prepared = prepare_project_folder(
                None,
                folder,
                title="Projekt öffnen",
                require_existing_project=True,
            )
        if prepared is None:
            continue

        return _save_project_folder(folder, created_new=action == "create")


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
    initial_project_created = False
    if data_dir is None:
        selected = _choose_initial_project(project_root)
        if selected is None:
            return
        settings, data_dir, initial_project_created = selected

    while True:
        if not data_dir.exists() or not data_dir.is_dir():
            action = _invalid_data_dir_action(data_dir, prepared=False)
            if action == "reset":
                settings = load_settings()
                settings["data_path"] = ""
                save_settings(settings)
                selected = _choose_initial_project(project_root)
                if selected is None:
                    return
                settings, data_dir, initial_project_created = selected
                continue
            if action == "choose":
                settings, data_dir = _choose_data_path(settings, data_dir)
                continue
            return

        if (
            prepare_project_folder(
                None, data_dir, title="Datenordner prüfen", require_existing_project=True
            )
            is not None
        ):
            break

        action = _invalid_data_dir_action(data_dir, prepared=True)
        if action == "reset":
            settings = load_settings()
            settings["data_path"] = ""
            save_settings(settings)
            selected = _choose_initial_project(project_root)
            if selected is None:
                return
            settings, data_dir, initial_project_created = selected
        elif action == "choose":
            settings, data_dir = _choose_data_path(settings, data_dir)
            initial_project_created = False
        else:
            return

    w = MainWindow(data_dir)
    if not app_icon.isNull():
        w.setWindowIcon(app_icon)
    w.show()
    if initial_project_created:
        QTimer.singleShot(0, lambda: w._offer_default_catalog_for_new_project(data_dir))

    app.exec()
