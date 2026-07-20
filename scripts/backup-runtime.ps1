param(
    [ValidateSet('Backup','Verify','RestoreDrill')][string]$Mode = 'Backup',
    [string]$Archive = '',
    [string]$Target = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'runtime_backup.py'
if (-not $Archive) {
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $Archive = Join-Path $root ".runtime\backups\eagleeye-runtime-$stamp.zip"
}
switch ($Mode) {
    'Backup' { & $python $script backup --output $Archive }
    'Verify' { & $python $script verify $Archive }
    'RestoreDrill' {
        if (-not $Target) { $Target = Join-Path $root ".runtime\restore-drill\$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))" }
        & $python $script restore $Archive --target $Target
    }
}
exit $LASTEXITCODE
