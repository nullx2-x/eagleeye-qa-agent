$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:EAGLEEYE_AI_PROVIDER = if ($env:EAGLEEYE_AI_PROVIDER) { $env:EAGLEEYE_AI_PROVIDER } else { 'codex-agent' }
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "EagleEye virtual environment was not found: $python"
}
& $python -m app.mcp_entrypoint
