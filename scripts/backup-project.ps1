param(
    [Parameter(Mandatory = $true)][string]$Target
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\logger.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Log "Backing up $Target"
& "$env:USERPROFILE\.local\bin\uv.exe" run kicad-ai backup $Target
exit $LASTEXITCODE
