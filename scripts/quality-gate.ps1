param([switch]$SkipLive)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$arguments = @((Join-Path $PSScriptRoot 'quality_gate.py'))
if ($SkipLive) { $arguments += '--skip-live' }

$useUv = $true
if (Test-Path -LiteralPath $python) {
    & $python -c "import pytest" 2>$null
    if ($LASTEXITCODE -eq 0) { $useUv = $false }
}
if ($useUv) {
    Push-Location $root
    try {
        uv run python @arguments
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
& $python @arguments
exit $LASTEXITCODE
