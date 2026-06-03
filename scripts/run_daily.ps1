param(
    [string]$MonitorScript = "",
    [string]$State = "",
    [string]$Criteria = "",
    [string]$RunLogDirectory = "proposals\outputs\ns-tenders\run-logs",
    [int]$PageSize = 100,
    [int]$MaxPages = 80,
    [switch]$IncludeSeen,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    if ([string]::IsNullOrWhiteSpace($Criteria)) {
        $Criteria = Join-Path (Get-Location).Path "config\targeted-stream-criteria.json"
    }
    if ([string]::IsNullOrWhiteSpace($MonitorScript)) {
        $MonitorScript = Join-Path (Get-Location).Path "tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1"
    }
    if ([string]::IsNullOrWhiteSpace($State)) {
        $State = Join-Path (Get-Location).Path "data\seen_tenders_state.json"
    }

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
        open_tender_count = if ($summary) { $summary.open_tender_count } else { $null }
        open_tender_snapshot_path = if ($summary) { $summary.open_tender_snapshot_path } else { $null }
        open_tender_latest_path = if ($summary) { $summary.open_tender_latest_path } else { $null }
        candidate_bucket_counts = if ($summary) { $summary.candidate_bucket_counts } else { $null }
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
