$ErrorActionPreference = "Stop"
. "$PSScriptRoot\logger.ps1"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if ($args.Count -lt 1) {
    Write-Log "Usage: validate.ps1 <project-or-schematic> [--skidl]" "ERROR"
    exit 2
}
Write-Log "Running kicad-ai validate $($args -join ' ')"
& "$env:USERPROFILE\.local\bin\uv.exe" run kicad-ai validate @args
exit $LASTEXITCODE
