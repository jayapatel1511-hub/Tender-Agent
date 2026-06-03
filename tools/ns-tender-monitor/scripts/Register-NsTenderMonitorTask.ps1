param(
    [string]$TaskName = "Tender Agent Monitor",
    [string]$MonitorScript = "",
    [int]$EveryHours = 4
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
if ([string]::IsNullOrWhiteSpace($MonitorScript)) {
    $MonitorScript = Join-Path $RepoRoot "tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1"
}

if (-not (Test-Path -LiteralPath $MonitorScript)) {
    throw "Monitor script not found: $MonitorScript"
}

$argumentParts = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"{0}"' -f $MonitorScript)
)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argumentParts -join " ")
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(8)
$trigger.Repetition = New-ScheduledTaskRepetitionSettings -Interval (New-TimeSpan -Hours $EveryHours) -Duration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel LeastPrivilege
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

[pscustomobject]@{
    task_name = $TaskName
    monitor_script = $MonitorScript
    every_hours = $EveryHours
} | ConvertTo-Json -Depth 4
