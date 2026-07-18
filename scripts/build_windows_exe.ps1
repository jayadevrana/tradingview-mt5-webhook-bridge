Param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing build dependencies..."
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -e ".[dev]"

Write-Host "Running tests..."
& $PythonExe -m pytest

Write-Host "Building EXE..."
& $PythonExe -m PyInstaller --noconfirm tv2mt5_bridge.spec

Write-Host "Build complete. Output: dist/TV2MT5Bridge.exe"
