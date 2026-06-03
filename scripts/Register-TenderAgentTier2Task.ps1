param(
    [string]$TaskName = "Tender Agent Tier 2 Triage",
    [string]$RunScript = "",
    [int]$AtHour = 9,
    [ValidateSet("S4U", "Interactive")]
    [string]$LogonType = "Interactive"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($RunScript)) {
    $RunScript = Join-Path $RepoRoot "scripts\run_tier2.ps1"
}

if (-not (Test-Path -LiteralPath $RunScript)) {
    throw "Run script not found: $RunScript"
}

$argumentParts = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"{0}"' -f $RunScript)
)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argumentParts -join " ") -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At (Get-Date).Date.AddHours($AtHour)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType $LogonType -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

[pscustomobject]@{
    task_name = $TaskName
    run_script = $RunScript
    at_hour = $AtHour
    logon_type = $LogonType
} | ConvertTo-Json -Depth 4
