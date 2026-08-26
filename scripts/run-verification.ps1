param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = ".",
    [Parameter(Mandatory = $false)]
    [string]$BaseRef = "",
    [Parameter(Mandatory = $false)]
    [string]$HeadRef = "HEAD",
    [Parameter(Mandatory = $false)]
    [string]$ServiceType = "web",
    [Parameter(Mandatory = $false)]
    [string]$Mode = ""
)

$arguments = @(
    "run", "python", "scripts/run_verification.py",
    "--project-root", $ProjectRoot,
    "--head", $HeadRef,
    "--service-type", $ServiceType
)
if ($BaseRef) { $arguments += @("--base", $BaseRef) }
if ($Mode) { $arguments += @("--mode", $Mode) }

& uv @arguments
exit $LASTEXITCODE
