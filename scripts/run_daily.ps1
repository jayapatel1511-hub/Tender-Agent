param(
    [string]$MonitorScript = "C:\Users\jpate\.codex\skills\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1",
    [string]$State = "C:\Users\jpate\.codex\skills\ns-tender-monitor\references\seen_tenders_state.json",
    [string]$Criteria = "C:\Users\jpate\.codex\skills\ns-tender-monitor\references\default_criteria.json",
    [string]$RunLogDirectory = "proposals\outputs\ns-tenders\run-logs",
    [int]$PageSize = 25,
    [int]$MaxPages = 2,
    [switch]$IncludeSeen,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    New-Item -ItemType Directory -Force -Path $RunLogDirectory | Out-Null

    $started = Get-Date
    $stamp = $started.ToString("yyyyMMdd-HHmmss")
    $logPath = Join-Path $RunLogDirectory "daily-tender-agent-$stamp.json"

    $status = git status --short --branch
    $remotes = git remote -v

    $powerShellExe = "powershell"
    if (Get-Command pwsh -ErrorAction SilentlyContinue) {
        $powerShellExe = "pwsh"
    }

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $MonitorScript,
        "-ProposalRepo",
        (Get-Location).Path,
        "-State",
        $State,
        "-Criteria",
        $Criteria,
        "-PageSize",
        $PageSize,
        "-MaxPages",
        $MaxPages
    )
    if ($IncludeSeen) {
        $arguments += "-IncludeSeen"
    }
    if ($DryRun) {
        $arguments += "-DryRun"
    }

    $output = @(& $powerShellExe @arguments 2>&1 | ForEach-Object { [string]$_ })
    $exitCode = $LASTEXITCODE
    $completed = Get-Date
    $summary = $null
    try {
        $joinedOutput = $output -join [Environment]::NewLine
        $jsonStart = $joinedOutput.IndexOf("{", [StringComparison]::Ordinal)
        $jsonEnd = $joinedOutput.LastIndexOf("}", [StringComparison]::Ordinal)
        if ($jsonStart -ge 0 -and $jsonEnd -gt $jsonStart) {
            $summaryJson = $joinedOutput.Substring($jsonStart, $jsonEnd - $jsonStart + 1)
            $summary = $summaryJson | ConvertFrom-Json
        }
    }
    catch {
        $summary = $null
    }
    $outputExcerpt = @($output | Select-Object -First 80)

    $log = [ordered]@{
        started_at = $started.ToString("o")
        completed_at = $completed.ToString("o")
        exit_code = $exitCode
        repo_root = (Get-Location).Path
        repo_status = @($status)
        git_remotes = @($remotes)
        monitor_script = $MonitorScript
        state_file = $State
        criteria_file = $Criteria
        command = "$powerShellExe " + ($arguments -join " ")
        matches = if ($summary) { $summary.matches } else { $null }
        generated_briefs = if ($summary) { @($summary.generated_briefs) } else { @() }
        generated_analyses = if ($summary) { @($summary.generated_analyses) } else { @() }
        summary_path = if ($summary) { $summary.summary_path } else { $null }
        dry_run = [bool]$DryRun
        output_excerpt = $outputExcerpt
    }

    $log | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $logPath -Encoding UTF8
    $output
    Write-Host "Run log: $logPath"

    if ($exitCode -ne 0) {
        exit $exitCode
    }
}
finally {
    Pop-Location
}
