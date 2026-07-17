param([ValidateRange(1,10)][int]$Attempts = 5)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $root '.runtime\startup-health'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$ensure = Join-Path $PSScriptRoot 'ensure-eagleeye.ps1'
$python = Join-Path $root '.venv\Scripts\python.exe'
$smoke = Join-Path $PSScriptRoot 'operational_smoke.py'
$lastError = ''

for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
    try {
        $recovery = & $ensure -TimeoutSeconds 30 | ConvertFrom-Json
        $output = Join-Path $runtime 'latest.json'
        & $python $smoke --skip-browser --output $output | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Operational smoke failed with exit code $LASTEXITCODE" }
        $report = Get-Content -Raw -LiteralPath $output | ConvertFrom-Json
        $report | Add-Member -NotePropertyName recovery -NotePropertyValue $recovery -Force
        $report | Add-Member -NotePropertyName attempt -NotePropertyValue $attempt -Force
        $report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $output -Encoding UTF8
        exit 0
    }
    catch {
        $lastError = $_.Exception.Message
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds 5 }
    }
}

@{ status='FAIL'; finishedAt=[DateTime]::UtcNow.ToString('o'); attempts=$Attempts; error=$lastError } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'latest.json') -Encoding UTF8
throw "EagleEye startup health failed after $Attempts attempts: $lastError"
