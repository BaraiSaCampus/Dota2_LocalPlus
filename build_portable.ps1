param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Invoke-Python {
    param([string[]]$Arguments)

    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Arguments
        return
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
        return
    }

    throw "Python is required to build the portable package."
}

Write-Host "Installing build dependency: PyInstaller"
Invoke-Python -Arguments @("-m", "pip", "install", "PyInstaller")
Invoke-Python -Arguments @("-m", "pip", "install", "PySide6")

if (-not (Test-Path -LiteralPath ".\item_prices.json")) {
    Write-Host "Generating item price cache"
    Invoke-Python -Arguments @("-c", "import economy_overlay; economy_overlay.load_item_prices()")
}

Remove-Item -Recurse -Force ".\build" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".\dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".\release" -ErrorAction SilentlyContinue

$separator = if ($IsWindows -or $env:OS -eq "Windows_NT") { ";" } else { ":" }
$dataArg = "item_prices.json${separator}."
$modeArgs = if ($OneFile) { @("--onefile") } else { @("--onedir") }

$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed"
)
$pyInstallerArgs += $modeArgs
$pyInstallerArgs += @(
    "--name", "Dota2_LocalPlus",
    "--add-data", $dataArg,
    ".\Dota2_LocalPlus.py"
)
Invoke-Python -Arguments $pyInstallerArgs

New-Item -ItemType Directory -Force -Path ".\release" | Out-Null
if ($OneFile) {
    New-Item -ItemType Directory -Force -Path ".\release\Dota2_LocalPlus" | Out-Null
    Copy-Item ".\dist\Dota2_LocalPlus.exe" ".\release\Dota2_LocalPlus\Dota2_LocalPlus.exe" -Force
} else {
    Copy-Item ".\dist\Dota2_LocalPlus" ".\release\Dota2_LocalPlus" -Recurse -Force
}

Copy-Item ".\README.md" ".\release\Dota2_LocalPlus\README.md" -Force

$launcher = @'
@echo off
setlocal
pushd "%~dp0"
start "" "%~dp0Dota2_LocalPlus.exe"
popd
'@
[System.IO.File]::WriteAllText((Join-Path $PWD "release\Dota2_LocalPlus\Start_Dota2_LocalPlus.bat"), ($launcher -replace "`n", "`r`n"), [System.Text.Encoding]::ASCII)

Compress-Archive -Path ".\release\Dota2_LocalPlus" -DestinationPath ".\release\Dota2_LocalPlus_portable.zip" -Force

Write-Host ""
Write-Host "Portable package created:"
Write-Host "  release\Dota2_LocalPlus\Dota2_LocalPlus.exe"
Write-Host "  release\Dota2_LocalPlus_portable.zip"
