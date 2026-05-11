param(
    [string]$DotaPath = ""
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Find-Python {
    $commands = @(
        @{ File = "python"; Args = @("--version") },
        @{ File = "py"; Args = @("-3", "--version") }
    )

    foreach ($command in $commands) {
        $found = Get-Command $command.File -ErrorAction SilentlyContinue
        if (-not $found) {
            continue
        }

        try {
            $process = Start-Process -FilePath $command.File -ArgumentList $command.Args -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$env:TEMP\python-version.out" -RedirectStandardError "$env:TEMP\python-version.err"
            if ($process.ExitCode -eq 0) {
                if ($command.File -eq "py") {
                    return @{ File = "py"; Prefix = @("-3") }
                }
                return @{ File = "python"; Prefix = @() }
            }
        } catch {
            continue
        }
    }

    return $null
}

function Add-CommonPythonPaths {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311",
        "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts",
        "$env:LOCALAPPDATA\Programs\Python\Python312",
        "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
        "$env:ProgramFiles\Python311",
        "$env:ProgramFiles\Python311\Scripts",
        "$env:ProgramFiles\Python312",
        "$env:ProgramFiles\Python312\Scripts"
    )

    foreach ($path in $candidates) {
        if ((Test-Path -LiteralPath $path) -and ($env:Path -notlike "*$path*")) {
            $env:Path = "$path;$env:Path"
        }
    }
}

function Ensure-Python {
    $python = Find-Python
    if ($python) {
        return $python
    }

    Write-Host "Python was not found. Trying to install Python 3.11 with winget..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Python is not installed and winget is unavailable. Please install Python 3.10+ manually, then run this script again."
    }

    winget install --id Python.Python.3.11 -e --source winget --accept-package-agreements --accept-source-agreements
    Add-CommonPythonPaths

    $python = Find-Python
    if (-not $python) {
        throw "Python installation finished, but python was still not found in PATH. Please reopen PowerShell or restart Windows, then run this script again."
    }

    return $python
}

function Invoke-Python {
    param(
        [hashtable]$Python,
        [string[]]$Arguments
    )

    $allArgs = @()
    $allArgs += $Python.Prefix
    $allArgs += $Arguments
    & $Python.File @allArgs
}

$python = Ensure-Python

Write-Host "Using Python:"
Invoke-Python -Python $python -Arguments @("--version")

Write-Host "Installing Python dependency: PySide6"
Invoke-Python -Python $python -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Python -Python $python -Arguments @("-m", "pip", "install", "PySide6")

Write-Host "Writing Dota2 Game State Integration config"
if ([string]::IsNullOrWhiteSpace($DotaPath)) {
    Invoke-Python -Python $python -Arguments @(".\install_gsi_config.py")
} else {
    Invoke-Python -Python $python -Arguments @(".\install_gsi_config.py", $DotaPath)
}

Write-Host "Starting Dota2 Economy Overlay"
$startArgs = @()
$startArgs += $python.Prefix
$startArgs += ".\economy_overlay.py"
Start-Process -FilePath $python.File -ArgumentList $startArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden

Write-Host ""
Write-Host "Done. Restart Dota2 if it is already running."
Write-Host "Default hotkeys:"
Write-Host "  Ctrl+Alt+E  Force show/hide"
Write-Host "  Ctrl+Alt+T  Toggle mouse click-through"
