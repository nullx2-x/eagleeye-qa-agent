param(
    [ValidateRange(1, 60)]
    [int]$TimeoutSeconds = 15
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Test-Endpoint {
    param([Parameter(Mandatory)][string]$Uri)
    try {
        Invoke-WebRequest -Uri $Uri -TimeoutSec 2 -UseBasicParsing | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

$apiStarted = $false
$mcpStarted = $false
if (-not (Test-Endpoint -Uri 'http://127.0.0.1:8766/health')) {
    Start-Process `
        -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'start-eagleeye.ps1')) `
        -WorkingDirectory $root `
        -WindowStyle Hidden | Out-Null
    $apiStarted = $true
}
if (-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 8768 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    Start-Process `
        -FilePath 'powershell.exe' `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'start-mcp.ps1')) `
        -WorkingDirectory $root `
        -WindowStyle Hidden | Out-Null
    $mcpStarted = $true
}

$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
do {
    $apiHealthy = Test-Endpoint -Uri 'http://127.0.0.1:8766/health'
    $mcpHealthy = Test-NetConnection -ComputerName 127.0.0.1 -Port 8768 -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($apiHealthy -and $mcpHealthy) {
        break
    }
    Start-Sleep -Milliseconds 300
} while ([DateTime]::UtcNow -lt $deadline)

if (-not $apiHealthy -or -not $mcpHealthy) {
    throw "EagleEye recovery failed: api=$apiHealthy mcp=$mcpHealthy"
}

[PSCustomObject]@{
    api = 'healthy'
    mcp = 'healthy'
    apiStarted = $apiStarted
    mcpStarted = $mcpStarted
    dashboard = 'http://127.0.0.1:8766/'
} | ConvertTo-Json
