param(
    [string]$Snapshot = "",
    [string]$Profile = "",
    [string]$Triage = "",
    [string]$State = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    if ([string]::IsNullOrWhiteSpace($Snapshot)) {
        $Snapshot = Join-Path (Get-Location).Path "data\open-tenders\open-tenders-latest.json"
    }
    if ([string]::IsNullOrWhiteSpace($Profile)) {
        $Profile = Join-Path (Get-Location).Path "config\targeted-stream-criteria.json"
    }
    if ([string]::IsNullOrWhiteSpace($Triage)) {
        $Triage = Join-Path (Get-Location).Path "data\triage\triage-latest.json"
    }
    if ([string]::IsNullOrWhiteSpace($State)) {
        $State = Join-Path (Get-Location).Path "data\seen_tenders_state.json"
    }

    python .\scripts\run_triage.py --snapshot $Snapshot --profile $Profile --output $Triage --no-database
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    python .\scripts\run_downstream.py --triage $Triage --snapshot $Snapshot --state $State
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
