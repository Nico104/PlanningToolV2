
Erweiterungen zur letzten gezeigten Version:

- Im Kalender wird das Datum angezeigt

- Tag/Wochen/Monats Ansicht (Monatsansicht funktioniert mit list dialog der Termine)

- Wenn im Data Editor ein neuer Termin erstellt wird gibt es die Möglichkeit diesen zu wiederholen (Serientermin)

- Freier Tag kann entweder ein Feiertag oder Vorlesungsfrei sein und wird demensprechend im Kalendar angezeigt. Diese beiden Fälle wirden auch mit 2 Konflikten erweitert.

- Geplante Semester als LVA Attribut, kann gefiltert werden

- Termin Drag and Drop Liste wird nach LVA gruppiert und es wird angezeigt wie viele von den Terminen einem Datum und Zeitslot zugewiesen sind

- Export/Import Funktion mit User Entscheidung ob eine Änderung behalten oder ignoriert werden soll (Diese Logik muss wahrscheinlich besser definiert und überarbeitet werden)

- Filter Dock und Navigations Dock sind jetzt 2 individuelle Docks

- In der Termin Liste gibt es bei Rechtsklick jetzt eine "Springe zu" Option

- LVA haben jetzt Fachrichtung als Attribut und FAchrichtungen können im Data Editor Tab erstellt und bearbeitet werden

- In den Einstellungen ist als Data-Path "data_test" gesetzt, dies sind die Daten mit denen ich diese App entwickelt/getested habe. Wenn Sie diesen String im Settings-Dialog löschen dann wird der normale data Ordner verwendet und die App wird in einem neuen Speicherstand gestartet

- Wenn Sie das Projekt als zip/ordner herunterladen müsste man dieses mit Doppelklick auf Start_PlanningTool öffnen können, alternativ die main.py starten

Weitere wichtige Flows:

- Konflikt Highlight-Flow: Bei Klick auf eine Konflikt-Card wird ein Signal mit Termin-IDs bis ins Main Window weitergeleitet und von dort an den PlannerWorkspace übergeben. In der View wird anschließend die Highlight-Funktion aufgerufen, die die betroffenen Termine visuell hervorhebt und zum ersten betroffenen Termin (Tag/Woche) springt.

- Globaler Filter-Flow: Eine Filteränderung aktualisiert Planner-Ansicht, Terminliste, Data-Editor-Optionen und Konflikte konsistent.

- Navigation/View-Flow: Tag, Woche, Monat sowie Vor/Zurück wechseln die Periode und triggern ein Refresh mit den aktiven Filtern.

- Drag-and-Drop-Verschiebung: Ein Drop in Tag/Woche/Monat schreibt neue Terminwerte und lädt danach alle betroffenen Views neu.

- Unassign-Flow: Ein Termin kann zurück in die Liste gezogen werden und wird dadurch aus Datum/Zeit-Zuweisung gelöst.

- CRUD-Flow im Data Editor: Add/Edit/Delete läuft zentral über Crud-Handler und endet in einem vollständigen UI-Refresh.

- Konflikt-Regel-Flow: Änderungen in den Konflikt-Einstellungen werden gespeichert und die Konflikte danach neu berechnet.

- Refresh-Kaskade: Ein globales Refresh lädt State neu und synchronisiert Kalender, Docks, Filteroptionen und Konfliktanzeige.

- Import-Flow: Importdaten werden normalisiert, über einen Dialog bestätigt und anschließend vollständig übernommen/aktualisiert.

- Export-Flow: Alle relevanten JSON-Daten werden zu einer Projektdatei zusammengeführt und exportiert.