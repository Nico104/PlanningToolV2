$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $python -m pip install pyinstaller

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name Planungstool `
  --icon "$PSScriptRoot\src\ui\assets\icons\app_icon.ico" `
  --add-data "$PSScriptRoot\default_tables;default_tables" `
  --add-data "$PSScriptRoot\src\settings.json;src" `
  --add-data "$PSScriptRoot\src\studiensemester.json;src" `
  --add-data "$PSScriptRoot\src\konflikte.json;src" `
  --add-data "$PSScriptRoot\src\ui\styles;src\ui\styles" `
  --add-data "$PSScriptRoot\src\ui\assets;src\ui\assets" `
  "$PSScriptRoot\main.py"

Write-Host ""
Write-Host "Fertig: $PSScriptRoot\dist\Planungstool.exe"
