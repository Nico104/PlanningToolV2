$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $python -m pip install pyinstaller

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  "$PSScriptRoot\Planungstool.spec"

Write-Host ""
Write-Host "Fertig: $PSScriptRoot\dist\Planungstool.exe"
