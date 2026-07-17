param([string]$TaskName = 'EagleEye_StartupHealth')

$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'startup-health.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Recover EagleEye API/MCP and record startup health evidence.' -Force | Out-Null
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName,State,TaskPath | ConvertTo-Json
