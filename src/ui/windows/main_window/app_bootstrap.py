from pathlib import Path
import sys

from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog

from ....services.data_folder_service import (
    load_settings,
    resolve_data_dir,
    save_settings,
    validate_or_initialize_data_dir,
)
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


def _app_icon_path() -> Path:
    icon_dir = Path(__file__).resolve().parents[2] / "assets" / "icons"
    if sys.platform == "win32":
        preferred = icon_dir / "app_icon.ico"
    elif sys.platform == "darwin":
        preferred = icon_dir / "app_icon.icns"
    else:
        preferred = icon_dir / "app_icon.png"
    return preferred if preferred.exists() else icon_dir / "app_icon.png"


def _resolve_asset_urls(qss: str) -> str:
    icon_dir = (Path(__file__).resolve().parents[2] / "assets" / "icons").as_posix()
    qss = qss.replace('url("src/ui/assets/icons/', f'url("{icon_dir}/')
    qss = qss.replace("url('src/ui/assets/icons/", f"url('{icon_dir}/")
    return qss


def _choose_data_path(settings_path: Path, settings: dict, project_root: Path, current_data_dir: Path):
    text, ok = QInputDialog.getText(
        None,
        "Datenpfad setzen",
        "Neuer Datenordner Pfad:",
        text=str(settings.get("data_path", current_data_dir)),
    )
    if not ok:
        return settings, current_data_dir

    settings = load_settings(settings_path)
    settings["data_path"] = text.strip()
    save_settings(settings_path, settings)
    return settings, resolve_data_dir(project_root, settings)


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
        qss = _resolve_asset_urls(qss)
        set_qss_tokens(qss)
        app.setStyleSheet(qss)


def run_gui() -> None:
    _set_windows_app_id()
    app = QApplication([])
    icon_path = _app_icon_path()
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if icon_path.exists():
        app.setWindowIcon(app_icon)
    project_root = Path(__file__).resolve().parents[4]
    settings_path = project_root / "src" / "settings.json"
    settings = load_settings(settings_path)
    load_global_style(app, settings.get("theme", "light"))
    data_dir = resolve_data_dir(project_root, settings)

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
                settings = load_settings(settings_path)
                settings["data_path"] = ""
                save_settings(settings_path, settings)
                data_dir = project_root / "data"
                continue
            if msg.clickedButton() == set_btn:
                settings, data_dir = _choose_data_path(settings_path, settings, project_root, data_dir)
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
            settings = load_settings(settings_path)
            settings["data_path"] = ""
            save_settings(settings_path, settings)
            data_dir = project_root / "data"
        elif msg.clickedButton() == set_btn:
            settings, data_dir = _choose_data_path(settings_path, settings, project_root, data_dir)
        else:
            return

    w = MainWindow(data_dir)
    if not app_icon.isNull():
        w.setWindowIcon(app_icon)
    w.show()

    app.exec()
