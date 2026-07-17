param([switch]$SkipLive)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "EagleEye virtual environment was not found: $python" }
$arguments = @((Join-Path $PSScriptRoot 'quality_gate.py'))
if ($SkipLive) { $arguments += '--skip-live' }
& $python @arguments
exit $LASTEXITCODE
