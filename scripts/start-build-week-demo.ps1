param(
    [switch]$NoBrowser,
    [ValidateRange(5, 60)]
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:EAGLEEYE_AI_PROVIDER = if ($env:EAGLEEYE_AI_PROVIDER) { $env:EAGLEEYE_AI_PROVIDER } else { 'codex-agent' }
$env:EAGLEEYE_CODEX_TRANSPORT = if ($env:EAGLEEYE_CODEX_TRANSPORT) { $env:EAGLEEYE_CODEX_TRANSPORT } else { 'app-server' }
$env:EAGLEEYE_BROWSER_AI_MODEL = if ($env:EAGLEEYE_BROWSER_AI_MODEL) { $env:EAGLEEYE_BROWSER_AI_MODEL } else { 'gpt-5.6-terra' }
if (-not $env:EAGLEEYE_DEMO_TARGET) {
    try {
        $wordpress = Invoke-WebRequest -Uri 'http://127.0.0.1:8888/' -TimeoutSec 4 -UseBasicParsing
        $env:EAGLEEYE_DEMO_TARGET = if ([int]$wordpress.StatusCode -lt 500) {
            'http://127.0.0.1:8888/'
        }
        else {
            'http://127.0.0.1:8766/demo-site/'
        }
    }
    catch {
        $env:EAGLEEYE_DEMO_TARGET = 'http://127.0.0.1:8766/demo-site/'
    }
}

$health = & (Join-Path $PSScriptRoot 'ensure-eagleeye.ps1') -TimeoutSeconds $TimeoutSeconds | ConvertFrom-Json
$targetReady = $false
try {
    $response = Invoke-WebRequest -Uri $env:EAGLEEYE_DEMO_TARGET -TimeoutSec 4 -UseBasicParsing
    $targetReady = [int]$response.StatusCode -lt 500
}
catch {
    $targetReady = $false
}

if (-not $NoBrowser) {
    Start-Process 'http://127.0.0.1:8766/' | Out-Null
}

[PSCustomObject]@{
    status = 'ready'
    eagleeye = $health.api
    mcp = $health.mcp
    selectedProvider = $env:EAGLEEYE_AI_PROVIDER
    browserModel = $env:EAGLEEYE_BROWSER_AI_MODEL
    demoTarget = $env:EAGLEEYE_DEMO_TARGET
    demoTargetReady = $targetReady
    dashboard = 'http://127.0.0.1:8766/'
    extensionPath = (Join-Path $root 'chrome-extension')
} | ConvertTo-Json
