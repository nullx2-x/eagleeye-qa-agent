param(
    [Parameter(Mandatory = $true)][string]$ProjectRoot,
    [ValidateSet("quick", "development", "integration", "standard", "strict", "release_gate", "production_safe", "maintenance", "exploratory_ai")]
    [string]$Mode = "development",
    [int]$TimeoutSeconds = 900
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    uv run python scripts/run_project_qa.py $ProjectRoot --mode $Mode --timeout $TimeoutSeconds
}
finally {
    Pop-Location
}
