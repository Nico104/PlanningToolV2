# Planungstool

Das Planungstool ist eine Desktop-Anwendung zur Verwaltung und Planung von Lehrveranstaltungsterminen. Es wurde im Rahmen einer Bachelorarbeit entwickelt und unterstützt das Erfassen, Importieren, Prüfen und Exportieren von Termindaten.

Die Anwendung arbeitet mit lokalen Projektordnern. Ein Projektordner enthält die Stammdaten und Termine eines Planungsstands. Zusätzlich können Projektdaten als JSON- oder Excel-Datei ausgetauscht werden.

## Funktionsumfang

Die Anwendung umfasst im Wesentlichen:

- Verwaltung von LVAs, Räumen, Studienrichtungen, Terminen und freien Zeiträumen
- Kalenderansichten für Tag, Woche und Monat
- Terminplanung per Dialog oder Drag-and-Drop
- Unterstützung von Serienterminen
- Filter nach Semester, Studienrichtung, Studiensemester, LVA, Lehrperson, Typ, Gebäude und Raum
- Konfliktprüfung für relevante Planungsfälle
- Import und Export von Planungsdaten
- Export von Terminlisten für Lehrende
- Semester-Werkzeuge zum Kopieren oder Entfernen von Terminen eines Semesters
- Undo/Redo und speicherbare Layouts

## Start aus dem Quellcode

Die Anwendung kann mit Python gestartet werden:

```bash
pip install -r requirements.txt
python main.py
```

Optional liegt unter `dist/Planungstool.exe` eine gebaute Windows-Version bei.

## Projektstruktur

Ein Projekt wird als Ordner gespeichert. Darin liegen die Projektdaten getrennt nach Datenbereichen, unter anderem:

- `raeume.json`
- `lehrveranstaltungen.json`
- `termine.json`
- `studienrichtungen.json`
- `freie_tage.json`

Der verwendete Projektordner wird in den Einstellungen gespeichert. Beim Start prüft die Anwendung, ob der gespeicherte Ordner vorhanden und gültig ist. Falls kein gültiger Ordner gefunden wird, kann ein neuer Projektordner angelegt oder ein bestehender Projektordner ausgewählt werden.

## Standarddaten

Für neue Projekte können mitgelieferte Standarddaten importiert werden. Diese basieren auf TISS-Daten der TU Wien ETIT vom Juni 2026 und enthalten Räume sowie LVAs für den Elektrotechnik-Bachelor-Katalog.

Beim Anlegen eines neuen Projekts kann entschieden werden, ob diese Standarddaten übernommen, gezielt ausgewählt oder übersprungen werden.

## Import und Export

Planungsdaten können als Excel- oder JSON-Dateien importiert werden. Der Import unterscheidet zwischen neuen, geänderten und bereits vorhandenen Einträgen. Einträge mit fehlenden Pflichtverweisen werden nicht automatisch übernommen.

Der Export unterstützt vollständige Projektdateien sowie spezielle Ausgaben, zum Beispiel für Lehrende oder als Wochenkalender.

Das Beispielprojekt `BeispielProjektDaten.xlsx` ist als Test- und Demonstrationsdatei beigelegt.

## Konfliktprüfung

Die Konfliktprüfung dient als Hinweisfunktion. Konflikte blockieren die Planung nicht, sondern markieren Einträge, die geprüft werden sollten.

Geprüft werden unter anderem:

- Raumbelegungen
- Gruppenüberschneidungen
- Lehrpersonenüberschneidungen
- Studienplanüberschneidungen
- Feiertage und vorlesungsfreie Zeiträume
- Raumkapazitäten
- unvollständige Termine

Die aktiven Prüfungen und Schwellenwerte können in den Einstellungen angepasst werden.
