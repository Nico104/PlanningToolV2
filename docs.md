# PlannerV2 Documentation

## 1. Purpose
This is a desktop planning tool for scheduling university events (Termine).
It combines calendar planning (day/week/month), data administration, filtering, and conflict handling in one UI.

Primary goals:
- Plan and assign Termine to dates, times, and rooms
- Keep master data (LVA, Semester, rooms, etc.) consistent
- Detect and resolve scheduling conflicts
- Support quick workflows via keyboard shortcuts and a user intuitive ui

---

## 2. Core Features

### 2.1 Calendar Workspace
- Views: Day, Week, Month
- Drag and drop Termine within planner tables or out of them
- Visual cards for Termine with type-based styling
- Quick focus/highlight behavior for selected cards, shortcuts for quick unassign/delete for selected cards

#### Drag & Drop Components
- Drag-and-drop is supported across planner tables and the Termine list using custom table and area widgets:
	- TimeGridDropTable: Accepts Termine as drag targets, shows live preview blocks, and checks for conflicts in real time during drag (conflict preview is painted red if a rule is violated; only available in day/week views).
	- MonthDropTable: Accepts Termine as drag targets and shows drag preview, but does not perform live conflict checking during drag (due to missing time granularity).
	- TerminDragTable: Allows Termine to be dragged from the list for assignment.
	- TerminDropArea: Invisible drop target to unassign Termine by dragging them out of the planner.
	- Drag-and-drop uses a custom MIME type to transfer the Termin ID.

#### Custom Card Components
- TerminCard: Interactive card for each Termin, supports drag-and-drop, double-click, and right-click actions. Visual styling reflects type and assignment state.
- ConflictCard: Clickable card showing a detected conflict, emits all affected Termin IDs on click for quick navigation and highlighting.

#### Custom Widgets
- ChipListWidget: Displays a list of removable chips.
- TightComboBox: combo box with letter-jump navigation and better looking UI.
- TickCheckBox: Styled checkbox with a custom tick icon.
- Toast: Overlay notification widget for brief feedback, always appears above the main window and auto-hides.
- EditorTabWidget: Reusable table tab with Add/Edit/Delete buttons and context menu, used in the Data Editor for managing master data.

### 2.2 Termine List
- Grouped by LVA
- Expand/collapse groups
- Shows assigned/unassigned count per group
- Supports jump/edit/delete/unassign actions

### 2.3 Global Filters
- Fachrichtung
- Semester
- LVA
- Dozent
- Typ
- Raum
- Geplantes Semester

### 2.4 Data Editor
Create/edit/delete for:
- Termine
- LVAs
- Semester
- Räume
- Freie Tage
- Geplante Semester
- Fachrichtungen

### 2.5 Conflicts
- Conflict dock and conflict dialog
- Highlights related Termine in planner
- Refreshes conflict state after data changes
- Conflict detection is rule-based and extensible: rules are loaded from `konflikte.json` and can be enabled/disabled individually.
- Conflict preview is shown live while dragging Termine in day/week views (uses the same detection logic as the conflict dock).
- All conflict logic is handled by the ConflictDetector class, which can be extended for new rule types.

### 2.6 Import/Export
- Import JSON bundle
- Export project data to JSON
- Import dialog supports merging or overwriting existing data. Entries are compared by ID and content, and the user can interactively merge or ignore changes.

---

## 3. Main UI Structure

- Main window orchestration: `src/ui/windows/main_window/main_window.py`
- Shortcut registration: `src/ui/windows/main_window/shortcuts.py`
- Planner container/state wiring: `src/ui/planner/workspace.py`
- Day view: `src/ui/planner/day_view.py`
- Week view: `src/ui/planner/week_view.py`
- Month view: `src/ui/planner/month_view.py`
- Termine dock: `src/ui/docks/termine_dock.py`
- Data Editor dock: `src/ui/docks/data_editor_dock.py`
- Date navigation dock: `src/ui/docks/date_navigation_dock.py`
- Global filter dock: `src/ui/docks/global_filter_dock.py`
- FreeDayProvider: Central logic for handling holidays and free days, provides type/color info for planner views and conflict logic.

---

## 4. Keyboard Shortcuts

Global shortcuts (registered in `shortcuts.py`):
- F5: refresh
- Alt+Left / Alt+Right: previous/next period
- Ctrl+1 / Ctrl+2 / Ctrl+3: week/day/month view
- Ctrl+T: jump to today
- Ctrl+N: new Termin
- Ctrl+Alt+T: new Termin
- Ctrl+Alt+L: new LVA
- Ctrl+Alt+S: new Semester
- Ctrl+Alt+R: new room
- Ctrl+Alt+F: new free day
- Ctrl+Alt+G: new planned semester
- Ctrl+Alt+H: new Fachrichtung
- Ctrl+Comma: settings
- Ctrl+O: import
- Ctrl+Shift+E: export
- Ctrl+Shift+R: reset layouts
- Ctrl+Shift+K: open conflict settings

Planner-focused keyboard behavior:
- Delete / Backspace on focused calendar Termin card: unassign Termin
- Ctrl+Delete / Ctrl+Backspace on focused calendar Termin card: delete Termin

Notes:
- Some shortcuts are application-wide.
- Planner card delete/unassign shortcuts are scoped to planner tables to avoid interfering with text inputs.

---

## 5. Data Model Overview

Main data files are under `data/` (and `data_test/` for test data).

- termine.json
- lehrveranstaltungen.json
- semester.json
- raeume.json
- fachrichtungen.json
- freie_tage.json
- geplante_semester.json

General relation model:
- Termin references LVA, room, semester
- LVA can reference one or more planned semesters and a Fachrichtung
- Free days can affect planning visibility and conflict logic
ID usage:
- IDs are used as primary references across JSON files
- New IDs are generated by utility helpers in CRUD handlers

---

## 6. Typical Workflows

### 6.1 Create and assign a Termin
1. Press Ctrl+N or Ctrl+Alt+T (or use Data Editor -> Neuer Termin)
2. Fill required fields (name, LVA, type, duration, etc.)
3. Save
4. Termin appears in planner/list according to assignment

### 6.2 Unassign from calendar quickly
1. Focus a Termin card in calendar
2. Press Delete or Backspace
3. Termin is moved to unassigned state
Alternatively drag the termin into the termin list dock

### 6.3 Hard delete from calendar quickly
1. Focus a Termin card in calendar
2. Press Ctrl+Delete (or Ctrl+Backspace)
3. Confirm deletion in dialog when requested
Alternatively right click termin card in the termin list dock

### 6.4 Create master data from keyboard
- Use Ctrl+Alt+T/L/S/R/F/G/H to open the matching Data Editor add dialog directly

### 6.5 Handle conflicts settings
1. Open conflicts dialog (Ctrl+Shift+K)
2. Inspect/edit rules or data
3. Refresh and verify highlighted Termine

### 6.6 Click conflict card → jump and highlight

1. `ConflictCard` is initialized with `termin_ids` and stores them internally
2. Its `clicked` signal is connected to `ConflictsDock._on_card_clicked`
3. On click -> `mousePressEvent` triggers -> `clicked.emit(self.termin_ids)` (defined in `conflict_card.py`)
4. Qt calls `_on_card_clicked(termin_ids)` with the emitted data
5. Dock forwards via `conflict_items_highlight`
6. Planner receives IDs → jumps + highlights

### 6.7 Undo / Redo

1. User triggers Undo/Redo via `Bearbeiten -> Rückgängig/Wiederholen` or keyboard (`Ctrl+Z` / `Ctrl+Y`)
2. QAction/shortcut calls `MainWindow.perform_undo()` or `MainWindow.perform_redo()`
3. MainWindow asks `UndoService` for the next snapshot via `undo(self.ds)` / `redo(self.ds)`
4. If no snapshot exists, method returns and nothing changes
5. If a snapshot exists, MainWindow calls `UndoService.restore(self.ds, snapshot)`
6. `restore(...)` rewrites all tracked project files from the snapshot (termine, lvas, raeume, semester, fachrichtungen, freie_tage, geplante_semester)
7. MainWindow calls `refresh_everything()` so planner, docks, and conflicts are synchronized with restored data
8. MainWindow calls `update_undo_redo_actions()` to enable/disable menu entries according to stack state
9. Toast feedback is shown (`Rückgängig` / `Wiederholen`)


How snapshots are created:
- All mutating CRUD operations call `_record_undo_snapshot()` before writing new data
- `_record_undo_snapshot()` delegates to `UndoService.record_snapshot(self.ds)`
- `UndoService` emits a history-changed callback after stack updates (`record_snapshot`, `undo`, `redo`)
- `MainWindow` subscribes once via `undo_service.on_history_changed(self.update_undo_redo_actions)` (only used to enable/disable undo redo buttons)

### 6.8 Drag conflict preview

1. While dragging a Termin over day/week grid cells, the table tracks hover row/column and dragged `termin_id`
2. The view provides a conflict checker callback (`set_conflict_checker`) used on hover updates
3. Checker entrypoint is `has_preview_conflict(...)` in `conflict_service.py`
4. The checker simulates a temporary drop target (date/time/room) for the dragged Termin
5. It runs the same `ConflictDetector.detect_all(...)` pipeline as the conflicts dock
6. Therefore the same conflict rules and enabled/disabled flags from `konflikte.json` apply
7. If a conflict is detected for the dragged Termin, hover preview is painted red

Notes:
- Month view: no preview conflict check is wired (missing target time)

### 6.9 Layout presets

How to use:
1. Arrange your docks/windows as needed
2. Open `Ansicht -> Layout -> Aktuelles Layout speichern...`
3. Enter a layout name
4. Select any saved layout from `Ansicht -> Layout` to restore it
5. Use `Ctrl+Shift+R` (or `Layouts zurücksetzen`) to keep only `Standard`

How it works internally:
1. `LayoutManager` stores each layout state via `QMainWindow.saveState()`
2. Preset bytes are base64-encoded and written into `src/settings.json` under `layout_presets`
3. The currently selected preset name is written under `layout_current`
4. On startup, `MainWindow` calls `layout_mgr.init_default()`
5. `init_default()` loads `layout_presets` + `layout_current`, rebuilds menu entries, and applies the last selected layout
6. If persisted data is missing/invalid, `Standard` is used as fallback

### 6.10 Atomic File Saving

`DataService._write()` writes to a `.tmp` file first, then renames it over the target in one OS-level operation (`Path.replace()`). This ensures JSON files are never left in a partial/corrupt state if the app crashes mid-save.



---

### 6.11 Data Path Behavior

`Data Path` in Settings controls which folder is used as the active storage location.

- If `Data Path` points to a folder (for example `data_test`), all reads/writes happen there.
- If `Data Path` is empty, the app falls back to the default `data` folder.
- Switching `Data Path` means switching to a different dataset/profile.
- The same JSON filenames are used in whichever folder is active (`termine.json`, `lehrveranstaltungen.json`, etc.).
- If the folder does not exist, startup asks for reset/new path; if folder exists but required JSON files are missing, loading can fail.


---

### 6.12 Termine Search Bar

The Termine dock includes a live search input for:
- Termin name/ID
- LVA name/ID
- Raum name/ID
- Dozent name

Search is case-insensitive and uses simple substring matching.
Pressing Enter triggers jump only if at least one matching Termin is assigned (`datum` + `start_zeit`).

If there is no assigned match, no jump is triggered.
The search field visibility can be toggled in `Settings` via `Termine-Suche anzeigen`.


