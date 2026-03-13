import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog, QPushButton

from .main_window import MainWindow


def _load_settings(settings_path: Path) -> dict:
    if not settings_path.exists():
        return {}
    try:
        return json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_settings(settings_path: Path, settings: dict) -> None:
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _resolve_data_dir(project_root: Path, settings: dict) -> Path:
    data_path = str(settings.get("data_path", "")).strip()
    if not data_path:
        return project_root / "data"

    data_dir = Path(data_path)
    if not data_dir.is_absolute():
        data_dir = (project_root / data_dir).resolve()
    return data_dir


def _show_restart_hint() -> bool:
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle("Gespeichert")
    msg.setText("Gespeichert. Für manche Einstellungen muss das Programm neu gestartet werden.")
    restart_btn = QPushButton("Neustart")
    ok_btn = msg.addButton(QMessageBox.Ok)
    msg.addButton(restart_btn, QMessageBox.AcceptRole)
    msg.setDefaultButton(ok_btn)
    msg.exec()
    return msg.clickedButton() == restart_btn


def load_global_style(app: QApplication) -> None:
    app.setStyle("Fusion")

    pal = QPalette()

    # Light UI base
    pal.setColor(QPalette.Window, QColor("#f8f8f8"))
    pal.setColor(QPalette.Base, QColor("#ffffff"))
    pal.setColor(QPalette.Text, QColor("#111111"))
    pal.setColor(QPalette.WindowText, QColor("#111111"))
    pal.setColor(QPalette.Highlight, QColor("#01659b"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    qss_path = Path(__file__).resolve().parents[2] / "styles" / "light.qss"

    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def run_gui() -> None:
    app = QApplication([])
    load_global_style(app)

    project_root = Path(__file__).resolve().parents[4]
    settings_path = project_root / "src" / "settings.json"
    settings = _load_settings(settings_path)
    data_dir = _resolve_data_dir(project_root, settings)

    while not data_dir.exists() or not data_dir.is_dir():
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
            settings = _load_settings(settings_path)
            settings["data_path"] = ""
            _save_settings(settings_path, settings)
            data_dir = project_root / "data"
        elif msg.clickedButton() == set_btn:
            settings = _load_settings(settings_path)
            current_path = settings.get("data_path", "")
            text, ok = QInputDialog.getText(None, "Datenpfad setzen", "Neuer Datenordner Pfad:", text=current_path)
            if ok:
                settings["data_path"] = text.strip()
                _save_settings(settings_path, settings)
                data_dir = _resolve_data_dir(project_root, settings)
                if _show_restart_hint():
                    subprocess.Popen([sys.executable] + sys.argv)
                    sys.exit(0)
                return
        else:
            return

    w = MainWindow(data_dir)
    w.show()

    app.exec()
