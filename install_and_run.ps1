param(
    [string]$DotaPath = ""
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Show-UserMessage {
    param(
        [string]$Message,
        [bool]$IsError = $false
    )

    Add-Type -AssemblyName System.Windows.Forms
    $icon = if ($IsError) {
        [System.Windows.Forms.MessageBoxIcon]::Error
    } else {
        [System.Windows.Forms.MessageBoxIcon]::Information
    }
    [void][System.Windows.Forms.MessageBox]::Show(
        $Message,
        "Dota2 LocalPlus",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        $icon
    )
}

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

function Get-DependencyDirectories {
    $names = @("dependencies", "deps", "wheels", "wheelhouse")
    $dirs = @()
    foreach ($name in $names) {
        $path = Join-Path $PSScriptRoot $name
        if (Test-Path -LiteralPath $path -PathType Container) {
            $dirs += (Resolve-Path -LiteralPath $path).Path
        }
    }
    return $dirs
}

function Install-LocalPython {
    $dependencyDirs = Get-DependencyDirectories
    foreach ($dir in $dependencyDirs) {
        $installer = Get-ChildItem -LiteralPath $dir -File -Filter "python-*.exe" -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            Select-Object -First 1
        if (-not $installer) {
            continue
        }

        Write-Host "Python was not found. Installing bundled Python: $($installer.FullName)"
        Start-Process -FilePath $installer.FullName -ArgumentList @("/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_pip=1", "Include_launcher=1") -Wait
        Add-CommonPythonPaths
        return Find-Python
    }

    return $null
}

function Ensure-Python {
    $python = Find-Python
    if ($python) {
        return $python
    }

    $python = Install-LocalPython
    if ($python) {
        return $python
    }

    Write-Host "Python was not found. Trying to install Python 3.11 with winget..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Python is not installed and winget is unavailable. Please install Python 3.10+ manually, then run this script again."
    }

    winget install --id Python.Python.3.11 -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Python could not be installed automatically. Check the network connection, then install Python 3.11 from Microsoft Store and try again."
    }
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
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed (exit code ${LASTEXITCODE}): $($Arguments -join ' ')"
    }
}

try {
    $python = Ensure-Python

    Write-Host "Using Python:"
    Invoke-Python -Python $python -Arguments @("--version")

    Write-Host "Installing pinned Python runtime dependencies"
    $dependencyDirs = Get-DependencyDirectories
    $localPySide = $null
    foreach ($dir in $dependencyDirs) {
        $wheel = Get-ChildItem -LiteralPath $dir -File -Filter "PySide6*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($wheel) {
            $localPySide = $dir
            break
        }
    }

    Invoke-Python -Python $python -Arguments @("-m", "ensurepip", "--upgrade")
    if ($localPySide) {
        Write-Host "Installing runtime dependencies from local folder: $localPySide"
        Invoke-Python -Python $python -Arguments @("-m", "pip", "install", "--no-index", "--find-links", $localPySide, "-r", ".\requirements.txt")
    } else {
        Write-Host "No local PySide6 wheels found. Installing pinned dependencies from PyPI."
        Invoke-Python -Python $python -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "-r", ".\requirements.txt")
    }

    Write-Host "Writing Dota2 Game State Integration config"
    if ([string]::IsNullOrWhiteSpace($DotaPath)) {
        Invoke-Python -Python $python -Arguments @(".\install_gsi_config.py", "--select")
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
    Write-Host "  Ctrl+Alt+Q  Exit Dota2 LocalPlus"
    Show-UserMessage "Setup complete.`n`nThe overlay has started. Restart Dota2 if it is already running.`n`nTo exit: press Ctrl + Alt + Q, or right-click the system tray icon and choose Exit."
} catch {
    $message = "Setup did not finish.`n`n$($_.Exception.Message)`n`nCheck the network connection, then double-click install_and_run.bat again."
    Write-Error $message
    Show-UserMessage -Message $message -IsError $true
    exit 1
}
