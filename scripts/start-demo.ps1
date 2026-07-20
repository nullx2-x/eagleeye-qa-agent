$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "EagleEye virtual environment was not found: $python"
}
& $python -m uvicorn app.demo:app --host 127.0.0.1 --port 8767
