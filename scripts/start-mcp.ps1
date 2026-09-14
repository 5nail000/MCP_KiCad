$ErrorActionPreference = "Stop"
. "$PSScriptRoot\logger.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Log "Starting kicad-ai MCP server (stdio). Cursor normally launches this itself."
& "$env:USERPROFILE\.local\bin\uv.exe" run start-mcp
exit $LASTEXITCODE
