$ErrorActionPreference = "Stop"
. "$PSScriptRoot\logger.ps1"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Log "Workspace: $Root"
Write-Log "Running uv sync"
& "$env:USERPROFILE\.local\bin\uv.exe" sync --group dev
if ($LASTEXITCODE -ne 0) {
    Write-Log "uv sync failed" "ERROR"
    exit $LASTEXITCODE
}

Write-Log "Running doctor"
& "$env:USERPROFILE\.local\bin\uv.exe" run doctor
exit $LASTEXITCODE
