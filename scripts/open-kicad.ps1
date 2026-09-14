param(
    [string]$Project = "projects\examples\mcp-test\mcp-test.kicad_pro"
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\logger.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Log "Opening KiCad project: $Project"
& "$env:USERPROFILE\.local\bin\uv.exe" run kicad-ai open $Project
exit $LASTEXITCODE
