$ErrorActionPreference = "Stop"
. "$PSScriptRoot\logger.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Log "Running doctor"
& "$env:USERPROFILE\.local\bin\uv.exe" run doctor
exit $LASTEXITCODE
