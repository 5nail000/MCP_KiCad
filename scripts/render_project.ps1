$ErrorActionPreference = "Stop"
. "$PSScriptRoot\logger.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Log "Rendering KiCad project $($args -join ' ')"
& "$env:USERPROFILE\.local\bin\uv.exe" run python scripts/render_project.py @args
exit $LASTEXITCODE
