param(
    [string]$DotaPath = ""
)

# Kept as a Chinese-named entry point. The installer implementation lives in one file.
& (Join-Path $PSScriptRoot "install_and_run.ps1") -DotaPath $DotaPath
exit $LASTEXITCODE
