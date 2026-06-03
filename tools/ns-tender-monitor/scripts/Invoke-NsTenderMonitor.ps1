param(
    [string]$Criteria = "",
    [string]$State = "",
    [string]$ProposalRepo = "",
    [string]$Keyword = "",
    [int]$PageSize = 25,
    [int]$MaxPages = 2,
    [switch]$IncludeSeen,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
if ([string]::IsNullOrWhiteSpace($ProposalRepo)) {
    $ProposalRepo = $RepoRoot
}

$BaseUrl = "https://procurement-portal.novascotia.ca"
$Headers = @{
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    "Accept" = "application/json"
    "Referer" = "$BaseUrl/tenders"
}

function Write-JsonFile($Path, $Value) {
    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Get-FieldValue($Object, [string[]]$Names) {
    if ($null -eq $Object) {
        return ""
    }
    foreach ($name in $Names) {
        if ($Object.PSObject.Properties.Name -contains $name -and $null -ne $Object.$name) {
            return [string]$Object.$name
        }
    }
    return ""
}

function Get-TenderId($Tender) {
    $tenderId = Get-FieldValue $Tender @("tenderId", "id")
    return $tenderId.Trim()
}

function Get-Description($Tender) {
    $description = Get-FieldValue $Tender @("description", "memo", "tenderDescription", "scope", "details")
    $description = (($description -replace "\r?\n", " ") -replace "\s+", " ").Trim()
    if (-not [string]::IsNullOrWhiteSpace($description)) {
        return $description
    }
    $fallbackParts = @(
        (Get-FieldValue $Tender @("title")),
        (Get-FieldValue $Tender @("solicitationType")),
        (Get-FieldValue $Tender @("procurementEntity")),
        (Get-FieldValue $Tender @("endUserEntity"))
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    return (($fallbackParts -join ". ") -replace "\r?\n", " " -replace "\s+", " ").Trim()
}

function Get-DetailTender($Session, [string]$TenderId, $FallbackTender) {
    $detailUrl = "$BaseUrl/procurementui/tenders?tenderId=$([uri]::EscapeDataString($TenderId))"
    $detailData = Invoke-RestMethod -Uri $detailUrl -Method Post -Body "null" -ContentType "application/json" -WebSession $Session -Headers $Headers -TimeoutSec 30
    $detail = @($detailData.tenderDataList)[0]
    if ($null -eq $detail) {
        return $FallbackTender
    }
    return $detail
}

function New-OpenTenderRecord($Tender, [datetime]$RunAt) {
    $tenderId = Get-TenderId $Tender
    [pscustomobject]@{
        tender_id = $tenderId
        title = Get-FieldValue $Tender @("title")
        status = Get-FieldValue $Tender @("tenderStatus", "status")
        solicitation_type = Get-FieldValue $Tender @("solicitationType")
        procurement_entity = Get-FieldValue $Tender @("procurementEntity")
        end_user_entity = Get-FieldValue $Tender @("endUserEntity")
        post_date = Get-FieldValue $Tender @("postDate")
        closing_date = Get-FieldValue $Tender @("closingDate")
        description = Get-Description $Tender
        portal_url = "$BaseUrl/tenders/$([uri]::EscapeDataString($tenderId))"
        last_seen_at = $RunAt.ToString("o")
        source = "nova-scotia-procurement-portal"
        raw = $Tender
    }
}

function Write-OpenTenderSnapshot($Repo, [datetime]$RunAt, $Records, [bool]$IsDryRun) {
    $dbDir = Join-Path $Repo "data\open-tenders"
    $runsDir = Join-Path $dbDir "runs"
    New-Item -ItemType Directory -Force -Path $runsDir | Out-Null
    $payload = [pscustomobject]@{
        ran_at = $RunAt.ToString("s")
        source = "https://procurement-portal.novascotia.ca/tenders"
        open_tender_count = @($Records).Count
        tenders = @($Records)
    }
    $snapshotPath = Join-Path $runsDir ("open-tenders-" + $RunAt.ToString("yyyyMMdd-HHmmss") + ".json")
    Write-JsonFile $snapshotPath $payload
    $latestPath = Join-Path $dbDir "open-tenders-latest.json"
    if (-not $IsDryRun) {
        Write-JsonFile $latestPath $payload
    }
    return [pscustomobject]@{
        snapshot_path = $snapshotPath
        latest_path = $latestPath
    }
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-WebRequest -Uri "$BaseUrl/tenders" -UseBasicParsing -WebSession $session -Headers $Headers -TimeoutSec 30 | Out-Null
$auth = Invoke-RestMethod -Uri "$BaseUrl/procurementui/authenticate" -Method Post -Body '{"rpid":"GUEST"}' -ContentType "application/json" -WebSession $session -Headers $Headers -TimeoutSec 30
if ($auth -is [string] -and $auth.Contains("Request Rejected")) {
    throw "Nova Scotia Procurement Portal rejected the guest authentication request."
}
$token = ""
foreach ($tokenField in @("jwttoken", "jwtToken", "token", "access_token")) {
    if ($auth.PSObject.Properties.Name -contains $tokenField -and -not [string]::IsNullOrWhiteSpace([string]$auth.$tokenField)) {
        $token = [string]$auth.$tokenField
        break
    }
}
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Guest authentication did not return a token."
}
$Headers["Authorization"] = "Bearer $token"

$now = Get-Date
$openTenderRecords = New-Object System.Collections.Generic.List[object]
$openTenderIds = New-Object 'System.Collections.Generic.HashSet[string]'

for ($page = 1; $page -le $MaxPages; $page++) {
    $query = [uri]::EscapeDataString($Keyword)
    $url = "$BaseUrl/procurementui/tenders?page=$page&numberOfRecords=$PageSize&sortType=POSTED_DATE_DESC&keyword=$query"
    $data = Invoke-RestMethod -Uri $url -Method Post -Body "null" -ContentType "application/json" -WebSession $session -Headers $Headers -TimeoutSec 30
    $rows = @($data.tenderDataList)
    if ($rows.Count -eq 0) {
        break
    }
    foreach ($row in $rows) {
        $tenderId = Get-TenderId $row
        if ([string]::IsNullOrWhiteSpace($tenderId)) {
            continue
        }
        if ((Get-FieldValue $row @("tenderStatus", "status")).ToLowerInvariant() -ne "open") {
            continue
        }
        if ($openTenderIds.Contains($tenderId)) {
            continue
        }
        [void]$openTenderIds.Add($tenderId)

        $detail = Get-DetailTender $session $tenderId $row
        $openTenderRecords.Add((New-OpenTenderRecord $detail $now))
    }
}

$summaryDir = Join-Path $ProposalRepo "proposals\outputs\ns-tenders"
New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null
$snapshot = Write-OpenTenderSnapshot $ProposalRepo $now @($openTenderRecords.ToArray()) ([bool]$DryRun)

$summary = [pscustomobject]@{
    ran_at = $now.ToString("s")
    dry_run = [bool]$DryRun
    open_tender_count = $openTenderRecords.Count
    open_tender_snapshot_path = $snapshot.snapshot_path
    open_tender_latest_path = $snapshot.latest_path
    matches = 0
    generated_briefs = @()
    generated_analyses = @()
}
$summaryPath = Join-Path $summaryDir ("ns-tender-monitor-" + $now.ToString("yyyyMMdd-HHmmss") + ".json")
Write-JsonFile $summaryPath $summary

[pscustomobject]@{
    matches = 0
    open_tender_count = $openTenderRecords.Count
    open_tender_snapshot_path = $snapshot.snapshot_path
    open_tender_latest_path = $snapshot.latest_path
    generated_briefs = @()
    generated_analyses = @()
    summary_path = $summaryPath
    dry_run = [bool]$DryRun
} | ConvertTo-Json -Depth 8
