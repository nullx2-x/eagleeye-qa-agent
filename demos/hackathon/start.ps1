[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8767
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
& uv run uvicorn demos.hackathon.target_app:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
