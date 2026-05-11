param(
    [string]$DotaPath = ""
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "Installing Python dependency: PySide6"
python -m pip install PySide6

Write-Host "Writing Dota2 Game State Integration config"
if ([string]::IsNullOrWhiteSpace($DotaPath)) {
    python .\install_gsi_config.py
} else {
    python .\install_gsi_config.py "$DotaPath"
}

Write-Host "Starting Dota2 Economy Overlay"
Start-Process -FilePath python -ArgumentList ".\economy_overlay.py" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden

Write-Host ""
Write-Host "Done. Restart Dota2 if it is already running."
Write-Host "Default hotkeys:"
Write-Host "  Ctrl+Alt+E  Force show/hide"
Write-Host "  Ctrl+Alt+T  Toggle mouse click-through"
