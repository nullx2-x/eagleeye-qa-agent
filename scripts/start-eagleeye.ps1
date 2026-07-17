$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:EAGLEEYE_AI_PROVIDER = if ($env:EAGLEEYE_AI_PROVIDER) { $env:EAGLEEYE_AI_PROVIDER } else { 'codex-agent' }
$env:EAGLEEYE_CODEX_TRANSPORT = if ($env:EAGLEEYE_CODEX_TRANSPORT) { $env:EAGLEEYE_CODEX_TRANSPORT } else { 'app-server' }
$env:EAGLEEYE_SELF_REPAIR_ENABLED = if ($env:EAGLEEYE_SELF_REPAIR_ENABLED) { $env:EAGLEEYE_SELF_REPAIR_ENABLED } else { '1' }
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "EagleEye virtual environment was not found: $python"
}
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8766
