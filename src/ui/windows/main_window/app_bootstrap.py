from pathlib import Path

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from .main_window import MainWindow


def load_global_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    #app.setStyle("Windows")

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

    # Load data_path from settings.json in src
    import json
    project_root = Path(__file__).resolve().parents[4]
    settings_path = project_root / "src" / "settings.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        data_path = settings.get("data_path", "").strip()
        if data_path:
            data_dir = Path(data_path)
            if not data_dir.is_absolute():
                data_dir = (project_root / data_dir).resolve()
        else:
            data_dir = project_root / "data"
    else:
        data_dir = project_root / "data"
        
    while not data_dir.exists() or not data_dir.is_dir():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Datenordner ungültig")
        msg.setText(f"Der Datenordner '{data_dir}' ist ungültig oder nicht vorhanden.")
        msg.setInformativeText("Möchten Sie den Datenpfad zurücksetzen oder einen neuen Pfad wählen?")
        reset_btn = msg.addButton("Zurücksetzen", QMessageBox.AcceptRole)
        set_btn = msg.addButton("Pfad wählen", QMessageBox.ActionRole)
        cancel_btn = msg.addButton("Abbrechen", QMessageBox.RejectRole)
        msg.setDefaultButton(reset_btn)
        msg.exec()
        if msg.clickedButton() == reset_btn:
            # Reset to default
            if settings_path.exists():
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                settings["data_path"] = ""
                settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            data_dir = project_root / "data"
        elif msg.clickedButton() == set_btn:
            # Simple input dialog for data path
            from PySide6.QtWidgets import QInputDialog
            if settings_path.exists():
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
            else:
                settings = {}
            current_path = settings.get("data_path", "")
            text, ok = QInputDialog.getText(None, "Datenpfad setzen", "Neuer Datenordner Pfad:", text=current_path)
            if ok:
                settings["data_path"] = text.strip()
                settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                data_path = settings["data_path"]
                if data_path:
                    data_dir = Path(data_path)
                    if not data_dir.is_absolute():
                        data_dir = (project_root / data_dir).resolve()
                else:
                    data_dir = project_root / "data"
                from PySide6.QtWidgets import QMessageBox, QPushButton
                import sys, subprocess
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("Gespeichert")
                msg.setText("Gespeichert. Für manche Einstellungen muss das Programm neu gestartet werden.")
                restart_btn = QPushButton("Neustart")
                ok_btn = msg.addButton(QMessageBox.Ok)
                msg.addButton(restart_btn, QMessageBox.AcceptRole)
                msg.setDefaultButton(ok_btn)
                msg.exec()
                if msg.clickedButton() == restart_btn:
                    python = sys.executable
                    subprocess.Popen([python] + sys.argv)
                    sys.exit(0)
                return
        else:
            # Cancel pressed
            return
    w = MainWindow(data_dir)
    # w.resize(1500, 900)
    w.show()

    app.exec()
