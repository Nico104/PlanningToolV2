# Planungstool

Desktop-Anwendung zur Planung von LVA-Terminen, Räumen, Studiensemestern und Konflikten. Die App ist für lokale Projektordner ausgelegt: Ein Projekt besteht aus mehreren JSON-Dateien, kann aber auch als Excel-Datei importiert oder exportiert werden.

## Starten

### Als EXE

Die gebaute Anwendung liegt unter:

```text
dist/Planungstool.exe
```

Beim ersten Start fragt die App nach einem Projektordner. Es kann ein neues Projekt angelegt oder ein bestehendes Projekt geöffnet werden.

### Aus dem Quellcode

```powershell
.venv\Scripts\python.exe main.py
```

Benötigte Pakete:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Projektordner

Ein Projektordner enthält die Planungsdaten der App:

- Räume
- LVAs
- Termine
- Studienrichtungen
- freie Tage und vorlesungsfreie Zeiträume

Der zuletzt verwendete Projektordner wird in den Einstellungen gespeichert. Wenn dieser Ordner nicht mehr existiert oder ungültig ist, fragt die App beim Start nach einem neuen Projektordner.

## Standarddaten

Für neue Projekte können Standarddaten importiert werden:

- TISS-Daten TU Wien ETIT, Juni 2026
- Räume
- LVAs des Elektrotechnik-Bachelor-Katalogs

Beim Anlegen eines neuen Projekts kann ausgewählt werden, ob die Standarddaten vollständig importiert, gezielt ausgewählt oder übersprungen werden sollen.

## Import

Die App unterstützt:

- vollständige Projektimporte aus Excel oder JSON
- einzelne Listen für Räume oder LVAs aus Excel/CSV
- Standarddatenimport aus den mitgelieferten Tabellen

Beim Import prüft die App neue, geänderte und bereits vorhandene Einträge. Einträge mit fehlenden Pflichtverweisen werden nicht still übernommen, sondern im Importablauf ausgewiesen.

## Export

Wichtige Exporte:

- Projekt-Export als Excel-Datei
- Export für Lehrende
- Wochenkalender-Export

Das Beispielprojekt `Beispiel_Projekt.xlsx` liegt bewusst im Repository und kann zum Testen in ein neues Projekt importiert werden.

## Konflikte

Die Konfliktprüfung markiert auffällige Planungsfälle, blockiert die Planung aber nicht. Unterstützt werden unter anderem:

- Raum-Konflikte
- Gruppen-Konflikte
- Lehrpersonen-Konflikte
- Studienplan-Warnungen
- Feiertags- und vorlesungsfreie Konflikte
- Kapazitätswarnungen
- unvollständige Termine

Die aktiven Konfliktregeln und Schwellenwerte können in den Einstellungen angepasst werden.

## EXE bauen

```powershell
.\build_exe.ps1
```

Das Script verwendet `Planungstool.spec`. Dort ist definiert, welche Dateien in die EXE aufgenommen werden, z. B. Standardtabellen, Styles, Icons und Konfigurationsdateien.

## Entwicklung

Schneller Syntaxcheck:

```powershell
.venv\Scripts\python.exe -m compileall src main.py
```

Der Ordner `dist/` wird bewusst nicht ignoriert, damit die gebaute EXE bei Bedarf mitgegeben werden kann. Temporäre Build- und Testordner wie `build/`, `.pytest_cache/`, `.mypy_cache/` und `data_test/` sind ignoriert.
