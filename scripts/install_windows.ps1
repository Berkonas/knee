# TrailBuddy Analyzer - Windows setup. Right-click > "Run with PowerShell" (or use install_windows.bat).
# Installs the Python environment inside this folder (.venv), downloads the pose model into .\models
# and creates a Desktop shortcut. Nothing else on your computer is changed.
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
Write-Host "TrailBuddy Analyzer setup in: $Repo"

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $cand = Join-Path $env:USERPROFILE ".local\bin\uv.exe"; if (Test-Path $cand) { $uv = $cand } }
if (-not $uv) {
  Write-Host ""
  Write-Host "This setup needs 'uv' (a Python installer from Astral, https://docs.astral.sh/uv/)."
  $ans = Read-Host "Install uv now with Astral's official installer? [y/N]"
  if ($ans -match '^[Yy]$') {
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
  } else { Write-Host "Install uv yourself (see README), then run this script again."; exit 1 }
}

Write-Host "Installing Python packages (first run takes a few minutes)..."
& $uv sync --frozen
Write-Host "Downloading the pose model (about 9 MB, once)..."
& $uv run python -c "from trailbuddy.core.pose import model_path; print(model_path('full'))"

$Desktop = [Environment]::GetFolderPath("Desktop")
$Lnk = Join-Path $Desktop "TrailBuddy Analyzer.lnk"
$Shell = New-Object -ComObject WScript.Shell
$S = $Shell.CreateShortcut($Lnk)
$S.TargetPath = Join-Path $Repo ".venv\Scripts\pythonw.exe"
$S.Arguments = "-m trailbuddy"
$S.WorkingDirectory = $Repo
$S.IconLocation = Join-Path $Repo "assets\icon.ico"
$S.Description = "TrailBuddy Analyzer"
$S.Save()
Write-Host ""
Write-Host "Done. Double-click 'TrailBuddy Analyzer' on your Desktop to start."
Write-Host "If you move this folder, run this script again."
