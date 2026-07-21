[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https?://')]
    [string]$Url,

    [string]$ProjectName,

    [switch]$AllowLocalhost
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$arguments = @('run', 'python', '-m', 'scripts.run_url_audit', $Url)
if ($ProjectName) {
    $arguments += @('--project-name', $ProjectName)
}
if ($AllowLocalhost) {
    $arguments += '--allow-localhost'
}
& uv @arguments
exit $LASTEXITCODE
